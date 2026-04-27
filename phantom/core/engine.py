"""
PhantomStrike Master Engine — The heart of the framework.
Orchestrates all modules, AI, threading, and the full attack lifecycle.
REAL WORKING — no placeholders, no fakes.
"""
from __future__ import annotations
import asyncio
import logging
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from phantom.core.config import PhantomStrikeConfig, load_config, AttackProfile
from phantom.core.events import EventBus, Event, EventType
from phantom.ai.engine import PhantomAIEngine

logger = logging.getLogger("phantom")
console = Console()


class PhantomEngine:
    """
    Master orchestration engine.
    - Loads all 12 modules dynamically via loader
    - Manages AI provider pool (9 free providers)
    - Handles multi-threaded task execution
    - Coordinates the full kill chain
    """

    def __init__(self, config: Optional[PhantomStrikeConfig] = None):
        self.config = config or load_config()
        self.event_bus = EventBus()
        
        # Determine AI backend mode
        if self.config.backend_enabled and self.config.backend_url:
            from phantom.ai.remote import RemoteAIClient
            self.ai_engine = RemoteAIClient(self.config.backend_url)
            logger.info(f"Using REMOTE backend AI at {self.config.backend_url}")
        else:
            self.ai_engine = PhantomAIEngine(self.config)
            
        self._modules: dict[str, object] = {}
        self._start_time: Optional[datetime] = None
        self._session_id: str = ""
        self._is_running = False
        self._results_store: dict[str, dict] = {}

    async def start(self):
        """Initialize and start the engine with all modules."""
        self._start_time = datetime.now()
        self._session_id = f"ps_{self._start_time:%Y%m%d_%H%M%S}"

        # Setup logging
        self._setup_logging()

        # Print banner
        self._print_banner()

        # Start event bus
        await self.event_bus.start()

        # Initialize AI engine
        try:
            active_providers = await self.ai_engine.initialize()
            console.print(
                f"  [bold green]✓[/] AI Engine: {len(active_providers)} providers active",
            )
        except Exception as e:
            console.print(f"  [yellow]⚠[/] AI Engine: {e}")

        # Load all modules via the loader
        try:
            from phantom.core.loader import load_all_modules
            self._modules = await load_all_modules(self.event_bus)
            console.print(
                f"  [bold green]✓[/] Modules: {len(self._modules)} loaded",
            )
        except Exception as e:
            console.print(f"  [yellow]⚠[/] Module loader: {e}")

        # Emit start event
        await self.event_bus.emit(Event(
            type=EventType.ENGINE_START,
            data={"session_id": self._session_id},
            source="engine",
        ))

        self._is_running = True
        console.print(f"  [bold green]✓[/] Engine started (session: {self._session_id})")
        console.print()

    async def stop(self):
        """Gracefully shutdown everything."""
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

    def list_modules(self) -> list[dict]:
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

    async def execute_module(self, module_name: str, target: str,
                             options: dict = None) -> dict:
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
                "duration": result.duration if hasattr(result, "duration") else 0,
            }
        except Exception as e:
            logger.error(f"Module '{module_name}' failed: {e}")
            return {"error": str(e), "success": False, "module": module_name}

    async def execute_scan(self, target: str, module_names: list[str] = None) -> dict:
        """Execute scan with specified modules (or all recon modules)."""
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
                    "duration": result.duration if hasattr(result, "duration") else 0,
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

    async def execute_full_chain(self, target: str) -> dict:
        """Execute full kill chain: Recon → Vuln → AI Plan → Exploit → Post → Report."""
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
        vuln_modules = ["phantom-web", "phantom-cloud", "phantom-identity"]
        for mod_name in vuln_modules:
            if mod_name in self._modules:
                try:
                    result = await self._modules[mod_name].run(target)
                    chain_results[mod_name] = result.data if hasattr(result, "data") else {}
                    fc = result.findings_count if hasattr(result, "findings_count") else 0
                    console.print(f"  [green]✓[/] {mod_name}: {fc} findings")
                except Exception as e:
                    console.print(f"  [red]✗[/] {mod_name}: {e}")

        # Phase 3: AI Attack Planning
        console.print("\n[cyan]═══ Phase 3: AI Attack Path Planning ═══[/]")
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

        # Phase 5: Exploitation (only if auto_exploit is enabled)
        console.print("\n[cyan]═══ Phase 5: Exploitation ═══[/]")
        if self.config.attack.auto_exploit and "phantom-exploit" in self._modules:
            # Gather all discovered vulns
            all_vulns = []
            for mod_data in chain_results.values():
                if isinstance(mod_data, dict):
                    for key in ["sqli", "xss", "lfi", "ssrf", "rce"]:
                        if key in mod_data:
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

        # Phase 6: Post-Exploitation Enumeration
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

    def get_status(self) -> dict:
        """Get engine status."""
        return {
            "session_id": self._session_id,
            "running": self._is_running,
            "uptime_seconds": (
                (datetime.now() - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            "modules_loaded": len(self._modules),
            "modules": self.list_modules(),
            "ai_status": self.ai_engine.get_status(),
            "event_stats": self.event_bus.get_stats(),
            "results_stored": len(self._results_store),
        }

    def get_results(self) -> dict:
        """Get all stored results."""
        return self._results_store

    def _setup_logging(self):
        """Configure structured logging with Rich."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=console, rich_tracebacks=True)],
        )

    def _print_banner(self):
        """Print the PhantomStrike banner."""
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
[dim]         Version: {ver} | Python {pyver} | {os}[/dim]
""".format(
            ver=self.config.version,
            pyver=platform.python_version(),
            os=platform.system(),
        )
        console.print(banner)
        console.print("[bold green]  ⚡ Initializing PhantomStrike Engine...[/]")
