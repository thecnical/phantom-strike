"""
PhantomStrike ENHANCED Master Engine — Real working full-stack offensive framework.
Integrates all modules with dashboard, WebSocket, and real attack capabilities.
"""
from __future__ import annotations
import asyncio
import logging
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.logging import RichHandler

from phantom.core.config import PhantomStrikeConfig, load_config
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom")
console = Console()


class EnhancedPhantomEngine:
    """
    REAL working PhantomStrike engine.
    - Loads enhanced modules
    - Integrates dashboard
    - Real vulnerability detection
    - AI-powered analysis
    """

    def __init__(self, config: Optional[PhantomStrikeConfig] = None):
        self.config = config or load_config()
        self.event_bus = EventBus()
        
        # Use enhanced AI engine
        try:
            from phantom.ai.enhanced_engine import EnhancedPhantomAIEngine
            self.ai_engine = EnhancedPhantomAIEngine(self.config)
        except Exception as e:
            logger.warning(f"Could not load enhanced AI: {e}")
            self.ai_engine = None
            
        self._modules: Dict[str, Any] = {}
        self._start_time: Optional[datetime] = None
        self._session_id: str = ""
        self._is_running = False
        self._results_store: Dict[str, Dict] = {}
        self._dashboard = None

    async def start(self):
        """Initialize and start the engine."""
        self._start_time = datetime.now()
        self._session_id = f"ps_{self._start_time:%Y%m%d_%H%M%S}"

        self._setup_logging()
        self._print_banner()

        # Start event bus
        await self.event_bus.start()

        # Initialize AI
        if self.ai_engine:
            try:
                active_providers = await self.ai_engine.initialize()
                console.print(f"  [bold green]✓[/] AI Engine: {len(active_providers)} providers active")
                if not active_providers:
                    console.print("  [yellow]⚠ AI: No providers configured. Set GROQ_API_KEY or other provider keys.[/]")
            except Exception as e:
                console.print(f"  [yellow]⚠ AI Engine: {e}[/]")

        # Load enhanced modules
        try:
            await self._load_enhanced_modules()
            console.print(f"  [bold green]✓[/] Modules: {len(self._modules)} loaded")
        except Exception as e:
            console.print(f"  [yellow]⚠ Module loader: {e}[/]")
            import traceback
            traceback.print_exc()

        # Emit start event
        await self.event_bus.emit(Event(
            type=EventType.ENGINE_START,
            data={"session_id": self._session_id},
            source="engine",
        ))

        self._is_running = True
        console.print(f"  [bold green]✓[/] Engine started (session: {self._session_id})")
        console.print()

    async def _load_enhanced_modules(self):
        """Load all enhanced offensive modules."""
        modules_to_load = []

        # Network module
        try:
            from phantom.modules.network.engine import NetworkEngine
            modules_to_load.append(NetworkEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load network module: {e}")

        # OSINT module
        try:
            from phantom.modules.osint.engine import OSINTEngine
            modules_to_load.append(OSINTEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load OSINT module: {e}")

        # Enhanced Web module
        try:
            from phantom.modules.web.enhanced_engine import EnhancedWebEngine
            modules_to_load.append(EnhancedWebEngine(self.event_bus))
            logger.info("Loaded ENHANCED Web module with blind SQLi detection")
        except Exception as e:
            logger.warning(f"Could not load enhanced web module: {e}")
            # Fallback to basic
            try:
                from phantom.modules.web.engine import WebEngine
                modules_to_load.append(WebEngine(self.event_bus))
                logger.info("Loaded basic Web module")
            except Exception as e2:
                logger.warning(f"Could not load web module: {e2}")

        # Enhanced Cloud module
        try:
            from phantom.modules.cloud.enhanced_engine import EnhancedCloudEngine
            modules_to_load.append(EnhancedCloudEngine(self.event_bus))
            logger.info("Loaded ENHANCED Cloud module with S3 scanning")
        except Exception as e:
            logger.warning(f"Could not load enhanced cloud module: {e}")

        # Identity module
        try:
            from phantom.modules.identity.engine import IdentityEngine
            modules_to_load.append(IdentityEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load identity module: {e}")

        # Cred module
        try:
            from phantom.modules.cred.engine import CredEngine
            modules_to_load.append(CredEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load cred module: {e}")

        # Stealth module
        try:
            from phantom.modules.stealth.engine import StealthEngine
            modules_to_load.append(StealthEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load stealth module: {e}")

        # Exploit module
        try:
            from phantom.modules.exploit.engine import ExploitEngine
            modules_to_load.append(ExploitEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load exploit module: {e}")

        # C2 module
        try:
            from phantom.modules.c2.engine import C2Engine
            modules_to_load.append(C2Engine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load C2 module: {e}")

        # Post module
        try:
            from phantom.modules.post.engine import PostExploitEngine
            modules_to_load.append(PostExploitEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load post module: {e}")

        # Report module
        try:
            from phantom.modules.report.engine import ReportEngine
            modules_to_load.append(ReportEngine(self.event_bus))
        except Exception as e:
            logger.warning(f"Could not load report module: {e}")

        # Register all modules
        for module in modules_to_load:
            try:
                await module.initialize()
                self._modules[module.name] = module
                logger.info(f"Registered module: {module.name}")
            except Exception as e:
                logger.error(f"Failed to initialize module {module.name}: {e}")

    async def stop(self):
        """Gracefully shutdown."""
        self._is_running = False
        await self.event_bus.emit(Event(
            type=EventType.ENGINE_STOP,
            data={"session_id": self._session_id},
            source="engine",
        ))

        # Cleanup modules
        for name, module in self._modules.items():
            try:
                if hasattr(module, "cleanup"):
                    await module.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up module '{name}': {e}")

        # Shutdown AI
        if self.ai_engine:
            await self.ai_engine.shutdown()

        # Stop event bus
        await self.event_bus.stop()

        duration = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        console.print(f"\n[bold cyan]Session ended. Duration: {duration:.1f}s[/]")

    def register_module(self, module):
        """Register an offensive module."""
        self._modules[module.name] = module
        logger.info(f"Module registered: {module.name}")

    def get_module(self, name: str):
        """Get a loaded module by name."""
        return self._modules.get(name)

    def list_modules(self) -> List[Dict]:
        """List all loaded modules with metadata."""
        return [
            {
                "name": mod.name,
                "description": mod.description,
                "category": mod.category,
                "status": mod.status.value if hasattr(mod, "status") else "unknown",
            }
            for mod in self._modules.values()
        ]

    async def execute_module(self, module_name: str, target: str, options: dict = None) -> Dict:
        """Execute a single module against a target."""
        if module_name not in self._modules:
            return {"error": f"Module '{module_name}' not found", "success": False}

        module = self._modules[module_name]
        try:
            result = await module.run(target, options or {})
            # Store result
            key = f"{module_name}_{target}"
            self._results_store[key] = {
                "module": module_name,
                "target": target,
                "result": result.__dict__ if hasattr(result, "__dict__") else result,
                "timestamp": datetime.now().isoformat(),
            }
            return {
                "success": result.success if hasattr(result, "success") else True,
                "module": module_name,
                "findings_count": result.findings_count if hasattr(result, "findings_count") else 0,
                "data": result.data if hasattr(result, "data") else {},
                "duration": result.duration_seconds if hasattr(result, "duration_seconds") else 0,
            }
        except Exception as e:
            logger.error(f"Module '{module_name}' failed: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "success": False, "module": module_name}

    async def execute_scan(self, target: str, module_names: List[str] = None) -> Dict:
        """Execute scan with specified modules."""
        if not module_names:
            # Default: run recon modules
            module_names = [
                name for name, mod in self._modules.items()
                if hasattr(mod, "category") and mod.category in ("reconnaissance", "vulnerability")
            ]
            if not module_names:
                module_names = list(self._modules.keys())

        console.print(f"[bold yellow]⚡ Scanning target: {target}[/]")
        console.print(f"[dim]   Modules: {', '.join(module_names)}[/]")

        results = {}
        tasks = []
        for mod_name in module_names:
            if mod_name in self._modules:
                module = self._modules[mod_name]
                task = asyncio.create_task(module.run(target))
                tasks.append((mod_name, task))

        for mod_name, task in tasks:
            try:
                result = await task
                results[mod_name] = {
                    "success": result.success if hasattr(result, "success") else True,
                    "findings_count": result.findings_count if hasattr(result, "findings_count") else 0,
                    "data": result.data if hasattr(result, "data") else {},
                    "duration": result.duration_seconds if hasattr(result, "duration_seconds") else 0,
                }
                console.print(
                    f"  [green]✓[/] {mod_name}: "
                    f"{result.findings_count if hasattr(result, 'findings_count') else '?'} findings"
                )
            except Exception as e:
                logger.error(f"Module '{mod_name}' failed: {e}")
                results[mod_name] = {"error": str(e), "success": False}
                console.print(f"  [red]✗[/] {mod_name}: {e}")

        self._results_store[f"scan_{target}"] = results
        return results

    async def execute_full_chain(self, target: str) -> Dict:
        """Execute full 7-phase kill chain."""
        console.print(f"[bold red]🔥 FULL KILL CHAIN on {target}[/]")
        chain_results = {}

        # Phase 1: Reconnaissance
        console.print("\n[cyan]═══ Phase 1: Reconnaissance ═══[/]")
        recon_modules = ["phantom-osint", "phantom-network"]
        for mod_name in recon_modules:
            if mod_name in self._modules:
                try:
                    result = await self._modules[mod_name].run(target)
                    chain_results[mod_name] = result.data if hasattr(result, "data") else {}
                    fc = result.findings_count if hasattr(result, "findings_count") else 0
                    console.print(f"  [green]✓[/] {mod_name}: {fc} findings")
                except Exception as e:
                    console.print(f"  [red]✗[/] {mod_name}: {e}")

        # Phase 2: Vulnerability Discovery
        console.print("\n[cyan]═══ Phase 2: Vulnerability Discovery ═══[/]")
        vuln_modules = ["phantom-web", "phantom-cloud"]
        for mod_name in vuln_modules:
            if mod_name in self._modules:
                try:
                    result = await self._modules[mod_name].run(target)
                    chain_results[mod_name] = result.data if hasattr(result, "data") else {}
                    fc = result.findings_count if hasattr(result, "findings_count") else 0
                    console.print(f"  [green]✓[/] {mod_name}: {fc} findings")

                    # Broadcast critical vulnerabilities to dashboard
                    if hasattr(result, 'data') and result.data:
                        for vuln_type, vulns in result.data.items():
                            if isinstance(vulns, list):
                                for vuln in vulns:
                                    if isinstance(vuln, dict) and vuln.get('severity') in ['critical', 'high']:
                                        try:
                                            from phantom.web.dashboard import dashboard_manager
                                            await dashboard_manager.send_vulnerability(vuln)
                                        except:
                                            pass

                except Exception as e:
                    console.print(f"  [red]✗[/] {mod_name}: {e}")

        # Phase 3: AI Attack Planning
        console.print("\n[cyan]═══ Phase 3: AI Attack Path Planning ═══[/]")
        if self.ai_engine:
            try:
                from phantom.ai.attack_planner import AttackPlanner
                planner = AttackPlanner(self.ai_engine)
                attack_plan = await planner.plan_attack(chain_results)
                chain_results["attack_plan"] = attack_plan
                console.print(f"  [green]✓[/] AI generated attack plan")
            except Exception as e:
                console.print(f"  [yellow]⚠[/] AI planning skipped: {e}")

        # Phase 4: Generate Evasive Payloads
        console.print("\n[cyan]═══ Phase 4: Payload Generation ═══[/]")
        if "phantom-stealth" in self._modules:
            try:
                result = await self._modules["phantom-stealth"].run(target, {"type": "xss"})
                chain_results["stealth_payloads"] = result.data if hasattr(result, "data") else {}
                console.print(f"  [green]✓[/] Polymorphic payloads generated")
            except Exception as e:
                console.print(f"  [yellow]⚠[/] Stealth: {e}")

        # Phase 5: Exploitation
        console.print("\n[cyan]═══ Phase 5: Exploitation ═══[/]")
        if self.config.attack.auto_exploit and "phantom-exploit" in self._modules:
            all_vulns = []
            for mod_data in chain_results.values():
                if isinstance(mod_data, dict):
                    for key in ["sqli", "xss", "lfi", "ssrf", "rce", "blind_sqli", "stored_xss"]:
                        if key in mod_data and isinstance(mod_data[key], list):
                            all_vulns.extend(mod_data[key])

            if all_vulns:
                try:
                    result = await self._modules["phantom-exploit"].run(
                        target, {"vulnerabilities": all_vulns}
                    )
                    chain_results["exploit"] = result.data if hasattr(result, "data") else {}
                    console.print(f"  [green]✓[/] Exploitation complete")
                except Exception as e:
                    console.print(f"  [red]✗[/] Exploit: {e}")
            else:
                console.print("  [dim]No exploitable vulnerabilities found[/]")
        else:
            console.print("  [dim]Auto-exploit disabled (safe_mode)[/]")

        # Phase 6: Post-Exploitation
        console.print("\n[cyan]═══ Phase 6: Post-Exploitation ═══[/]")
        if "phantom-post" in self._modules:
            try:
                result = await self._modules["phantom-post"].run(target, {"operation": "enumerate"})
                chain_results["post_exploit"] = result.data if hasattr(result, "data") else {}
                console.print(f"  [green]✓[/] Post-exploitation enumeration ready")
            except Exception as e:
                console.print(f"  [yellow]⚠[/] Post-exploit: {e}")

        # Phase 7: Report Generation
        console.print("\n[cyan]═══ Phase 7: Report Generation ═══[/]")
        if "phantom-report" in self._modules:
            try:
                result = await self._modules["phantom-report"].run(target, {
                    "results": chain_results,
                    "session_id": self._session_id,
                })
                report_data = result.data if hasattr(result, "data") else {}
                chain_results["report"] = report_data
                console.print(f"  [green]✓[/] Report: {report_data.get('html_path', 'generated')}")
            except Exception as e:
                console.print(f"  [yellow]⚠[/] Report: {e}")

        console.print(f"\n[bold green]✅ Kill chain complete for {target}[/]")
        self._results_store[f"chain_{target}"] = chain_results
        return chain_results

    def get_status(self) -> Dict:
        """Get engine status."""
        ai_status = {}
        if self.ai_engine:
            try:
                ai_status = self.ai_engine.get_status()
            except:
                pass

        return {
            "session_id": self._session_id,
            "running": self._is_running,
            "uptime_seconds": (
                (datetime.now() - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            "modules_loaded": len(self._modules),
            "modules": self.list_modules(),
            "ai_status": ai_status,
            "ai_available": self.ai_engine is not None,
            "event_stats": self.event_bus.get_stats(),
            "results_stored": len(self._results_store),
        }

    def get_results(self) -> Dict:
        """Get all stored results."""
        return self._results_store

    def _setup_logging(self):
        """Configure logging."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=console, rich_tracebacks=True)],
        )

    def _print_banner(self):
        """Print banner."""
        banner = """
[bold red]
  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
[/bold red][bold cyan]                    S T R I K E[/bold cyan]
[dim]         "See Everything. Strike Anywhere. Leave Nothing."[/dim]
[dim]         Enhanced Engine v2.0 | Python {pyver} | {os}[/dim]
""".format(
            pyver=platform.python_version(),
            os=platform.system(),
        )
        console.print(banner)
        console.print("[bold green]  ⚡ Initializing Enhanced PhantomStrike Engine...[/]")
