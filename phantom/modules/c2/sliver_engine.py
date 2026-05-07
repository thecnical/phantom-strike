"""
PhantomStrike Sliver C2 Integration — SliverC2Engine.

Integrates the Sliver C2 framework (https://github.com/BishopFox/sliver) for
implant generation and management.  Degrades gracefully when Sliver is not
installed: all methods return ``{"success": False, "error": str}`` and the
C2Agent falls back to the existing ``phantom-c2`` module.

Requirements: 15.1–15.4, 19.2
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, Optional

from phantom.modules.base import BaseModule, ModuleResult
from phantom.core.events import Event, EventType

logger = logging.getLogger("phantom.c2.sliver")

# Human-readable error surfaced when Sliver is absent.
_SLIVER_NOT_INSTALLED = (
    "Sliver not installed — install from https://github.com/BishopFox/sliver "
    "or run: curl https://sliver.sh/install | sudo bash"
)

# Valid implant formats per OS
_VALID_FORMATS = {
    "linux": ["elf", "shared_lib", "shellcode"],
    "windows": ["exe", "dll", "shellcode", "service"],
    "macos": ["macho", "shared_lib"],
    "darwin": ["macho", "shared_lib"],
}

# Valid architectures
_VALID_ARCHES = {"amd64", "386", "arm64", "arm"}


class SliverC2Engine(BaseModule):
    """
    Sliver C2 integration module.

    Provides:
      - ``is_available()``     — check whether sliver-client is in PATH
      - ``generate_implant()`` — generate a Sliver implant via gRPC API;
                                 falls back to phantom-c2 when Sliver is absent
      - ``run()``              — BaseModule entry-point (dispatches to above)

    All public methods return structured dicts or ModuleResult objects and
    never raise unhandled exceptions.
    """

    # ------------------------------------------------------------------ #
    # BaseModule interface                                                 #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return "phantom-sliver"

    @property
    def description(self) -> str:
        return "Sliver C2 integration — implant generation with phantom-c2 fallback"

    @property
    def category(self) -> str:
        return "c2"

    async def _setup(self) -> None:
        """Probe Sliver availability and cache the result."""
        self._sliver_available: bool = self.is_available()
        if self._sliver_available:
            logger.info("[Sliver] sliver-client found in PATH")
        else:
            logger.warning(
                "[Sliver] sliver-client not found in PATH — Sliver C2 disabled. %s",
                _SLIVER_NOT_INSTALLED,
            )

        # Lazy reference to the phantom-c2 fallback module; injected by the
        # loader when both modules are registered.
        self._c2_fallback: Optional[Any] = None

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """
        Primary BaseModule entry-point.

        Supported operations (via ``options["operation"]``):
          - ``generate_implant`` (default)
          - ``status``

        Returns a ModuleResult whose ``data`` mirrors the dict returned by
        ``generate_implant()`` or a status summary.
        """
        options = options or {}
        operation = options.get("operation", "generate_implant")
        start_time = datetime.now()

        try:
            if operation == "generate_implant":
                result = self.generate_implant(
                    lhost=options.get("lhost", target),
                    lport=options.get("lport", 443),
                    os=options.get("os", "linux"),
                    arch=options.get("arch", "amd64"),
                    format=options.get("format", "elf"),
                )
                success = result.get("success", False)
                errors = [] if success else [result.get("error", "unknown error")]
                return ModuleResult(
                    module_name=self.name,
                    operation=operation,
                    success=success,
                    data=result,
                    errors=errors,
                    findings_count=1 if success else 0,
                    start_time=start_time,
                    end_time=datetime.now(),
                )

            elif operation == "status":
                data = {
                    "sliver_available": self._sliver_available,
                    "sliver_client_path": shutil.which("sliver-client") or "",
                    "fallback": "phantom-c2",
                }
                return ModuleResult(
                    module_name=self.name,
                    operation=operation,
                    success=True,
                    data=data,
                    start_time=start_time,
                    end_time=datetime.now(),
                )

            else:
                return ModuleResult(
                    module_name=self.name,
                    operation=operation,
                    success=False,
                    errors=[f"Unknown operation: {operation!r}"],
                    start_time=start_time,
                    end_time=datetime.now(),
                )

        except Exception as exc:  # pragma: no cover — safety net
            logger.exception("[Sliver] Unexpected error in run()")
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Unexpected error: {exc}"],
                start_time=start_time,
                end_time=datetime.now(),
            )

    # ------------------------------------------------------------------ #
    # Public Sliver methods                                                #
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        """
        Return ``True`` when the ``sliver-client`` binary is present in PATH.

        Uses ``shutil.which()`` so no subprocess is spawned and the check is
        always safe to call.

        Requirements: 15.2, 19.2
        """
        return shutil.which("sliver-client") is not None

    def generate_implant(
        self,
        lhost: str,
        lport: int,
        os: str = "linux",
        arch: str = "amd64",
        format: str = "elf",
    ) -> Dict[str, Any]:
        """
        Generate a Sliver C2 implant.

        When Sliver is available the method calls the Sliver gRPC API via the
        ``sliver-client`` CLI to produce a compiled implant binary.  When
        Sliver is unavailable it delegates to the ``phantom-c2`` module for
        payload generation.

        Args:
            lhost:  Listener host / callback address for the implant.
            lport:  Listener port (must be in 1–65535).
            os:     Target operating system (``linux``, ``windows``, ``macos``).
            arch:   Target architecture (``amd64``, ``386``, ``arm64``, ``arm``).
            format: Implant format (``elf``, ``exe``, ``dll``, ``macho``, …).

        Returns:
            On success::

                {"success": True, "implant_path": str, "implant_name": str}

            On failure::

                {"success": False, "error": str}

        Requirements: 15.1, 15.2, 15.3, 15.4
        """
        # ---- lport validation (Req 15.4) --------------------------------
        try:
            lport = int(lport)
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": f"Invalid lport {lport!r}: must be an integer in range 1–65535",
            }

        if not (1 <= lport <= 65535):
            return {
                "success": False,
                "error": (
                    f"Invalid lport {lport}: must be in range 1–65535"
                ),
            }

        # ---- Sliver available path (Req 15.1) ---------------------------
        if self.is_available():
            return self._generate_via_sliver_grpc(lhost, lport, os, arch, format)

        # ---- Sliver unavailable — fallback to phantom-c2 (Req 15.2, 15.3) --
        logger.info(
            "[Sliver] sliver-client not found — delegating to phantom-c2 fallback"
        )
        return self._generate_via_phantom_c2(lhost, lport, os, arch, format)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _generate_via_sliver_grpc(
        self,
        lhost: str,
        lport: int,
        target_os: str,
        arch: str,
        fmt: str,
    ) -> Dict[str, Any]:
        """
        Call the Sliver gRPC API through the ``sliver-client`` CLI to compile
        and retrieve an implant binary.

        The Sliver CLI ``generate`` sub-command accepts the following flags::

            sliver-client generate --mtls <lhost>:<lport> --os <os> --arch <arch>
                                   --format <format> --save <output_dir>

        Returns the standard ``{"success": bool, ...}`` dict.
        """
        output_dir = os.path.join(
            os.path.expanduser("~"), ".phantom-strike", "implants"
        )
        os.makedirs(output_dir, exist_ok=True)

        # Derive a deterministic implant name from the parameters so callers
        # can reference it without parsing filesystem output.
        implant_name = f"phantom_{target_os}_{arch}_{lport}"
        if fmt not in ("elf", "macho"):
            # Append extension for non-default formats
            ext_map = {
                "exe": ".exe", "dll": ".dll", "shellcode": ".bin",
                "shared_lib": ".so", "service": ".exe",
            }
            implant_name += ext_map.get(fmt, "")

        implant_path = os.path.join(output_dir, implant_name)

        cmd = [
            "sliver-client",
            "generate",
            "--mtls", f"{lhost}:{lport}",
            "--os", target_os,
            "--arch", arch,
            "--format", fmt,
            "--save", output_dir,
            "--name", implant_name,
        ]

        logger.info("[Sliver] Generating implant: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            # Binary disappeared between is_available() and here — treat as
            # unavailable and fall back.
            logger.warning("[Sliver] sliver-client disappeared — falling back to phantom-c2")
            return self._generate_via_phantom_c2(lhost, lport, target_os, arch, fmt)
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Sliver gRPC call timed out after 120 s — is the Sliver server running?",
            }
        except OSError as exc:
            return {"success": False, "error": f"Sliver gRPC error: {exc}"}

        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error("[Sliver] generate failed (rc=%d): %s", result.returncode, stderr)
            return {
                "success": False,
                "error": f"Sliver generate failed (rc={result.returncode}): {stderr}",
            }

        # Sliver writes the binary to output_dir; locate it.
        actual_path = self._find_generated_implant(output_dir, implant_name)
        if actual_path:
            implant_path = actual_path

        logger.info("[Sliver] Implant generated: %s", implant_path)

        await_event = Event(
            type=EventType.MODULE_LOADED,
            data={
                "module": self.name,
                "operation": "generate_implant",
                "implant_path": implant_path,
                "implant_name": implant_name,
            },
            source=self.name,
        )
        # Fire-and-forget; we are in a sync context here.
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.event_bus.emit(await_event))
        except RuntimeError:
            pass  # No event loop — skip event emission

        return {
            "success": True,
            "implant_path": implant_path,
            "implant_name": implant_name,
            "framework": "sliver",
            "lhost": lhost,
            "lport": lport,
            "os": target_os,
            "arch": arch,
            "format": fmt,
        }

    def _generate_via_phantom_c2(
        self,
        lhost: str,
        lport: int,
        target_os: str,
        arch: str,
        fmt: str,
    ) -> Dict[str, Any]:
        """
        Delegate implant generation to the existing ``phantom-c2`` module.

        This is the graceful fallback path when Sliver is not installed
        (Requirements 15.2, 15.3, 19.2).

        If the ``phantom-c2`` module reference has been injected via
        ``set_c2_fallback()``, it is called directly.  Otherwise the method
        returns a structured error indicating Sliver is unavailable.
        """
        if self._c2_fallback is not None:
            try:
                # phantom-c2's _generate_agent_payload() returns a dict with
                # "python", "bash", and "config" keys.
                payload = self._c2_fallback._generate_agent_payload(
                    lhost=lhost,
                    lport=lport,
                )
                # Persist the Python agent to disk so callers get a real path.
                output_dir = os.path.join(
                    os.path.expanduser("~"), ".phantom-strike", "implants"
                )
                os.makedirs(output_dir, exist_ok=True)
                implant_name = f"phantom_c2_{target_os}_{lport}.py"
                implant_path = os.path.join(output_dir, implant_name)
                with open(implant_path, "w") as fh:
                    fh.write(payload.get("python", ""))

                logger.info(
                    "[Sliver] phantom-c2 fallback implant written to %s", implant_path
                )
                return {
                    "success": True,
                    "implant_path": implant_path,
                    "implant_name": implant_name,
                    "framework": "phantom-c2",
                    "lhost": lhost,
                    "lport": lport,
                    "os": target_os,
                    "arch": arch,
                    "format": "python",
                    "fallback": True,
                }
            except Exception as exc:
                logger.error("[Sliver] phantom-c2 fallback error: %s", exc)
                return {
                    "success": False,
                    "error": f"Sliver not installed and phantom-c2 fallback failed: {exc}",
                }

        # No fallback module available — return the canonical unavailable error.
        return {"success": False, "error": _SLIVER_NOT_INSTALLED}

    def _find_generated_implant(self, output_dir: str, expected_name: str) -> Optional[str]:
        """
        Locate the most recently modified file in *output_dir* that matches
        *expected_name* (case-insensitive prefix match).

        Returns the full path on success, or ``None`` if nothing is found.
        """
        try:
            candidates = [
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.lower().startswith(expected_name.lower())
            ]
            if not candidates:
                return None
            # Return the most recently modified file.
            return max(candidates, key=os.path.getmtime)
        except OSError:
            return None

    def set_c2_fallback(self, c2_module: Any) -> None:
        """
        Inject the ``phantom-c2`` module instance for use as a fallback.

        Called by the module loader after both modules are registered so that
        ``SliverC2Engine`` can delegate to ``C2Engine`` without a circular
        import.
        """
        self._c2_fallback = c2_module
        logger.debug("[Sliver] phantom-c2 fallback module registered")
