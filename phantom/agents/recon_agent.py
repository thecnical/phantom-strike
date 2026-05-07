"""
PhantomStrike ReconAgent — passive and active reconnaissance specialist.

Uses phantom-osint and phantom-network modules to discover hosts, subdomains,
and network topology, then adds findings to the Knowledge Graph.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.recon")


class ReconAgent(BaseAgent):
    """
    Reconnaissance specialist agent.

    Responsibilities:
    - Passive OSINT gathering (subdomains, emails, ASN info)
    - Active network discovery (ping sweeps, traceroute)
    - DNS enumeration
    - Adds discovered hosts to the Knowledge Graph
    """

    @property
    def name(self) -> str:
        return "ReconAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are ReconAgent, a reconnaissance specialist for PhantomStrike. "
            "Your role is to perform passive and active reconnaissance against the target. "
            "Use OSINT techniques to discover subdomains, email addresses, ASN information, "
            "and network topology. Perform DNS enumeration and host discovery. "
            "Prioritize stealth — prefer passive techniques before active ones. "
            "Document all discovered hosts and network assets for subsequent agents."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute reconnaissance objective.

        1. Build fresh context from KG + OPPLAN state.
        2. Load recon skills.
        3. Execute phantom-osint and phantom-network modules.
        4. Add discovered hosts to KG.
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
        context: Dict[str, Any] = {
            "agent": self.name,
            "objective_id": objective.id,
            "objective_title": objective.title,
            "target": target,
            "phase": str(objective.phase),
            "kg_context": self._get_kg_context(target),
        }

        # 2. Load recon skills
        skills = self._load_skills("recon")
        context["available_skills"] = [
            getattr(s, "name", str(s)) for s in skills
        ]

        # 3. Query AI for action plan
        ai_response = self._query_ai(
            context,
            f"Plan reconnaissance for target: {target}. "
            "Identify the best OSINT and network discovery techniques to use.",
        )
        context["ai_plan"] = ai_response

        # 4. Execute phantom-osint module
        osint_result = self._execute_module(
            "phantom-osint",
            target=target,
            technique="T1595",  # Active Scanning
        )
        if osint_result.get("success"):
            osint_findings = osint_result.get("data", osint_result.get("results", {}))
            if isinstance(osint_findings, dict):
                # Extract subdomains
                for subdomain in osint_findings.get("subdomains", []):
                    findings.append({"type": "subdomain", "value": subdomain, "source": "osint"})
                # Extract hosts
                for host in osint_findings.get("hosts", []):
                    findings.append({"type": "host", "ip": host, "source": "osint"})
                    _id = self._add_host_to_kg(host, kg_updates)
                # Extract emails
                for email in osint_findings.get("emails", []):
                    findings.append({"type": "email", "value": email, "source": "osint"})
            mitre_techniques.append("T1595")
        else:
            err = osint_result.get("error", "phantom-osint not available")
            logger.warning("[%s] phantom-osint: %s", self.name, err)
            errors.append(f"phantom-osint: {err}")

        # 5. Execute phantom-network module for host discovery
        network_result = self._execute_module(
            "phantom-network",
            target=target,
            technique="T1046",  # Network Service Discovery
        )
        if network_result.get("success"):
            net_findings = network_result.get("data", network_result.get("results", {}))
            if isinstance(net_findings, dict):
                for host in net_findings.get("live_hosts", []):
                    findings.append({"type": "host", "ip": host, "source": "network_scan"})
                    self._add_host_to_kg(host, kg_updates)
                for route in net_findings.get("routes", []):
                    findings.append({"type": "route", "value": route, "source": "network_scan"})
            mitre_techniques.append("T1046")
        else:
            err = network_result.get("error", "phantom-network not available")
            logger.warning("[%s] phantom-network: %s", self.name, err)
            errors.append(f"phantom-network: {err}")

        # 6. Add target itself to KG if not already present
        if target and target != "unknown":
            self._add_host_to_kg(target, kg_updates)

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

    def _add_host_to_kg(self, ip: str, kg_updates: List[Dict[str, Any]]) -> int:
        """Add a host to the KG and record the update. Returns node ID or -1."""
        if self._knowledge_graph is None:
            return -1
        try:
            node_id = self._knowledge_graph.add_host(ip)
            kg_updates.append({"action": "add_host", "data": {"ip": ip, "node_id": node_id}})
            return node_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_host failed for %s: %s", self.name, ip, exc)
            return -1
