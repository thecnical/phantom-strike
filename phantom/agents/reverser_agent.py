"""
PhantomStrike ReverserAgent — binary analysis and reverse engineering specialist.

Uses the phantom-reverser module to analyze binaries, find ROP gadgets,
and disassemble code, adding binary analysis findings to the Knowledge Graph.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.reverser")


class ReverserAgent(BaseAgent):
    """
    Binary analysis and reverse engineering specialist agent.

    Responsibilities:
    - Static binary analysis (file type, imports, exports, strings)
    - ROP gadget discovery for exploit development
    - Disassembly and code analysis
    - Vulnerability identification in binaries
    - Adds binary analysis findings to the Knowledge Graph
    """

    @property
    def name(self) -> str:
        return "ReverserAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are ReverserAgent, a binary analysis and reverse engineering specialist "
            "for PhantomStrike. "
            "Your role is to analyze binaries found on target systems to identify "
            "vulnerabilities, understand functionality, and support exploit development. "
            "Techniques include: static analysis using file, strings, and objdump; "
            "ROP gadget discovery for return-oriented programming exploits; "
            "disassembly using radare2 or objdump; "
            "and identification of dangerous functions (strcpy, gets, system, etc.). "
            "Use the phantom-reverser module for all binary analysis operations. "
            "Document all findings including imports, exports, interesting strings, "
            "and potential vulnerability indicators."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute binary analysis objective.

        1. Build fresh context from KG.
        2. Execute phantom-reverser module.
        3. Add binary analysis findings to KG.
        4. Return AgentResult with findings.
        """
        start_time = time.time()
        findings: List[Dict[str, Any]] = []
        errors: List[str] = []
        kg_updates: List[Dict[str, Any]] = []
        mitre_techniques: List[str] = []

        target = getattr(objective, "target", None) or (
            self._opplan.target if self._opplan else "unknown"
        )

        # Extract binary path from objective description or metadata
        binary_path = getattr(objective, "binary_path", None)
        if binary_path is None:
            # Try to extract from objective description
            desc = getattr(objective, "description", "")
            if "binary:" in desc:
                binary_path = desc.split("binary:")[-1].strip().split()[0]

        # 1. Build fresh context (Req 8.1, 8.2)
        kg_context = self._get_kg_context(target)
        context: Dict[str, Any] = {
            "agent": self.name,
            "objective_id": objective.id,
            "objective_title": objective.title,
            "target": target,
            "binary_path": binary_path,
            "phase": str(objective.phase),
            "kg_context": kg_context,
        }

        # 2. Load reverser skills (use exploit phase as closest match)
        skills = self._load_skills("exploit")
        context["available_skills"] = [getattr(s, "name", str(s)) for s in skills]

        # 3. Query AI for analysis strategy
        ai_response = self._query_ai(
            context,
            f"Plan binary analysis for target: {target}. "
            f"Binary path: {binary_path or 'unknown'}. "
            "Determine the best static analysis and reverse engineering approach.",
        )
        context["ai_plan"] = ai_response

        # 4. Execute phantom-reverser module — binary analysis
        analyze_result = self._execute_module(
            "phantom-reverser",
            target=target,
            technique="T1059",  # Command and Scripting Interpreter (analysis context)
            operation="analyze_binary",
            binary_path=binary_path or "",
        )

        if analyze_result.get("success"):
            analyze_data = analyze_result.get("data", analyze_result.get("results", {}))
            if isinstance(analyze_data, dict):
                # File type and metadata
                file_type = analyze_data.get("file_type", "")
                if file_type:
                    findings.append({
                        "type": "binary_metadata",
                        "file_type": file_type,
                        "binary_path": binary_path,
                        "architecture": analyze_data.get("architecture", ""),
                        "bits": analyze_data.get("bits", 0),
                    })

                # Imports
                for imp in analyze_data.get("imports", []):
                    findings.append({
                        "type": "binary_import",
                        "function": imp,
                        "binary_path": binary_path,
                        "is_dangerous": self._is_dangerous_function(imp),
                    })

                # Exports
                for exp in analyze_data.get("exports", []):
                    findings.append({
                        "type": "binary_export",
                        "function": exp,
                        "binary_path": binary_path,
                    })

                # Interesting strings
                for string in analyze_data.get("interesting_strings", []):
                    findings.append({
                        "type": "binary_string",
                        "value": string,
                        "binary_path": binary_path,
                    })

                # Potential vulnerabilities
                for vuln in analyze_data.get("potential_vulns", []):
                    findings.append({
                        "type": "binary_vulnerability",
                        "description": vuln,
                        "binary_path": binary_path,
                    })
                    self._add_binary_vuln_to_kg(target, vuln, binary_path or "", kg_updates)

                mitre_techniques.append("T1059")
        else:
            err = analyze_result.get("error", "phantom-reverser not available")
            logger.warning("[%s] phantom-reverser analyze: %s", self.name, err)
            errors.append(f"phantom-reverser analyze: {err}")

        # 5. Execute phantom-reverser module — ROP gadget discovery
        rop_result = self._execute_module(
            "phantom-reverser",
            target=target,
            technique="T1203",  # Exploitation for Client Execution
            operation="find_rop_gadgets",
            binary_path=binary_path or "",
        )

        if rop_result.get("success"):
            rop_data = rop_result.get("data", rop_result.get("results", {}))
            if isinstance(rop_data, dict):
                gadgets = rop_data.get("gadgets", [])
                if gadgets:
                    findings.append({
                        "type": "rop_gadgets",
                        "count": len(gadgets),
                        "binary_path": binary_path,
                        "sample_gadgets": gadgets[:5],  # First 5 as sample
                    })
                    mitre_techniques.append("T1203")
        else:
            err = rop_result.get("error", "phantom-reverser ROP not available")
            logger.debug("[%s] phantom-reverser ROP: %s", self.name, err)

        # 6. Execute phantom-reverser module — disassembly
        disasm_result = self._execute_module(
            "phantom-reverser",
            target=target,
            technique="T1059",
            operation="disassemble",
            binary_path=binary_path or "",
        )

        if disasm_result.get("success"):
            disasm_data = disasm_result.get("data", disasm_result.get("results", {}))
            if isinstance(disasm_data, dict):
                disasm_output = disasm_data.get("disassembly", "")
                if disasm_output:
                    findings.append({
                        "type": "disassembly",
                        "binary_path": binary_path,
                        "output_preview": disasm_output[:500],  # First 500 chars
                    })

        duration = time.time() - start_time
        success = len(findings) > 0 or (not errors)

        logger.info(
            "[%s] Completed objective %s: %d findings, %d errors in %.1fs",
            self.name, objective.id, len(findings), len(errors), duration,
        )

        return AgentResult(
            success=success,
            agent_name=self.name,
            objective_id=objective.id,
            findings=findings,
            errors=errors,
            kg_updates=kg_updates,
            mitre_techniques_used=mitre_techniques,
            duration_seconds=duration,
            raw_output=ai_response,
        )

    @staticmethod
    def _is_dangerous_function(func_name: str) -> bool:
        """Check if a function name is commonly associated with vulnerabilities."""
        dangerous = {
            "strcpy", "strcat", "sprintf", "gets", "scanf",
            "memcpy", "memmove", "strncpy", "strncat", "snprintf",
            "system", "popen", "exec", "execve", "execvp",
            "printf", "fprintf", "vprintf",  # format string
        }
        return func_name.lower().rstrip("@plt") in dangerous

    def _add_binary_vuln_to_kg(
        self,
        host_ip: str,
        vuln_description: str,
        binary_path: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add a binary vulnerability finding to the KG."""
        if self._knowledge_graph is None:
            return
        try:
            host_id = self._knowledge_graph.add_host(host_ip)
            vuln_id = self._knowledge_graph.add_vulnerability(
                host_id,
                f"Binary Vulnerability: {vuln_description[:50]}",
                url=binary_path,
                severity="high",
                properties={"source": "binary_analysis", "binary": binary_path},
            )
            kg_updates.append({
                "action": "add_vulnerability",
                "data": {
                    "host": host_ip,
                    "vuln_type": "binary_vulnerability",
                    "description": vuln_description,
                    "binary_path": binary_path,
                    "vuln_id": vuln_id,
                },
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_binary_vuln failed: %s", self.name, exc)
