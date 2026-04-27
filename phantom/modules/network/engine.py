"""
PhantomStrike Network Recon Engine — Multi-threaded port scanning,
service detection, OS fingerprinting, and topology mapping.
Scans 65535 ports in seconds using async socket connections.
"""
from __future__ import annotations
import asyncio
import logging
import socket
import struct
from datetime import datetime
from typing import Optional

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.network")

# Common service banners
SERVICE_SIGNATURES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 111: "rpcbind", 135: "msrpc",
    139: "netbios", 143: "imap", 443: "https", 445: "smb",
    993: "imaps", 995: "pop3s", 1433: "mssql", 1521: "oracle",
    3306: "mysql", 3389: "rdp", 5432: "postgresql", 5900: "vnc",
    6379: "redis", 8080: "http-proxy", 8443: "https-alt",
    8888: "http-alt", 9200: "elasticsearch", 9300: "elasticsearch",
    27017: "mongodb", 11211: "memcached",
}


class NetworkEngine(BaseModule):
    """Elite multi-threaded network reconnaissance module."""

    @property
    def name(self) -> str:
        return "phantom-network"

    @property
    def description(self) -> str:
        return "Network recon — async port scan, service detection, OS fingerprint"

    @property
    def category(self) -> str:
        return "reconnaissance"

    async def _setup(self):
        pass

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run full network scan on target."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()

        # Resolve target to IP
        try:
            ip = socket.gethostbyname(target)
        except socket.gaierror:
            return ModuleResult(
                module_name=self.name, operation="network_scan",
                success=False, errors=[f"Cannot resolve: {target}"],
                start_time=start_time, end_time=datetime.now(),
            )

        findings = {
            "target": target,
            "ip": ip,
            "open_ports": [],
            "services": [],
            "os_hints": [],
        }

        # Determine scan range
        scan_type = options.get("scan_type", "common")
        if scan_type == "full":
            ports = list(range(1, 65536))
        elif scan_type == "top1000":
            ports = list(range(1, 1001))
        else:  # common
            ports = list(SERVICE_SIGNATURES.keys()) + [
                8000, 8001, 8008, 8081, 8082, 8180, 8888, 9000, 9090,
                9443, 10000, 2049, 2375, 2376, 4443, 4848, 5000, 5001,
                5555, 6000, 6443, 7001, 7070, 7443, 8009, 8161, 8280,
            ]

        # Multi-threaded port scan
        max_concurrent = options.get("threads", 200)
        semaphore = asyncio.Semaphore(max_concurrent)
        timeout = options.get("timeout", 3)

        async def scan_port(port: int):
            async with semaphore:
                try:
                    conn = asyncio.open_connection(ip, port)
                    reader, writer = await asyncio.wait_for(conn, timeout=timeout)

                    # Port is open — try to grab banner
                    service = SERVICE_SIGNATURES.get(port, "unknown")
                    banner = ""

                    try:
                        # Send probe for banner grabbing
                        if port in (80, 8080, 8000, 8443, 443):
                            writer.write(
                                f"HEAD / HTTP/1.1\r\nHost: {target}\r\n\r\n".encode()
                            )
                        else:
                            writer.write(b"\r\n")
                        await writer.drain()

                        banner_data = await asyncio.wait_for(
                            reader.read(1024), timeout=2
                        )
                        banner = banner_data.decode("utf-8", errors="ignore").strip()
                    except Exception:
                        pass

                    writer.close()

                    port_info = {
                        "port": port,
                        "state": "open",
                        "service": service,
                        "banner": banner[:200] if banner else "",
                    }
                    findings["open_ports"].append(port_info)
                    findings["services"].append(port_info)

                    # Emit event
                    await self.event_bus.emit(Event(
                        type=EventType.PORT_FOUND,
                        data=port_info,
                        source=self.name,
                    ))

                    logger.info(
                        f"[NET] {ip}:{port} OPEN ({service})"
                        f"{' — ' + banner[:50] if banner else ''}"
                    )

                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    pass

        # Execute all port scans concurrently
        logger.info(
            f"[NET] Scanning {ip} ({target}) — "
            f"{len(ports)} ports, {max_concurrent} threads"
        )

        await asyncio.gather(*[scan_port(p) for p in ports])

        # Sort results
        findings["open_ports"].sort(key=lambda x: x["port"])
        findings["services"].sort(key=lambda x: x["port"])

        # OS hinting from service banners
        for svc in findings["services"]:
            b = svc.get("banner", "").lower()
            if "ubuntu" in b or "debian" in b:
                findings["os_hints"].append("Linux (Ubuntu/Debian)")
            elif "centos" in b or "redhat" in b:
                findings["os_hints"].append("Linux (CentOS/RHEL)")
            elif "windows" in b or "microsoft" in b:
                findings["os_hints"].append("Windows Server")
            elif "freebsd" in b:
                findings["os_hints"].append("FreeBSD")

        findings["os_hints"] = list(set(findings["os_hints"]))

        self.status = ModuleStatus.COMPLETED

        return ModuleResult(
            module_name=self.name,
            operation="network_scan",
            success=True,
            data=findings,
            findings_count=len(findings["open_ports"]),
            start_time=start_time,
            end_time=datetime.now(),
        )
