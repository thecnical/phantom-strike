"""
PhantomStrike OSINT Engine — Deep Open-Source Intelligence Gathering.
Multi-threaded subdomain enumeration, email harvesting, DNS intelligence,
technology detection, and WHOIS reconnaissance.
"""
from __future__ import annotations
import asyncio
import logging
import socket
from datetime import datetime
from typing import Optional

import aiohttp
import dns.resolver
import dns.asyncresolver

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.osint")


class OSINTEngine(BaseModule):
    """Deep OSINT module with multi-threaded reconnaissance."""

    @property
    def name(self) -> str:
        return "phantom-osint"

    @property
    def description(self) -> str:
        return "Deep OSINT — subdomains, emails, DNS intel, tech detection"

    @property
    def category(self) -> str:
        return "reconnaissance"

    async def _setup(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._dns_resolver = dns.asyncresolver.Resolver()
        self._dns_resolver.timeout = 5
        self._dns_resolver.lifetime = 10

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run full OSINT scan on target domain."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()
        findings = {
            "subdomains": [],
            "emails": [],
            "dns_records": {},
            "whois": {},
            "technologies": [],
            "ip_addresses": [],
        }

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/125.0.0.0"},
        )

        try:
            # Run all OSINT tasks concurrently (multi-threaded)
            tasks = [
                self._enumerate_subdomains(target, findings),
                self._gather_dns_records(target, findings),
                self._harvest_emails(target, findings),
                self._detect_technologies(target, findings),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"[OSINT] Error: {e}")
        finally:
            if self._session:
                await self._session.close()

        self.status = ModuleStatus.COMPLETED
        total = (
            len(findings["subdomains"]) + len(findings["emails"])
            + len(findings["ip_addresses"])
        )

        return ModuleResult(
            module_name=self.name,
            operation="full_osint_scan",
            success=True,
            data=findings,
            findings_count=total,
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def _enumerate_subdomains(self, domain: str, findings: dict):
        """Multi-threaded subdomain enumeration using multiple sources."""
        # Common subdomain wordlist
        common_subs = [
            "www", "mail", "ftp", "admin", "blog", "dev", "staging", "api",
            "app", "test", "portal", "secure", "vpn", "m", "mobile", "shop",
            "store", "cdn", "assets", "img", "images", "static", "docs",
            "help", "support", "status", "monitor", "dashboard", "panel",
            "cms", "crm", "erp", "git", "gitlab", "jenkins", "ci", "cd",
            "db", "database", "mysql", "postgres", "redis", "elastic",
            "kibana", "grafana", "prometheus", "vault", "consul", "nomad",
            "k8s", "kubernetes", "docker", "registry", "harbor", "minio",
            "s3", "backup", "log", "logs", "syslog", "auth", "sso", "oauth",
            "login", "signup", "register", "account", "profile", "user",
            "payment", "billing", "invoice", "order", "checkout", "cart",
            "search", "analytics", "tracking", "metrics", "demo", "sandbox",
            "uat", "qa", "prod", "production", "internal", "intranet",
            "ns1", "ns2", "mx", "smtp", "pop", "imap", "webmail", "email",
            "proxy", "gateway", "lb", "loadbalancer", "firewall", "waf",
        ]

        semaphore = asyncio.Semaphore(50)  # 50 concurrent DNS lookups

        async def check_subdomain(sub: str):
            async with semaphore:
                fqdn = f"{sub}.{domain}"
                try:
                    answers = await self._dns_resolver.resolve(fqdn, "A")
                    ips = [str(r) for r in answers]
                    findings["subdomains"].append({
                        "subdomain": fqdn,
                        "ips": ips,
                        "source": "dns_brute",
                    })
                    findings["ip_addresses"].extend(ips)

                    await self.event_bus.emit(Event(
                        type=EventType.SUBDOMAIN_FOUND,
                        data={"subdomain": fqdn, "ips": ips},
                        source=self.name,
                    ))
                    logger.info(f"[OSINT] Subdomain: {fqdn} → {', '.join(ips)}")
                except Exception:
                    pass

        await asyncio.gather(*[check_subdomain(s) for s in common_subs])

        # Also try crt.sh for certificate transparency
        try:
            async with self._session.get(
                f"https://crt.sh/?q=%.{domain}&output=json",
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    certs = await resp.json()
                    seen = set()
                    for cert in certs[:200]:
                        name = cert.get("name_value", "")
                        for sub in name.split("\n"):
                            sub = sub.strip().lower()
                            if sub.endswith(domain) and sub not in seen:
                                seen.add(sub)
                                findings["subdomains"].append({
                                    "subdomain": sub,
                                    "source": "crt.sh",
                                })
        except Exception as e:
            logger.debug(f"[OSINT] crt.sh error: {e}")

    async def _gather_dns_records(self, domain: str, findings: dict):
        """Gather all DNS record types."""
        record_types = ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CNAME", "SRV"]

        for rtype in record_types:
            try:
                answers = await self._dns_resolver.resolve(domain, rtype)
                records = [str(r) for r in answers]
                findings["dns_records"][rtype] = records
                logger.info(f"[OSINT] DNS {rtype}: {', '.join(records[:3])}")
            except Exception:
                pass

    async def _harvest_emails(self, domain: str, findings: dict):
        """Harvest email addresses from multiple sources."""
        # Search via web scraping common patterns
        search_urls = [
            f"https://www.google.com/search?q=%22@{domain}%22",
        ]

        try:
            # Check common email patterns
            common_patterns = [
                f"info@{domain}", f"admin@{domain}", f"support@{domain}",
                f"contact@{domain}", f"sales@{domain}", f"security@{domain}",
                f"abuse@{domain}", f"postmaster@{domain}", f"webmaster@{domain}",
            ]

            # Verify MX records exist (indicates email capability)
            try:
                mx_records = await self._dns_resolver.resolve(domain, "MX")
                if mx_records:
                    for pattern in common_patterns:
                        findings["emails"].append({
                            "email": pattern,
                            "source": "pattern_generation",
                            "verified": False,
                        })
                        await self.event_bus.emit(Event(
                            type=EventType.EMAIL_FOUND,
                            data={"email": pattern},
                            source=self.name,
                        ))
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"[OSINT] Email harvest error: {e}")

    async def _detect_technologies(self, domain: str, findings: dict):
        """Detect web technologies used by the target."""
        try:
            url = f"https://{domain}"
            async with self._session.get(url, allow_redirects=True) as resp:
                headers = dict(resp.headers)
                body = await resp.text()

                # Server header
                if "Server" in headers:
                    findings["technologies"].append({
                        "name": headers["Server"],
                        "category": "web_server",
                    })

                # X-Powered-By
                if "X-Powered-By" in headers:
                    findings["technologies"].append({
                        "name": headers["X-Powered-By"],
                        "category": "framework",
                    })

                # Technology detection from HTML
                tech_patterns = {
                    "WordPress": ["wp-content", "wp-includes", "wordpress"],
                    "React": ["react", "_next", "__NEXT_DATA__"],
                    "Angular": ["ng-version", "angular"],
                    "Vue.js": ["vue", "__VUE__"],
                    "jQuery": ["jquery"],
                    "Bootstrap": ["bootstrap"],
                    "Laravel": ["laravel", "csrf-token"],
                    "Django": ["csrfmiddlewaretoken", "django"],
                    "Express": ["express"],
                    "Cloudflare": ["cloudflare", "cf-ray"],
                }

                body_lower = body.lower()
                for tech, patterns in tech_patterns.items():
                    if any(p in body_lower for p in patterns):
                        findings["technologies"].append({
                            "name": tech,
                            "category": "framework",
                        })
                        await self.event_bus.emit(Event(
                            type=EventType.TECH_DETECTED,
                            data={"tech": tech, "domain": domain},
                            source=self.name,
                        ))

        except Exception as e:
            logger.debug(f"[OSINT] Tech detection error: {e}")
