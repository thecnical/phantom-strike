"""
PhantomStrike CLI — Full interactive command-line interface.
Beautiful Rich-powered terminal UI with ALL commands working.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.syntax import Syntax

from phantom.core.engine import PhantomEngine
from phantom.core.config import load_config, AttackProfile

console = Console()

HELP_TEXT = {
    "scan": {
        "usage": "scan <target> [modules...]",
        "description": "Run vulnerability scan on a target domain or IP.",
        "examples": [
            "scan example.com",
            "scan example.com phantom-web phantom-cloud",
            "scan 192.168.1.0/24",
        ],
        "flags": {
            "--modules": "Comma-separated module names to run",
            "--threads": "Override thread count (default: 100)",
        },
    },
    "recon": {
        "usage": "recon <target>",
        "description": "Full OSINT + network reconnaissance on a target.",
        "examples": ["recon example.com", "recon 10.0.0.1"],
        "flags": {},
    },
    "attack": {
        "usage": "attack <target>",
        "description": "Execute the full 7-phase kill chain: Recon → Vuln → AI Plan → Payload → Exploit → Post → Report.",
        "examples": ["attack example.com"],
        "flags": {
            "--auto-exploit": "Enable auto-exploitation (disabled in safe mode)",
        },
    },
    "module": {
        "usage": "module <name> <target> [options_json]",
        "description": "Run a specific module with custom options.",
        "examples": [
            'module phantom-stealth example.com {"type":"xss"}',
            'module phantom-cred example.com {"type":"spray"}',
            'module phantom-c2 0.0.0.0 {"operation":"generate_agent","lhost":"10.0.0.1","lport":4444}',
        ],
        "flags": {},
    },
    "ai": {
        "usage": "ai <subcommand>",
        "description": "AI engine commands — query, status, plan attacks.",
        "examples": [
            "ai status",
            "ai ask How to exploit JWT none algorithm?",
            "ai plan example.com",
        ],
        "flags": {},
    },
    "c2": {
        "usage": "c2 <subcommand>",
        "description": "Command & Control — manage agents, send commands, generate payloads.",
        "examples": [
            "c2 status",
            "c2 agents",
            "c2 generate 10.0.0.1 4444",
            "c2 cmd agent_abc123 whoami",
        ],
        "flags": {},
    },
    "report": {
        "usage": "report <target>",
        "description": "Generate a professional pentest report from stored results.",
        "examples": ["report example.com"],
        "flags": {},
    },
    "stealth": {
        "usage": "stealth <type> [count]",
        "description": "Generate polymorphic payloads — XSS, SQLi, or reverse shells.",
        "examples": [
            "stealth xss 20",
            "stealth sqli 10",
            "stealth reverse_shell 10.0.0.1 4444",
        ],
        "flags": {},
    },
    "results": {
        "usage": "results [target]",
        "description": "Show all stored scan results.",
        "examples": ["results", "results example.com"],
        "flags": {},
    },
}


class PhantomStrikeCLI:
    """Interactive CLI for PhantomStrike — ALL commands working."""

    def __init__(self):
        self.config = load_config()
        self.engine = PhantomEngine(self.config)

    async def run(self):
        """Main CLI loop."""
        await self.engine.start()
        self._show_status_panel()

        while True:
            try:
                cmd = Prompt.ask(
                    "\n[bold cyan]phantom[/bold cyan][bold red]>[/bold red]",
                    default="help",
                )
                await self._handle_command(cmd.strip())
            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit[/yellow]")
            except EOFError:
                break

    async def _handle_command(self, cmd: str):
        """Route commands to handlers."""
        parts = cmd.split()
        if not parts:
            return

        command = parts[0].lower()
        args = parts[1:]

        handlers = {
            "help": self._cmd_help,
            "scan": self._cmd_scan,
            "recon": self._cmd_recon,
            "attack": self._cmd_attack,
            "module": self._cmd_module,
            "ai": self._cmd_ai,
            "c2": self._cmd_c2,
            "stealth": self._cmd_stealth,
            "report": self._cmd_report,
            "results": self._cmd_results,
            "browser": self._cmd_browser,
            "status": self._cmd_status,
            "config": self._cmd_config,
            "modules": self._cmd_modules,
            "clear": self._cmd_clear,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
        }

        handler = handlers.get(command)
        if handler:
            try:
                await handler(args)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        else:
            console.print(f"[red]Unknown command: {command}. Type 'help'.[/red]")

    # ─── Help ─────────────────────────────────────────────────

    async def _cmd_help(self, args: list):
        """Show help — general or for a specific command."""
        if args and args[0] in HELP_TEXT:
            # Detailed help for specific command
            info = HELP_TEXT[args[0]]
            console.print(Panel(
                f"[bold]Usage:[/] {info['usage']}\n\n"
                f"[bold]Description:[/] {info['description']}\n\n"
                f"[bold]Examples:[/]\n" + "\n".join(f"  [cyan]phantom> {ex}[/]" for ex in info["examples"]) +
                ("\n\n[bold]Flags:[/]\n" + "\n".join(f"  [green]{k}[/] — {v}" for k, v in info["flags"].items()) if info["flags"] else ""),
                title=f"📖 Help: {args[0]}",
                border_style="cyan",
            ))
            return

        table = Table(
            title="⚡ PhantomStrike Commands",
            title_style="bold cyan",
            border_style="cyan",
            show_lines=True,
        )
        table.add_column("Command", style="bold green", width=28)
        table.add_column("Description", style="white")
        table.add_column("Example", style="dim cyan")

        cmds = [
            ("scan <target>", "Quick vulnerability scan", "scan example.com"),
            ("recon <target>", "Full OSINT + network reconnaissance", "recon example.com"),
            ("attack <target>", "Full 7-phase kill chain 🔥", "attack example.com"),
            ("module <name> <target>", "Run a specific module", "module phantom-web target.com"),
            ("ai status", "Show AI provider status", "ai status"),
            ("ai ask <query>", "Ask AI anything", "ai ask explain JWT forgery"),
            ("ai plan <target>", "AI attack planning", "ai plan example.com"),
            ("c2 status", "C2 server status", "c2 status"),
            ("c2 agents", "List active agents", "c2 agents"),
            ("c2 generate <lhost> <lport>", "Generate C2 agent payload", "c2 generate 10.0.0.1 4444"),
            ("c2 cmd <agent_id> <command>", "Send command to agent", "c2 cmd agent_abc whoami"),
            ("stealth xss|sqli [count]", "Generate polymorphic payloads", "stealth xss 20"),
            ("stealth reverse_shell <ip> <port>", "Generate reverse shells", "stealth reverse_shell 10.0.0.1 4444"),
            ("report <target>", "Generate pentest report", "report example.com"),
            ("results [target]", "Show stored results", "results"),
            ("modules", "List all loaded modules", "modules"),
            ("status", "Engine status", "status"),
            ("config", "Show configuration", "config"),
            ("help <command>", "Detailed help for a command", "help scan"),
            ("clear", "Clear screen", "clear"),
            ("exit", "Exit PhantomStrike", "exit"),
        ]
        for cmd, desc, ex in cmds:
            table.add_row(cmd, desc, ex)

        console.print(table)
        console.print("[dim]Type 'help <command>' for detailed help on any command.[/dim]")

    # ─── Scan ─────────────────────────────────────────────────

    async def _cmd_scan(self, args: list):
        """Quick vulnerability scan."""
        if not args:
            console.print("[red]Usage: scan <target> [module1 module2 ...][/red]")
            return
        target = args[0]
        modules = args[1:] if len(args) > 1 else None

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Scanning {target}...", total=100)
            progress.update(task, advance=10)
            results = await self.engine.execute_scan(target, modules)
            progress.update(task, completed=100)

        # Display results summary
        total_findings = sum(
            r.get("findings_count", 0) for r in results.values()
            if isinstance(r, dict) and "error" not in r
        )
        console.print(f"\n[bold green]✅ Scan complete.[/] {len(results)} modules | {total_findings} findings")

    # ─── Recon ────────────────────────────────────────────────

    async def _cmd_recon(self, args: list):
        """Full OSINT + network recon."""
        if not args:
            console.print("[red]Usage: recon <target>[/red]")
            return
        target = args[0]
        console.print(f"[bold cyan]🔍 Full reconnaissance on {target}...[/bold cyan]")
        results = await self.engine.execute_scan(target, ["phantom-osint", "phantom-network"])
        for mod_name, result in results.items():
            if isinstance(result, dict) and "data" in result:
                console.print(f"  [green]✓[/] {mod_name}: {result.get('findings_count', 0)} findings")

    # ─── Attack (Full Kill Chain) ─────────────────────────────

    async def _cmd_attack(self, args: list):
        """Full 7-phase kill chain."""
        if not args:
            console.print("[red]Usage: attack <target>[/red]")
            return
        target = args[0]
        if not Confirm.ask(f"[bold red]⚠ Execute FULL KILL CHAIN on {target}?[/]"):
            return
        await self.engine.execute_full_chain(target)

    # ─── Module (Run Specific) ────────────────────────────────

    async def _cmd_module(self, args: list):
        """Run a specific module with options."""
        if len(args) < 2:
            console.print("[red]Usage: module <module_name> <target> [options_json][/red]")
            return
        mod_name = args[0]
        target = args[1]
        options = {}
        if len(args) > 2:
            try:
                options = json.loads(" ".join(args[2:]))
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON options[/red]")
                return

        console.print(f"[yellow]Running {mod_name} on {target}...[/yellow]")
        result = await self.engine.execute_module(mod_name, target, options)
        if result.get("success"):
            console.print(f"[green]✅ {mod_name}: {result.get('findings_count', 0)} findings[/green]")
            if result.get("data"):
                console.print(Syntax(
                    json.dumps(result["data"], indent=2, default=str)[:2000],
                    "json", theme="monokai",
                ))
        else:
            console.print(f"[red]❌ {result.get('error', 'Unknown error')}[/red]")

    # ─── AI Commands ──────────────────────────────────────────

    async def _cmd_ai(self, args: list):
        """AI engine commands."""
        if not args:
            console.print("[red]Usage: ai status | ai ask <query> | ai plan <target>[/red]")
            return

        subcmd = args[0]

        if subcmd == "status":
            status = self.engine.ai_engine.get_status()
            table = Table(title="🧠 AI Providers", border_style="cyan")
            table.add_column("Provider", style="bold")
            table.add_column("Model")
            table.add_column("Active", justify="center")
            table.add_column("Requests", justify="right")
            table.add_column("Status")

            for name, info in status.items():
                active = "✅" if info["active"] else "❌"
                blocked = "🔴 Blocked" if info["blocked"] else "🟢 Ready"
                table.add_row(
                    name, info["model"], active,
                    f"{info['requests_today']}/{info['daily_limit']}", blocked,
                )
            console.print(table)

        elif subcmd == "ask" and len(args) > 1:
            query = " ".join(args[1:])
            console.print("[dim]🧠 Querying AI...[/dim]")
            try:
                response = await self.engine.ai_engine.query(query)
                console.print(Panel(
                    response.content,
                    title=f"🧠 {response.provider} ({response.model})",
                    subtitle=f"{response.latency_ms:.0f}ms | {response.tokens_used} tokens",
                    border_style="green",
                ))
            except Exception as e:
                console.print(f"[red]AI Error: {e}[/red]")

        elif subcmd == "plan" and len(args) > 1:
            target = args[1]
            console.print(f"[dim]🧠 AI planning attack for {target}...[/dim]")
            try:
                from phantom.ai.attack_planner import AttackPlanner
                planner = AttackPlanner(self.engine.ai_engine)
                plan = await planner.plan_attack({"target": target})
                console.print(Panel(
                    json.dumps(plan, indent=2, default=str)[:3000],
                    title="🎯 AI Attack Plan",
                    border_style="red",
                ))
            except Exception as e:
                console.print(f"[red]AI Plan Error: {e}[/red]")
        else:
            console.print("[red]Usage: ai status | ai ask <query> | ai plan <target>[/red]")

    # ─── C2 Commands ──────────────────────────────────────────

    async def _cmd_c2(self, args: list):
        """C2 command & control."""
        if not args:
            console.print("[red]Usage: c2 status | agents | generate <lhost> <lport> | cmd <agent_id> <command>[/red]")
            return

        subcmd = args[0]
        c2 = self.engine.get_module("phantom-c2")
        if not c2:
            console.print("[red]C2 module not loaded[/red]")
            return

        if subcmd == "status":
            result = await c2.run("", {"operation": "status"})
            data = result.data if hasattr(result, "data") else {}
            console.print(Panel(
                f"Active Agents: {data.get('active_agents', 0)}\n"
                f"Total Agents: {data.get('total_agents', 0)}\n"
                f"Encryption: {data.get('encryption', 'AES-256-GCM')}\n"
                f"Channels: {', '.join(data.get('channels', []))}",
                title="📡 C2 Status",
                border_style="magenta",
            ))

        elif subcmd == "agents":
            result = await c2.run("", {"operation": "list_agents"})
            data = result.data if hasattr(result, "data") else {}
            agents = data.get("agents", {})
            if not agents:
                console.print("[dim]No agents registered[/dim]")
                return
            table = Table(title="📡 C2 Agents", border_style="magenta")
            table.add_column("ID", style="bold")
            table.add_column("Hostname")
            table.add_column("IP")
            table.add_column("User")
            table.add_column("Status")
            table.add_column("Last Seen")
            for aid, info in agents.items():
                table.add_row(aid, info["hostname"], info["ip"],
                              info["user"], info["status"], info["last_seen"])
            console.print(table)

        elif subcmd == "generate" and len(args) >= 3:
            lhost, lport = args[1], int(args[2])
            result = await c2.run("", {
                "operation": "generate_agent", "lhost": lhost, "lport": lport,
            })
            data = result.data if hasattr(result, "data") else {}
            payload = data.get("agent_payload", {})
            console.print(Panel(
                payload.get("python", "")[:2000],
                title=f"🐍 Python Agent ({lhost}:{lport})",
                border_style="green",
            ))
            console.print(Panel(
                payload.get("bash", "")[:1000],
                title=f"🐚 Bash Agent ({lhost}:{lport})",
                border_style="yellow",
            ))

        elif subcmd == "cmd" and len(args) >= 3:
            agent_id, command = args[1], " ".join(args[2:])
            cmd_obj = c2._queue_command(agent_id, command)
            console.print(f"[green]✅ Command queued: {cmd_obj.command_id}[/green]")

    # ─── Stealth ──────────────────────────────────────────────

    async def _cmd_stealth(self, args: list):
        """Generate polymorphic payloads."""
        if not args:
            console.print("[red]Usage: stealth xss|sqli [count] | stealth reverse_shell <ip> <port>[/red]")
            return

        payload_type = args[0]
        stealth = self.engine.get_module("phantom-stealth")
        if not stealth:
            console.print("[red]Stealth module not loaded[/red]")
            return

        if payload_type == "reverse_shell" and len(args) >= 3:
            result = await stealth.run("", {
                "type": "reverse_shell", "lhost": args[1], "lport": int(args[2]),
            })
        else:
            count = int(args[1]) if len(args) > 1 else 10
            result = await stealth.run("", {"type": payload_type, "count": count})

        data = result.data if hasattr(result, "data") else {}
        payloads = data.get("payloads", [])
        table = Table(title=f"👻 {payload_type.upper()} Payloads ({len(payloads)})", border_style="red")
        table.add_column("#", style="bold", width=4)
        table.add_column("Payload", style="cyan", overflow="fold")
        table.add_column("Encoding", style="dim")
        for p in payloads[:15]:
            lang = p.get("language", p.get("encoding", ""))
            table.add_row(str(p.get("id", "")), str(p.get("payload", ""))[:100], lang)
        console.print(table)

    # ─── Report ───────────────────────────────────────────────

    async def _cmd_report(self, args: list):
        """Generate pentest report."""
        if not args:
            console.print("[red]Usage: report <target>[/red]")
            return
        target = args[0]
        report_mod = self.engine.get_module("phantom-report")
        if not report_mod:
            console.print("[red]Report module not loaded[/red]")
            return

        results = self.engine.get_results()
        result = await report_mod.run(target, {
            "results": results,
            "session_id": self.engine._session_id,
        })
        data = result.data if hasattr(result, "data") else {}
        console.print(f"[bold green]📊 Report generated![/]")
        console.print(f"  HTML: {data.get('html_path', 'N/A')}")
        console.print(f"  JSON: {data.get('json_path', 'N/A')}")

    # ─── Results ──────────────────────────────────────────────

    async def _cmd_results(self, args: list):
        """Show stored results."""
        results = self.engine.get_results()
        if not results:
            console.print("[dim]No results stored yet. Run a scan first.[/dim]")
            return
        tree = Tree("📊 Scan Results")
        for key, data in results.items():
            branch = tree.add(f"[bold]{key}[/]")
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict) and "findings_count" in v:
                        branch.add(f"{k}: {v['findings_count']} findings")
                    elif isinstance(v, dict) and "error" in v:
                        branch.add(f"[red]{k}: {v['error']}[/]")
        console.print(tree)

    # ─── Browser ──────────────────────────────────────────────

    async def _cmd_browser(self, args: list):
        """Browser-based commands."""
        if not args:
            console.print("[red]Usage: browser crawl <url> | browser xss <url>[/red]")
            return
        console.print(f"[bold magenta]🎭 Browser: {' '.join(args)}[/bold magenta]")
        # Browser commands delegated to Playwright engine
        try:
            from phantom.core.browser import PhantomBrowser
            browser = PhantomBrowser(self.config)
            await browser.initialize()
            if args[0] == "crawl" and len(args) > 1:
                result = await browser.crawl_page(args[1])
                console.print(f"[green]Crawled: {len(result.get('links', []))} links found[/green]")
            elif args[0] == "xss" and len(args) > 1:
                result = await browser.test_xss(args[1])
                console.print(f"[green]XSS test: {result}[/green]")
            await browser.shutdown()
        except Exception as e:
            console.print(f"[yellow]Browser: {e}. Run 'playwright install chromium' first.[/yellow]")

    # ─── Status, Config, Modules ──────────────────────────────

    async def _cmd_status(self, args: list):
        """Engine status."""
        status = self.engine.get_status()
        table = Table(title="⚡ Engine Status", border_style="green")
        table.add_column("Component", style="bold")
        table.add_column("Value")
        table.add_row("Session", status["session_id"])
        table.add_row("Running", "✅ Yes" if status["running"] else "❌ No")
        table.add_row("Uptime", f"{status['uptime_seconds']:.1f}s")
        table.add_row("Modules", str(status["modules_loaded"]))
        table.add_row("Results Stored", str(status["results_stored"]))
        console.print(table)

    async def _cmd_config(self, args: list):
        """Show config."""
        console.print(Panel(
            f"Profile: {self.config.attack.profile.value}\n"
            f"AI Primary: {self.config.ai_primary_provider.value}\n"
            f"AI Providers: {len(self.config.ai_providers)} configured\n"
            f"Scan Threads: {self.config.threading.max_scan_threads}\n"
            f"Playwright: {'Enabled' if self.config.playwright.enabled else 'Disabled'}\n"
            f"Safe Mode: {'ON' if self.config.attack.safe_mode else 'OFF'}\n"
            f"Auto Exploit: {'ON' if self.config.attack.auto_exploit else 'OFF'}\n"
            f"Data Dir: {self.config.data_dir}",
            title="⚙️ Configuration",
            border_style="blue",
        ))

    async def _cmd_modules(self, args: list):
        """List all loaded modules."""
        modules = self.engine.list_modules()
        table = Table(title="📦 Loaded Modules", border_style="magenta")
        table.add_column("#", width=3)
        table.add_column("Name", style="bold green")
        table.add_column("Category")
        table.add_column("Description")
        table.add_column("Status")
        for i, mod in enumerate(modules, 1):
            table.add_row(
                str(i), mod["name"], mod["category"],
                mod["description"][:50], f"🟢 {mod['status']}",
            )
        console.print(table)
        console.print(f"[dim]Total: {len(modules)} modules loaded[/dim]")

    async def _cmd_clear(self, args: list):
        """Clear screen."""
        console.clear()

    async def _cmd_exit(self, args: list):
        """Exit."""
        console.print("[bold cyan]Shutting down PhantomStrike...[/bold cyan]")
        await self.engine.stop()
        sys.exit(0)

    # ─── UI ───────────────────────────────────────────────────

    def _show_status_panel(self):
        """Show initial status panel."""
        ai_count = len([
            p for p in self.config.ai_providers.values()
            if p.enabled and p.api_key
        ])
        modules = self.engine.list_modules()
        panel = Panel(
            f"[green]✓[/] AI Providers: {ai_count} configured (Groq #1)\n"
            f"[green]✓[/] Modules: {len(modules)} loaded\n"
            f"[green]✓[/] Threads: {self.config.threading.max_scan_threads} scan threads\n"
            f"[green]✓[/] Profile: {self.config.attack.profile.value}\n"
            f"[green]✓[/] Safe Mode: {'ON' if self.config.attack.safe_mode else 'OFF'}\n\n"
            f"[dim]Type 'help' for all commands | 'help <cmd>' for details[/dim]",
            title="[bold green]⚡ PhantomStrike Ready[/bold green]",
            border_style="green",
        )
        console.print(panel)
