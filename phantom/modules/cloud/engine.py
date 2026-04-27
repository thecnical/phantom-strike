"""
PhantomStrike Cloud Security Scanner — AWS, Azure, GCP misconfiguration detection.
Multi-threaded cloud asset enumeration and vulnerability discovery.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.cloud")

# Common S3 bucket name patterns
S3_WORDLIST = [
    "backup", "backups", "data", "files", "media", "static", "assets",
    "uploads", "images", "docs", "documents", "logs", "temp", "tmp",
    "dev", "staging", "prod", "production", "test", "internal",
    "private", "public", "www", "web", "api", "config", "db",
    "database", "export", "dump", "archive", "old", "legacy",
]

# Azure blob endpoints
AZURE_BLOB_SUFFIXES = [".blob.core.windows.net", ".file.core.windows.net"]

# GCP storage endpoint
GCP_STORAGE_URL = "https://storage.googleapis.com"


class CloudEngine(BaseModule):
    """Multi-threaded cloud security scanner — AWS, Azure, GCP."""

    @property
    def name(self) -> str:
        return "phantom-cloud"

    @property
    def description(self) -> str:
        return "Cloud security — S3 buckets, Azure blobs, GCP storage, misconfigs"

    @property
    def category(self) -> str:
        return "cloud"

    async def _setup(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Scan for cloud misconfigurations related to target domain."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()

        findings = {
            "target": target,
            "s3_buckets": [],
            "azure_blobs": [],
            "gcp_buckets": [],
            "exposed_metadata": [],
            "misconfigurations": [],
        }

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/125.0.0.0"},
        )

        try:
            # Strip domain to base name
            base_name = target.replace("www.", "").split(".")[0]

            # Multi-threaded cloud enumeration
            tasks = [
                self._enum_s3_buckets(base_name, target, findings),
                self._enum_azure_blobs(base_name, findings),
                self._enum_gcp_buckets(base_name, findings),
                self._check_metadata_endpoints(target, findings),
                self._check_cloud_misconfigs(target, findings),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"[CLOUD] Error: {e}")
        finally:
            if self._session:
                await self._session.close()

        total = sum(len(findings[k]) for k in [
            "s3_buckets", "azure_blobs", "gcp_buckets", "exposed_metadata",
        ])

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name, operation="cloud_scan",
            success=True, data=findings, findings_count=total,
            start_time=start_time, end_time=datetime.now(),
        )

    async def _enum_s3_buckets(self, base_name: str, domain: str, findings: dict):
        """Enumerate potentially open S3 buckets."""
        semaphore = asyncio.Semaphore(30)
        candidates = []

        # Generate bucket name candidates
        for suffix in S3_WORDLIST:
            candidates.extend([
                f"{base_name}-{suffix}",
                f"{suffix}-{base_name}",
                f"{base_name}{suffix}",
                f"{base_name}.{suffix}",
            ])
        candidates.append(base_name)
        candidates.append(domain.replace(".", "-"))

        async def check_bucket(name: str):
            async with semaphore:
                url = f"https://{name}.s3.amazonaws.com"
                try:
                    async with self._session.get(url) as resp:
                        if resp.status == 200:
                            body = await resp.text()
                            is_listable = "<ListBucketResult" in body
                            bucket = {
                                "name": name,
                                "url": url,
                                "status": resp.status,
                                "listable": is_listable,
                                "severity": "critical" if is_listable else "medium",
                            }
                            findings["s3_buckets"].append(bucket)
                            await self.event_bus.emit(Event(
                                type=EventType.VULN_FOUND,
                                data={**bucket, "type": "open_s3_bucket"},
                                source=self.name, severity="critical" if is_listable else "medium",
                            ))
                            logger.info(
                                f"[CLOUD] 🪣 S3 bucket found: {name} "
                                f"({'LISTABLE!' if is_listable else 'exists'})"
                            )
                        elif resp.status == 403:
                            # Bucket exists but private
                            findings["s3_buckets"].append({
                                "name": name, "url": url,
                                "status": 403, "listable": False, "severity": "info",
                            })
                except Exception:
                    pass

        await asyncio.gather(*[check_bucket(c) for c in candidates])

    async def _enum_azure_blobs(self, base_name: str, findings: dict):
        """Enumerate Azure Blob Storage containers."""
        semaphore = asyncio.Semaphore(20)
        candidates = [base_name, f"{base_name}dev", f"{base_name}prod", f"{base_name}backup"]

        async def check_blob(name: str):
            async with semaphore:
                url = f"https://{name}.blob.core.windows.net/?comp=list"
                try:
                    async with self._session.get(url) as resp:
                        if resp.status == 200:
                            findings["azure_blobs"].append({
                                "name": name, "url": url,
                                "status": resp.status, "severity": "critical",
                            })
                            logger.info(f"[CLOUD] 📦 Azure blob found: {name}")
                except Exception:
                    pass

        await asyncio.gather(*[check_blob(c) for c in candidates])

    async def _enum_gcp_buckets(self, base_name: str, findings: dict):
        """Enumerate Google Cloud Storage buckets."""
        semaphore = asyncio.Semaphore(20)
        candidates = [base_name, f"{base_name}-backup", f"{base_name}-data"]

        async def check_gcp(name: str):
            async with semaphore:
                url = f"{GCP_STORAGE_URL}/{name}"
                try:
                    async with self._session.get(url) as resp:
                        if resp.status == 200:
                            findings["gcp_buckets"].append({
                                "name": name, "url": url,
                                "status": resp.status, "severity": "high",
                            })
                            logger.info(f"[CLOUD] ☁️ GCP bucket found: {name}")
                except Exception:
                    pass

        await asyncio.gather(*[check_gcp(c) for c in candidates])

    async def _check_metadata_endpoints(self, target: str, findings: dict):
        """Check if target is vulnerable to cloud metadata SSRF."""
        metadata_urls = [
            # AWS IMDSv1
            ("http://169.254.169.254/latest/meta-data/", "AWS"),
            ("http://169.254.169.254/latest/user-data/", "AWS"),
            # GCP
            ("http://metadata.google.internal/computeMetadata/v1/", "GCP"),
            # Azure
            ("http://169.254.169.254/metadata/instance?api-version=2021-02-01", "Azure"),
        ]

        for meta_url, cloud_type in metadata_urls:
            try:
                # Try SSRF via the target
                test_url = f"https://{target}/?url={meta_url}"
                async with self._session.get(test_url, allow_redirects=False) as resp:
                    body = await resp.text()
                    if any(indicator in body for indicator in [
                        "ami-id", "instance-id", "compute", "subscriptionId",
                    ]):
                        findings["exposed_metadata"].append({
                            "cloud": cloud_type, "url": meta_url,
                            "severity": "critical",
                        })
                        logger.info(f"[CLOUD] 🔴 METADATA EXPOSED: {cloud_type}")
            except Exception:
                pass

    async def _check_cloud_misconfigs(self, target: str, findings: dict):
        """Check common cloud misconfigurations."""
        checks = [
            (f"https://{target}/.env", "Exposed .env file"),
            (f"https://{target}/.git/HEAD", "Exposed .git directory"),
            (f"https://{target}/wp-config.php.bak", "WordPress config backup"),
            (f"https://{target}/.aws/credentials", "AWS credentials exposed"),
            (f"https://{target}/server-status", "Apache server-status"),
            (f"https://{target}/debug", "Debug endpoint exposed"),
            (f"https://{target}/actuator/health", "Spring Actuator exposed"),
            (f"https://{target}/graphql", "GraphQL endpoint"),
            (f"https://{target}/.well-known/openid-configuration", "OpenID config"),
        ]

        for url, desc in checks:
            try:
                async with self._session.get(url) as resp:
                    if resp.status == 200:
                        body = await resp.text()
                        if len(body) > 10 and "404" not in body.lower()[:200]:
                            findings["misconfigurations"].append({
                                "url": url, "description": desc,
                                "status": resp.status, "severity": "high",
                            })
                            logger.info(f"[CLOUD] ⚠️ Misconfig: {desc}")
            except Exception:
                pass
