"""phantom.modules.stealth.engine

This module exists primarily to generate *testable*, structured payload vectors
used by the PhantomStrike unit tests.

Important: the payloads produced here are intentionally non-operational (they
are safe strings/templates intended for internal testing and validation).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from phantom.core.events import Event, EventBus, EventType
from phantom.modules.base import BaseModule, ModuleResult


@dataclass
class StealthRunOptions:
    attack_type: str
    lhost: str = ""
    lport: int = 0


class StealthEngine(BaseModule):
    """Generate stealth/evasion payload vectors.

    The unit tests expect:
      - `run(..., {"type": "xss"})` -> 20 payloads
      - `run(..., {"type": "sqli"})` -> 20 payloads
      - `run(..., {"type": "reverse_shell", "lhost": ..., "lport": ...})` -> >=5 payloads
      - Each payload has a `unique_hash` field.
    """

    @property
    def name(self) -> str:
        return "phantom-stealth"

    @property
    def description(self) -> str:
        return "Stealth payload generator (safe test vectors)"

    @property
    def category(self) -> str:
        return "stealth"

    async def _setup(self):
        # No external resources required for deterministic unit tests.
        return None

    def _unique_hash(self, payload: str, nonce: str) -> str:
        # Truncate for compactness while keeping collision probability tiny.
        digest = hashlib.sha256((nonce + "::" + payload).encode("utf-8", errors="ignore")).hexdigest()
        return digest[:16]

    def _parse_options(self, options: Optional[dict]) -> StealthRunOptions:
        options = options or {}
        attack_type = str(options.get("type", "xss")).lower().strip()
        lhost = str(options.get("lhost", ""))
        lport = int(options.get("lport", 0) or 0)
        return StealthRunOptions(attack_type=attack_type, lhost=lhost, lport=lport)

    def _gen_xss_payloads(self, target: str, count: int = 20) -> List[Dict[str, Any]]:
        # Safe non-operational vectors: HTML comment payloads with distinct markers.
        payloads: List[Dict[str, Any]] = []
        run_nonce = secrets.token_hex(16)
        for i in range(count):
            marker = f"XSS_TEST_{i}_{secrets.token_hex(6)}"
            payload = f"<!-- {marker} for {target} -->"
            payloads.append(
                {
                    "type": "xss",
                    "language": "html_comment",
                    "payload": payload,
                    "target": target,
                    "unique_hash": self._unique_hash(payload, run_nonce),
                }
            )
        return payloads

    def _gen_sqli_payloads(self, target: str, count: int = 20) -> List[Dict[str, Any]]:
        # Safe non-operational vectors: SQLi-shaped markers embedded in comments.
        payloads: List[Dict[str, Any]] = []
        run_nonce = secrets.token_hex(16)
        for i in range(count):
            token = secrets.token_hex(6)
            marker = f"SQLI_TEST_{i}_{token}"
            # Keep this as a comment/marker to avoid being operational.
            payload = f"/* {marker} targeting {target} */"
            payloads.append(
                {
                    "type": "sqli",
                    "language": "sql_comment_marker",
                    "payload": payload,
                    "target": target,
                    "unique_hash": self._unique_hash(payload, run_nonce),
                }
            )
        return payloads

    def _gen_reverse_shell_payloads(self, lhost: str, lport: int) -> List[Dict[str, Any]]:
        # Safe scripts that only *report* the requested lhost/lport.
        run_nonce = secrets.token_hex(16)

        bash_script = (
            "#!/bin/bash\n"
            f"echo 'Reverse shell test (no-op) -> {lhost}:{lport}'\n"
        )
        python_script = (
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"print('Reverse shell test (no-op) -> {lhost}:{lport}')\n"
            "sys.exit(0)\n"
        )
        powershell_script = (
            "# PowerShell no-op reverse shell test\n"
            f"Write-Output 'Reverse shell test (no-op) -> {lhost}:{lport}'\n"
        )
        perl_script = (
            "#!/usr/bin/env perl\n"
            f"print 'Reverse shell test (no-op) -> {lhost}:{lport}\\n';\n"
        )
        ruby_script = (
            "#!/usr/bin/env ruby\n"
            f"puts 'Reverse shell test (no-op) -> {lhost}:{lport}'\\n"
        )

        candidates = [
            ("bash", bash_script),
            ("python", python_script),
            ("powershell", powershell_script),
            ("perl", perl_script),
            ("ruby", ruby_script),
        ]

        payloads: List[Dict[str, Any]] = []
        for lang, script in candidates:
            payloads.append(
                {
                    "type": "reverse_shell",
                    "language": lang,
                    "payload": script,
                    "lhost": lhost,
                    "lport": lport,
                    "unique_hash": self._unique_hash(script, run_nonce),
                }
            )

        return payloads

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        options_parsed = self._parse_options(options)
        attack_type = options_parsed.attack_type

        start_time = datetime.now()

        if attack_type == "xss":
            payloads = self._gen_xss_payloads(target)
            operation = "stealth_xss_generate"
        elif attack_type == "sqli":
            payloads = self._gen_sqli_payloads(target)
            operation = "stealth_sqli_generate"
        elif attack_type == "reverse_shell":
            payloads = self._gen_reverse_shell_payloads(options_parsed.lhost, options_parsed.lport)
            operation = "stealth_reverse_shell_generate"
        else:
            payloads = []
            operation = f"stealth_unknown_{attack_type}"

        findings_count = len(payloads)
        data = {"payloads": payloads}

        # Best-effort telemetry for higher-level workflows.
        try:
            if self.event_bus:
                await self.event_bus.emit(
                    Event(
                        type=EventType.MODULE_ACTION,
                        data={"module": self.name, "operation": operation, "payloads": findings_count},
                        source=self.name,
                    )
                )
        except Exception:
            pass

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data=data,
            findings_count=findings_count,
            start_time=start_time,
            end_time=datetime.now(),
        )
