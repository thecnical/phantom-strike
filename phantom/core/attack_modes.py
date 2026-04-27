"""
PhantomStrike Attack Modes System
Provides full-killchain autonomous and stealth evasive attack modes
"""

import asyncio
import random
import time
from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AttackMode(Enum):
    """Available attack modes."""
    FULL_KILLCHAIN = "full-killchain"  # Autonomous complete engagement
    STEALTH = "stealth"  # Evasive, slow, avoid detection
    AGGRESSIVE = "aggressive"  # Fast, loud, internal pentest
    RECON = "recon"  # Information gathering only
    WEB = "web"  # Web application focused
    C2 = "c2"  # Command & Control operations


@dataclass
class AttackConfig:
    """Configuration for attack modes."""
    mode: AttackMode
    target: str
    auto_exploit: bool = False
    auto_post_exploit: bool = False
    auto_report: bool = True
    delay_jitter: bool = False  # Random delays between requests
    request_delay: float = 0.0  # Base delay between requests
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


class AttackModeEngine:
    """Engine to execute attacks in different modes."""
    
    def __init__(self, engine):
        self.engine = engine
        self.active_mode: Optional[AttackMode] = None
        self.attack_config: Optional[AttackConfig] = None
        self._stop_event = asyncio.Event()
        self._progress_callbacks: List[Callable] = []
        
    def configure(self, config: AttackConfig):
        """Configure attack mode."""
        self.attack_config = config
        self.active_mode = config.mode
        
        # Apply mode-specific settings
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
            config.max_threads = 20  # Low and slow
            
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
        """Execute attack based on configured mode."""
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
        
    async def _execute_full_killchain(self, results: Dict) -> Dict:
        """Execute autonomous full kill chain."""
        config = self.attack_config
        target = config.target
        
        # Phase 1: Reconnaissance
        await self._notify_progress(10, "Phase 1/6: Reconnaissance - OSINT & Network")
        osint_result = await self.engine.execute_module("phantom-osint", target)
        network_result = await self.engine.execute_module("phantom-network", target)
        results["phases"]["reconnaissance"] = {
            "osint_findings": len(osint_result.findings),
            "network_findings": len(network_result.findings),
        }
        results["findings"].extend(osint_result.findings)
        results["findings"].extend(network_result.findings)
        
        # Phase 2: Web Assessment
        await self._notify_progress(25, "Phase 2/6: Web Vulnerability Assessment")
        if self._should_stop():
            return results
        web_result = await self.engine.execute_module("phantom-web", target)
        results["phases"]["web_assessment"] = {
            "findings": len(web_result.findings),
        }
        results["findings"].extend(web_result.findings)
        
        # Extract vulnerabilities
        for finding in web_result.findings:
            if finding.get("severity") in ["high", "critical"]:
                results["vulnerabilities"].append(finding)
                
        # Phase 3: Cloud Assessment
        await self._notify_progress(40, "Phase 3/6: Cloud Security Assessment")
        if self._should_stop():
            return results
        cloud_result = await self.engine.execute_module("phantom-cloud", target)
        results["phases"]["cloud_assessment"] = {
            "findings": len(cloud_result.findings),
        }
        results["findings"].extend(cloud_result.findings)
        
        # Phase 4: Auto-Exploitation (DANGEROUS)
        if config.auto_exploit and results["vulnerabilities"]:
            await self._notify_progress(60, "Phase 4/6: Auto-Exploitation (DANGEROUS)")
            if self._should_stop():
                return results
            exploit_results = await self._auto_exploit(results["vulnerabilities"])
            results["phases"]["exploitation"] = exploit_results
            results["exploited"].extend(exploit_results.get("successful", []))
            
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
            results["phases"]["reporting"] = {
                "generated": report_result.success,
            }
            
        await self._notify_progress(100, "Kill chain complete!")
        return results
        
    async def _execute_stealth(self, results: Dict) -> Dict:
        """Execute stealth evasive attack."""
        config = self.attack_config
        target = config.target
        
        await self._notify_progress(0, "Stealth mode: Initializing evasive techniques")
        
        # Apply jitter delays
        await self._apply_jitter()
        
        # Stealth recon - slow and distributed
        await self._notify_progress(20, "Stealth: Passive reconnaissance")
        osint_result = await self.engine.execute_module("phantom-osint", target)
        await self._apply_jitter()
        
        # Very slow network scan with evasion
        await self._notify_progress(40, "Stealth: Slow network scan (evasive)")
        # Use single thread, random delays
        network_result = await self.engine.execute_module("phantom-network", target)
        await self._apply_jitter()
        
        # Web scan with throttling
        await self._notify_progress(70, "Stealth: Web scan with request throttling")
        web_result = await self.engine.execute_module("phantom-web", target)
        
        results["phases"]["stealth_recon"] = {
            "osint": len(osint_result.findings),
            "network": len(network_result.findings),
            "web": len(web_result.findings),
            "evasion_techniques_used": config.evasion_techniques,
        }
        results["findings"].extend(osint_result.findings)
        results["findings"].extend(network_result.findings)
        results["findings"].extend(web_result.findings)
        
        await self._notify_progress(100, "Stealth reconnaissance complete")
        return results
        
    async def _execute_aggressive(self, results: Dict) -> Dict:
        """Execute aggressive fast attack."""
        config = self.attack_config
        target = config.target
        
        await self._notify_progress(10, "AGGRESSIVE MODE: Fast parallel execution")
        
        # Run all modules in parallel with max threads
        tasks = [
            self.engine.execute_module("phantom-osint", target),
            self.engine.execute_module("phantom-network", target),
            self.engine.execute_module("phantom-web", target),
            self.engine.execute_module("phantom-cloud", target),
        ]
        
        await self._notify_progress(30, "Running all modules in parallel...")
        module_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (module, result) in enumerate(zip(["osint", "network", "web", "cloud"], module_results)):
            if isinstance(result, Exception):
                logger.error(f"[AGGRESSIVE] {module} failed: {result}")
                results["phases"][module] = {"error": str(result)}
            else:
                results["phases"][module] = {"findings": len(result.findings)}
                results["findings"].extend(result.findings)
                
        await self._notify_progress(100, "Aggressive scan complete")
        return results
        
    async def _auto_exploit(self, vulnerabilities: List[Dict]) -> Dict:
        """Auto-exploit vulnerabilities (DANGEROUS - Full Write)."""
        config = self.attack_config
        results = {
            "attempted": [],
            "successful": [],
            "failed": [],
            "commands_executed": [],
        }
        
        for vuln in vulnerabilities:
            vuln_type = vuln.get("type", "").lower()
            vuln_url = vuln.get("url", "")
            
            logger.warning(f"[EXPLOIT] Attempting exploitation of {vuln_type} at {vuln_url}")
            
            # SQL Injection - Full write exploitation
            if "sql" in vuln_type:
                exploit_result = await self._exploit_sql_injection(vuln)
                if exploit_result.get("success"):
                    results["successful"].append({
                        "type": "sql_injection",
                        "target": vuln_url,
                        "data_extracted": exploit_result.get("data", []),
                        "severity": "critical",
                    })
                    results["commands_executed"].append(f"SQLi exploit on {vuln_url}")
                    
            # Remote Code Execution - Full command execution
            elif "rce" in vuln_type or "command" in vuln_type:
                exploit_result = await self._exploit_rce(vuln)
                if exploit_result.get("success"):
                    results["successful"].append({
                        "type": "rce",
                        "target": vuln_url,
                        "shell_access": True,
                        "severity": "critical",
                    })
                    results["commands_executed"].append(f"RCE exploit on {vuln_url}")
                    
            # File Upload - Web shell deployment
            elif "upload" in vuln_type:
                exploit_result = await self._exploit_file_upload(vuln)
                if exploit_result.get("success"):
                    results["successful"].append({
                        "type": "file_upload",
                        "target": vuln_url,
                        "webshell_deployed": True,
                        "severity": "critical",
                    })
                    
            # LFI/RFI - File read/write
            elif "lfi" in vuln_type or "rfi" in vuln_type:
                exploit_result = await self._exploit_lfi(vuln)
                if exploit_result.get("success"):
                    results["successful"].append({
                        "type": "lfi",
                        "target": vuln_url,
                        "files_accessed": exploit_result.get("files", []),
                        "severity": "high",
                    })
                    
        return results
        
    async def _exploit_sql_injection(self, vuln: Dict) -> Dict:
        """Exploit SQL Injection for data extraction."""
        # DANGEROUS: This attempts to extract database data
        return {"success": False, "reason": "Requires manual confirmation"}
        
    async def _exploit_rce(self, vuln: Dict) -> Dict:
        """Exploit Remote Code Execution."""
        # DANGEROUS: This attempts command execution
        return {"success": False, "reason": "Requires manual confirmation"}
        
    async def _exploit_file_upload(self, vuln: Dict) -> Dict:
        """Exploit file upload for web shell."""
        # DANGEROUS: This deploys web shells
        return {"success": False, "reason": "Requires manual confirmation"}
        
    async def _exploit_lfi(self, vuln: Dict) -> Dict:
        """Exploit Local File Inclusion."""
        # DANGEROUS: This reads sensitive files
        return {"success": False, "reason": "Requires manual confirmation"}
        
    async def _auto_post_exploit(self, exploited: List[Dict]) -> Dict:
        """Post-exploitation and lateral movement."""
        return {
            "privilege_escalation_attempted": False,
            "lateral_movement": [],
            "persistence_established": False,
            "data_exfiltrated": [],
        }
        
    async def _apply_jitter(self):
        """Apply random delay for evasion."""
        if self.attack_config and self.attack_config.delay_jitter:
            delay = random.uniform(1.0, 5.0)
            await asyncio.sleep(delay)
            
    async def _notify_progress(self, percent: int, message: str):
        """Notify progress callbacks."""
        logger.info(f"[PROGRESS] {percent}% - {message}")
        for callback in self._progress_callbacks:
            try:
                await callback(percent, message)
            except:
                pass
                
    def _should_stop(self) -> bool:
        """Check if attack should stop."""
        return self._stop_event.is_set()
        
    def stop(self):
        """Stop the attack."""
        self._stop_event.set()
        
    def on_progress(self, callback: Callable):
        """Register progress callback."""
        self._progress_callbacks.append(callback)
