"""
PhantomStrike C2Agent — Command and Control specialist.

Uses phantom-sliver with fallback to phantom-c2 for implant generation and
C2 infrastructure management, adding implant info to the Knowledge Graph.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.c2")


class C2Agent(BaseAgent):
    """
    Command and Control specialist agent.

    Responsibilities:
    - Sliver C2 implant generation (primary)
    - Fallback to phantom-c2 when Sliver is unavailable
    - C2 listener setup and management
    - Implant deployment to compromised hosts
    - Adds implant and C2 infrastructure info to the Knowledge Graph
    """

    @property
    def name(self) -> str:
        return "C2Agent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are C2Agent, a Command and Control specialist for PhantomStrike. "
            "Your role is to establish and manage C2 infrastructure for the engagement. "
            "Primary workflow: (1) Generate implants using Sliver C2 framework, "
            "(2) Fall back to phantom-c2 module if Sliver is unavailable, "
            "(3) Deploy implants to compromised hosts, "
            "(4) Establish persistent C2 channels for post-exploitation. "
            "Prefer encrypted, resilient C2 channels (HTTPS, DNS) over plaintext. "
            "Document all implants, listeners, and C2 infrastructure in the Knowledge Graph."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute C2 establishment objective.

        1. Build fresh context from KG.
        2. Try phantom-sliver for implant generation.
        3. Fall back to phantom-c2 if Sliver unavailable.
        4. Add implant info to KG.
        5. Return AgentResult with findings.
        """
        start_time = time.time()
        findings: List[Dict[str, Any]] = []
        errors: List[str] = []
        kg_updates: List[Dict[str, Any]] = []
        mitre_techniques: List[str] = []

        target = getattr(objective, "target", None) or (
            self._opplan.target if self._opplan else "unknown"
        )

        # 1. Build fresh context (Req 8.1, 8.2)
        kg_context = self._get_kg_context(target)
        context: Dict[str, Any] = {
            "agent": self.name,
            "objective_id": objective.id,
            "objective_title": objective.title,
            "target": target,
            "phase": str(objective.phase),
            "kg_context": kg_context,
        }

        # 2. Load C2 skills
        skills = self._load_skills("c2")
        context["available_skills"] = [getattr(s, "name", str(s)) for s in skills]

        # 3. Query AI for C2 strategy
        ai_response = self._query_ai(
            context,
            f"Plan C2 infrastructure for target: {target}. "
            "Determine the best implant type and C2 channel for this engagement.",
        )
        context["ai_plan"] = ai_response

        # 4. Try phantom-sliver first (primary C2)
        sliver_result = self._execute_module(
            "phantom-sliver",
            target=target,
            technique="T1071",  # Application Layer Protocol
            operation="generate_implant",
            lhost="0.0.0.0",
            lport=443,
            os="linux",
            arch="amd64",
            format="elf",
        )

        if sliver_result.get("success"):
            implant_path = sliver_result.get("implant_path", "")
            implant_name = sliver_result.get("implant_name", "")
            findings.append({
                "type": "c2_implant",
                "framework": "sliver",
                "implant_path": implant_path,
                "implant_name": implant_name,
                "target": target,
            })
            self._add_implant_to_kg(target, "sliver", implant_name, kg_updates)
            mitre_techniques.append("T1071")
            logger.info("[%s] Sliver implant generated: %s", self.name, implant_name)
        else:
            # 5. Fall back to phantom-c2 (Req 19.2)
            sliver_err = sliver_result.get("error", "phantom-sliver not available")
            logger.info(
                "[%s] Sliver unavailable (%s) — falling back to phantom-c2",
                self.name, sliver_err,
            )

            c2_result = self._execute_module(
                "phantom-c2",
                target=target,
                technique="T1071",
                operation="generate_payload",
            )

            if c2_result.get("success"):
                c2_data = c2_result.get("data", c2_result.get("results", {}))
                payload_path = ""
                payload_type = "unknown"
                if isinstance(c2_data, dict):
                    payload_path = c2_data.get("payload_path", "")
                    payload_type = c2_data.get("payload_type", "unknown")

                findings.append({
                    "type": "c2_implant",
                    "framework": "phantom-c2",
                    "payload_path": payload_path,
                    "payload_type": payload_type,
                    "target": target,
                })
                self._add_implant_to_kg(target, "phantom-c2", payload_type, kg_updates)
                mitre_techniques.append("T1071")
            else:
                err = c2_result.get("error", "phantom-c2 not available")
                logger.warning("[%s] phantom-c2 fallback failed: %s", self.name, err)
                errors.append(f"phantom-c2: {err}")
                errors.append(f"phantom-sliver: {sliver_err}")

        # 6. Set up listener if we have a working C2
        if findings and not errors:
            listener_result = self._execute_module(
                "phantom-c2",
                target=target,
                technique="T1090",  # Proxy
                operation="start_listener",
                port=443,
                protocol="https",
            )
            if listener_result.get("success"):
                findings.append({
                    "type": "c2_listener",
                    "port": 443,
                    "protocol": "https",
                })
                mitre_techniques.append("T1090")

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

    def _add_implant_to_kg(
        self,
        host_ip: str,
        framework: str,
        implant_name: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add implant/C2 info to the KG as a vulnerability-like node."""
        if self._knowledge_graph is None:
            return
        try:
            host_id = self._knowledge_graph.add_host(host_ip)
            vuln_id = self._knowledge_graph.add_vulnerability(
                host_id,
                f"C2 Implant ({framework})",
                severity="critical",
                properties={
                    "framework": framework,
                    "implant_name": implant_name,
                    "type": "c2_implant",
                },
            )
            kg_updates.append({
                "action": "add_c2_implant",
                "data": {
                    "host": host_ip,
                    "framework": framework,
                    "implant_name": implant_name,
                    "node_id": vuln_id,
                },
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_implant failed: %s", self.name, exc)
