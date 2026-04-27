"""
PhantomStrike ENHANCED Cloud Security Module — REAL cloud scanning.
S3 bucket enumeration, Azure Blob scanning, GCP storage, IAM misconfig detection.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse, urlencode

import aiohttp

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.cloud")

# Cloud metadata IPs
AWS_METADATA_IP = "169.254.169.254"
GCP_METADATA_IP = "169.254.169.254"
AZURE_METADATA_IP = "169.254.169.254"

# Common S3 bucket name variations
S3_BUCKET_PATTERNS = [
    "{domain}", "{domain}-backup", "{domain}-backups", "{domain}-data",
    "{domain}-dev", "{domain}-prod", "{domain}-staging", "{domain}-test",
    "{domain}-assets", "{domain}-uploads", "{domain}-files", "{domain}-media",
    "{domain}-logs", "{domain}-archives", "{domain}-storage", "{domain}-s3",
    "{tld}-backup", "{tld}-data", "{tld}-assets", "{tld}-files",
    "backup-{domain}", "data-{domain}", "assets-{domain}", "files-{domain}",
    "{domain}-public", "{domain}-private", "{domain}-shared", "{domain}-temp",
    "{clean_name}", "{clean_name}-backup", "{clean_name}-data",
    "{clean_name}-dev", "{clean_name}-prod", "{clean_name}-staging",
]

# Azure Blob patterns
AZURE_BLOB_PATTERNS = [
    "{domain}", "{domain}backup", "{domain}data", "{domain}assets",
    "{clean_name}", "{clean_name}backup", "{clean_name}data",
]

# GCP Storage patterns
GCP_BUCKET_PATTERNS = [
    "{domain}", "{domain}-backup", "{domain}-data", "{domain}-assets",
    "{clean_name}", "{clean_name}-backup", "{clean_name}-data",
]


class EnhancedCloudEngine(BaseModule):
    """REAL cloud security scanner with actual bucket enumeration."""

    @property
    def name(self) -> str:
        return "phantom-cloud"

    @property
    def description(self) -> str:
        return "Cloud security — S3, Azure Blob, GCP, IAM misconfig, metadata SSRF"

    @property
    def category(self) -> str:
        return "vulnerability"

    async def _setup(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._findings: List[Dict] = []

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run comprehensive cloud security scan."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()

        # Extract domain/TLD from target
        parsed = urlparse(target if target.startswith("http") else f"https://{target}")
        domain = parsed.netloc or target
        domain = domain.replace("www.", "")
        tld = domain.split(".")[-1] if "." in domain else domain
        clean_name = domain.replace(".", "-").replace("_", "-")

        findings = {
            "target": target,
            "domain": domain,
            "s3_buckets": [],
            "azure_blobs": [],
            "gcp_buckets": [],
            "iam_misconfigs": [],
            "metadata_ssrf": [],
            "cloud_front": [],
            "cdn_misconfigs": [],
        }

        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=50,
            enable_cleanup_closed=True,
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )

        try:
            logger.info(f"[CLOUD] Starting cloud scan for {domain}")

            # Phase 1: S3 Bucket Enumeration
            logger.info(f"[CLOUD] Enumerating S3 buckets for {domain}")
            s3_findings = await self._enumerate_s3_buckets(domain, tld, clean_name)
            findings["s3_buckets"].extend(s3_findings)

            # Phase 2: Azure Blob Enumeration
            logger.info(f"[CLOUD] Enumerating Azure Blobs for {domain}")
            azure_findings = await self._enumerate_azure_blobs(domain, clean_name)
            findings["azure_blobs"].extend(azure_findings)

            # Phase 3: GCP Storage Enumeration
            logger.info(f"[CLOUD] Enumerating GCP buckets for {domain}")
            gcp_findings = await self._enumerate_gcp_buckets(domain, clean_name)
            findings["gcp_buckets"].extend(gcp_findings)

            # Phase 4: Metadata SSRF Testing
            logger.info(f"[CLOUD] Testing metadata SSRF on {target}")
            metadata_findings = await self._test_metadata_ssrf(target)
            findings["metadata_ssrf"].extend(metadata_findings)

            # Phase 5: CloudFront/CDN Analysis
            logger.info(f"[CLOUD] Analyzing CDN configuration for {domain}")
            cdn_findings = await self._analyze_cdn(domain, target)
            findings["cloud_front"].extend(cdn_findings)

            # Phase 6: IAM Misconfiguration Checks
            iam_findings = await self._check_iam_misconfigs(target)
            findings["iam_misconfigs"].extend(iam_findings)

        except Exception as e:
            logger.error(f"[CLOUD] Scan error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self._session.close()

        total_findings = (
            len(findings["s3_buckets"]) + len(findings["azure_blobs"]) +
            len(findings["gcp_buckets"]) + len(findings["metadata_ssrf"]) +
            len(findings["iam_misconfigs"])
        )

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name,
            operation="cloud_scan",
            success=True,
            data=findings,
            findings_count=total_findings,
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def _enumerate_s3_buckets(self, domain: str, tld: str, clean_name: str) -> List[Dict]:
        """Enumerate S3 buckets with real HTTP requests."""
        findings = []
        tested_buckets = set()

        # Generate bucket name variations
        bucket_names = set()
        for pattern in S3_BUCKET_PATTERNS:
            name = pattern.format(
                domain=domain,
                tld=tld,
                clean_name=clean_name,
            )
            bucket_names.add(name)
            # Also add without hyphens
            bucket_names.add(name.replace("-", ""))

        # Common prefixes/suffixes
        prefixes = ["", "prod-", "dev-", "staging-", "test-", "prod", "dev", "staging", "test"]
        for prefix in prefixes:
            for base in [domain, clean_name, tld]:
                bucket_names.add(f"{prefix}{base}")
                bucket_names.add(f"{base}{prefix}")

        # Remove invalid names
        bucket_names = {b for b in bucket_names if b and len(b) >= 3 and len(b) <= 63}

        logger.info(f"[CLOUD] Testing {len(bucket_names)} S3 bucket variations")

        async def check_bucket(bucket_name: str):
            if bucket_name in tested_buckets:
                return
            tested_buckets.add(bucket_name)

            # Check multiple S3 endpoints
            endpoints = [
                f"https://{bucket_name}.s3.amazonaws.com",
                f"https://s3.amazonaws.com/{bucket_name}",
                f"https://{bucket_name}.s3-website-us-east-1.amazonaws.com",
            ]

            for url in endpoints:
                try:
                    async with self._session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=10),
                        ssl=False
                    ) as resp:
                        body = await resp.text()

                        # Check for public bucket indicators
                        if resp.status == 200:
                            # List bucket contents
                            if "<ListBucketResult" in body or "<Contents>" in body:
                                findings.append({
                                    "type": "open_s3_bucket",
                                    "bucket": bucket_name,
                                    "url": url,
                                    "status": "listable",
                                    "evidence": "Bucket contents listable",
                                    "severity": "critical",
                                })
                                await self._emit_vuln(findings[-1])
                                logger.info(f"[CLOUD] 🔴 OPEN S3 BUCKET (Listable): {bucket_name}")
                                return

                            # Static website hosting
                            findings.append({
                                "type": "open_s3_bucket",
                                "bucket": bucket_name,
                                "url": url,
                                "status": "accessible",
                                "evidence": f"HTTP 200 - Bucket accessible ({len(body)} bytes)",
                                "severity": "high",
                            })
                            await self._emit_vuln(findings[-1])
                            logger.info(f"[CLOUD] 🔴 OPEN S3 BUCKET (200 OK): {bucket_name}")
                            return

                        elif resp.status == 403:
                            # Bucket exists but is private - still useful info
                            if "AccessDenied" in body:
                                findings.append({
                                    "type": "s3_bucket_exists",
                                    "bucket": bucket_name,
                                    "url": url,
                                    "status": "private",
                                    "evidence": "Bucket exists but access denied",
                                    "severity": "info",
                                })
                                logger.info(f"[CLOUD] ℹ️ S3 Bucket exists (private): {bucket_name}")
                                return

                        elif resp.status == 404:
                            # Bucket doesn't exist
                            pass

                except Exception as e:
                    logger.debug(f"[CLOUD] S3 check error for {bucket_name}: {e}")

        # Check buckets concurrently
        semaphore = asyncio.Semaphore(50)

        async def limited_check(bucket: str):
            async with semaphore:
                await check_bucket(bucket)

        await asyncio.gather(*[limited_check(b) for b in bucket_names])
        return findings

    async def _enumerate_azure_blobs(self, domain: str, clean_name: str) -> List[Dict]:
        """Enumerate Azure Blob storage accounts."""
        findings = []
        tested_accounts = set()

        account_names = set()
        for pattern in AZURE_BLOB_PATTERNS:
            name = pattern.format(domain=domain, clean_name=clean_name)
            # Azure storage names: 3-24 chars, lowercase alphanumeric
            name = name.lower().replace("-", "").replace(".", "")[:24]
            if len(name) >= 3:
                account_names.add(name)

        # Add common variations
        for base in [domain.replace(".", "").replace("-", "")[:24], clean_name.replace("-", "")[:24]]:
            account_names.add(base)
            account_names.add(f"{base}storage"[:24])
            account_names.add(f"{base}data"[:24])

        async def check_azure_account(account: str):
            if account in tested_accounts or len(account) < 3:
                return
            tested_accounts.add(account)

            # Azure Blob endpoints
            endpoints = [
                f"https://{account}.blob.core.windows.net",
                f"https://{account}.blob.core.windows.net/?comp=list",
            ]

            for url in endpoints:
                try:
                    async with self._session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=10),
                        ssl=False
                    ) as resp:
                        body = await resp.text()

                        if resp.status == 200 and "<EnumerationResults" in body:
                            findings.append({
                                "type": "open_azure_blob",
                                "account": account,
                                "url": url,
                                "status": "listable",
                                "evidence": "Blob containers listable",
                                "severity": "critical",
                            })
                            await self._emit_vuln(findings[-1])
                            logger.info(f"[CLOUD] 🔴 OPEN AZURE BLOB: {account}")
                            return

                        elif "ResourceNotFound" not in body and "InvalidUri" not in body:
                            # Account exists
                            if resp.status in [403, 401]:
                                logger.info(f"[CLOUD] ℹ️ Azure Blob exists (private): {account}")

                except Exception as e:
                    logger.debug(f"[CLOUD] Azure check error: {e}")

        semaphore = asyncio.Semaphore(30)

        async def limited_check(account: str):
            async with semaphore:
                await check_azure_account(account)

        await asyncio.gather(*[limited_check(a) for a in account_names])
        return findings

    async def _enumerate_gcp_buckets(self, domain: str, clean_name: str) -> List[Dict]:
        """Enumerate Google Cloud Storage buckets."""
        findings = []
        tested_buckets = set()

        bucket_names = set()
        for pattern in GCP_BUCKET_PATTERNS:
            name = pattern.format(domain=domain, clean_name=clean_name)
            bucket_names.add(name)

        # GCP bucket naming rules
        bucket_names = {b.lower() for b in bucket_names if 3 <= len(b) <= 63}

        async def check_gcp_bucket(bucket: str):
            if bucket in tested_buckets:
                return
            tested_buckets.add(bucket)

            # GCP Storage endpoints
            endpoints = [
                f"https://storage.googleapis.com/{bucket}",
                f"https://{bucket}.storage.googleapis.com",
            ]

            for url in endpoints:
                try:
                    async with self._session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=10),
                        ssl=False
                    ) as resp:
                        body = await resp.text()

                        if resp.status == 200:
                            if "<ListBucketResult" in body or "<Contents>" in body:
                                findings.append({
                                    "type": "open_gcp_bucket",
                                    "bucket": bucket,
                                    "url": url,
                                    "status": "listable",
                                    "evidence": "Bucket contents listable",
                                    "severity": "critical",
                                })
                                await self._emit_vuln(findings[-1])
                                logger.info(f"[CLOUD] 🔴 OPEN GCP BUCKET: {bucket}")
                                return

                        elif resp.status == 403 and "access" in body.lower():
                            # Private bucket
                            logger.info(f"[CLOUD] ℹ️ GCP Bucket exists (private): {bucket}")

                except Exception as e:
                    logger.debug(f"[CLOUD] GCP check error: {e}")

        semaphore = asyncio.Semaphore(30)

        async def limited_check(bucket: str):
            async with semaphore:
                await check_gcp_bucket(bucket)

        await asyncio.gather(*[limited_check(b) for b in bucket_names])
        return findings

    async def _test_metadata_ssrf(self, target: str) -> List[Dict]:
        """Test for cloud metadata SSRF vulnerabilities."""
        findings = []

        # SSRF payloads targeting cloud metadata services
        metadata_payloads = [
            # AWS
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/latest/user-data",
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            # GCP
            "http://169.254.169.254/computeMetadata/v1/",
            "http://metadata.google.internal/computeMetadata/v1/",
            # Azure
            "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
            "http://169.254.169.254/metadata/identity/oauth2/token",
        ]

        # Common SSRF injection points
        ssrf_params = ["url", "uri", "path", "file", "document", "src", "dest", "callback", "redirect"]

        for payload in metadata_payloads:
            for param in ssrf_params:
                try:
                    # Try GET with parameter
                    test_url = f"{target}?{param}={payload}"

                    async with self._session.get(
                        test_url,
                        timeout=aiohttp.ClientTimeout(total=10),
                        allow_redirects=False,
                        ssl=False
                    ) as resp:
                        body = await resp.text()

                        # Check for cloud metadata indicators
                        aws_indicators = ["ami-id", "instance-id", "instance-type", "local-hostname", "availability-zone"]
                        gcp_indicators = ["project-id", "numeric-project-id", "zone", "cluster-name"]
                        azure_indicators = ["compute", "network", "subscriptionId", "resourceGroupName"]

                        found_indicators = []
                        for indicator in aws_indicators + gcp_indicators + azure_indicators:
                            if indicator in body:
                                found_indicators.append(indicator)

                        if found_indicators:
                            cloud_type = "AWS" if any(i in aws_indicators for i in found_indicators) else \
                                         "GCP" if any(i in gcp_indicators for i in found_indicators) else "Azure"

                            findings.append({
                                "type": "metadata_ssrf",
                                "cloud": cloud_type,
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "evidence": f"Cloud metadata accessed: {', '.join(found_indicators[:5])}",
                                "severity": "critical",
                            })
                            await self._emit_vuln(findings[-1])
                            logger.info(f"[CLOUD] 🔴 METADATA SSRF ({cloud_type}): {target}")
                            return findings

                except Exception as e:
                    logger.debug(f"[CLOUD] SSRF test error: {e}")

        return findings

    async def _analyze_cdn(self, domain: str, target: str) -> List[Dict]:
        """Analyze CDN configuration for misconfigurations."""
        findings = []

        try:
            # Check for CloudFront
            async with self._session.head(target, ssl=False, allow_redirects=True) as resp:
                headers = dict(resp.headers)

                # CloudFront checks
                if "x-amz-cf-id" in headers:
                    findings.append({
                        "type": "cloudfront_detected",
                        "provider": "AWS CloudFront",
                        "cf_id": headers.get("x-amz-cf-id", "")[:20],
                        "severity": "info",
                    })

                # Check for S3 origin exposure
                if "x-amz-request-id" in headers:
                    findings.append({
                        "type": "s3_origin_detected",
                        "provider": "AWS S3",
                        "request_id": headers.get("x-amz-request-id", "")[:20],
                        "evidence": "Direct S3 access possible",
                        "severity": "medium",
                    })

                # Azure CDN
                if "x-azure-ref" in headers or "x-msedge-ref" in headers:
                    findings.append({
                        "type": "azure_cdn_detected",
                        "provider": "Azure CDN",
                        "severity": "info",
                    })

                # Cloudflare
                if "cf-ray" in headers:
                    findings.append({
                        "type": "cloudflare_detected",
                        "provider": "Cloudflare",
                        "ray_id": headers.get("cf-ray", ""),
                        "severity": "info",
                    })

                # Fastly
                if "x-served-by" in headers and "fastly" in headers.get("x-served-by", "").lower():
                    findings.append({
                        "type": "fastly_detected",
                        "provider": "Fastly",
                        "severity": "info",
                    })

        except Exception as e:
            logger.debug(f"[CLOUD] CDN analysis error: {e}")

        return findings

    async def _check_iam_misconfigs(self, target: str) -> List[Dict]:
        """Check for IAM/Auth misconfigurations."""
        findings = []

        # Common IAM misconfig endpoints
        iam_endpoints = [
            "/.aws/credentials", "/aws/credentials",
            "/.env", "/env", "/.env.local",
            "/config.json", "/secrets.json",
            "/api-keys", "/apikeys",
            "/.git/config", "/.git/HEAD",
            "/terraform.tfstate", "/.terraform/terraform.tfstate",
        ]

        for endpoint in iam_endpoints:
            try:
                url = f"{target.rstrip('/')}{endpoint}"
                async with self._session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False
                ) as resp:
                    if resp.status == 200:
                        body = await resp.text()

                        # Check for credentials in response
                        if any(x in body for x in ["aws_access_key_id", "aws_secret_access_key", "AKIA"]):
                            findings.append({
                                "type": "aws_credentials_exposed",
                                "url": url,
                                "evidence": "AWS credentials found in exposed file",
                                "severity": "critical",
                            })
                            await self._emit_vuln(findings[-1])
                            logger.info(f"[CLOUD] 🔴 AWS CREDENTIALS EXPOSED: {url}")

                        elif "secret" in body.lower() or "password" in body.lower() or "api_key" in body.lower():
                            findings.append({
                                "type": "secrets_exposed",
                                "url": url,
                                "evidence": "Potential secrets in exposed file",
                                "severity": "critical",
                            })
                            await self._emit_vuln(findings[-1])
                            logger.info(f"[CLOUD] 🔴 SECRETS EXPOSED: {url}")

            except Exception as e:
                logger.debug(f"[CLOUD] IAM check error: {e}")

        return findings

    async def _emit_vuln(self, vuln: dict):
        """Emit vulnerability event."""
        await self.event_bus.emit(Event(
            type=EventType.VULN_FOUND,
            data=vuln,
            source=self.name,
            severity=vuln.get("severity", "medium"),
        ))
