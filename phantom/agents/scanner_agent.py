"""
PhantomStrike ScannerAgent — port and service scanning specialist.

Performs port scanning and service enumeration against discovered hosts,
adding services and vulnerabilities to the Knowledge Graph.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.scanner")


class ScannerAgent(BaseAgent):
    """
    Port and service scanning specialist agent.

    Responsibilities:
    - TCP/UDP port scanning
    - Service version detection
    - OS fingerprinting
    - Basic vulnerability identification from service banners
    - Adds services and vulnerabilities to the Knowledge Graph
    """

    @property
    def name(self) -> str:
        return "ScannerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are ScannerAgent, a port and service scanning specialist for PhantomStrike. "
            "Your role is to enumerate open ports, identify running services and their versions, "
            "and perform OS fingerprinting on discovered hosts. "
            "Use nmap-style scanning techniques to build a comprehensive picture of the attack surface. "
            "Identify potentially vulnerable services based on version information. "
            "Document all open ports, service banners, and version information for the exploit agents."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute port/service scanning objective.

        1. Build fresh context from KG hosts.
        2. Execute phantom-network module for port scanning.
        3. Add services and vulnerabilities to KG.
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

        # 1. Build fresh context (Req 8.1, 8.2)
        kg_context = self._get_kg_context(target)
        context: Dict[str, Any] = {
            "agent": self.name,
            "objective_id": objective.id,
            "objective_title": objective.title,
            "target": target,
            "phase": str(objective.phase),
            "kg_context": kg_context,
            "known_hosts": [h.get("label") for h in kg_context.get("hosts", [])],
        }

        # 2. Load scan skills
        skills = self._load_skills("scan")
        context["available_skills"] = [getattr(s, "name", str(s)) for s in skills]

        # 3. Query AI for scan strategy
        ai_response = self._query_ai(
            context,
            f"Plan port and service scanning for target: {target}. "
            "Determine the optimal scan strategy based on known hosts.",
        )
        context["ai_plan"] = ai_response

        # 4. Execute phantom-network for port scanning
        scan_result = self._execute_module(
            "phantom-network",
            target=target,
            technique="T1046",  # Network Service Discovery
            scan_type="port_scan",
        )

        if scan_result.get("success"):
            scan_data = scan_result.get("data", scan_result.get("results", {}))
            if isinstance(scan_data, dict):
                # Process open ports and services
                for port_info in scan_data.get("open_ports", []):
                    port = port_info.get("port")
                    service = port_info.get("service", "unknown")
                    version = port_info.get("version", "")
                    host_ip = port_info.get("host", target)

                    findings.append({
                        "type": "open_port",
                        "host": host_ip,
                        "port": port,
                        "service": service,
                        "version": version,
                    })

                    # Add service to KG
                    self._add_service_to_kg(host_ip, port, service, version, kg_updates)

                    # Flag potentially vulnerable services
                    if version and self._is_potentially_vulnerable(service, version):
                        findings.append({
                            "type": "potential_vulnerability",
                            "host": host_ip,
                            "port": port,
                            "service": service,
                            "version": version,
                            "reason": "outdated_version",
                        })
                        self._add_vuln_to_kg(host_ip, f"Outdated {service}", kg_updates)

            mitre_techniques.append("T1046")
        else:
            err = scan_result.get("error", "phantom-network not available")
            logger.warning("[%s] phantom-network scan: %s", self.name, err)
            errors.append(f"phantom-network: {err}")

        # 5. Try sandbox-based nmap if available
        if self._sandbox is not None:
            try:
                nmap_result = self._sandbox.run_nmap(target, flags="-sV -sC --open")
                if isinstance(nmap_result, dict) and nmap_result.get("success"):
                    findings.append({
                        "type": "nmap_output",
                        "host": target,
                        "output": nmap_result.get("stdout", ""),
                    })
                    mitre_techniques.append("T1595.001")
            except Exception as exc:  # noqa: BLE001
                logger.debug("[%s] Sandbox nmap failed: %s", self.name, exc)

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

    def _add_service_to_kg(
        self,
        host_ip: str,
        port: Any,
        service: str,
        version: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add a service node to the KG linked to its host."""
        if self._knowledge_graph is None:
            return
        try:
            from phantom.db.knowledge_graph import EdgeType, NodeType

            host_id = self._knowledge_graph.add_host(host_ip)
            svc_label = f"{service}/{port}@{host_ip}"
            props = {"port": port, "service": service, "version": version, "host_ip": host_ip}
            svc_id = self._knowledge_graph._insert_node(NodeType.SERVICE, svc_label, props)
            self._knowledge_graph.link(host_id, svc_id, EdgeType.HAS_SERVICE)
            kg_updates.append({
                "action": "add_service",
                "data": {"host": host_ip, "port": port, "service": service, "version": version},
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_service failed: %s", self.name, exc)

    def _add_vuln_to_kg(
        self,
        host_ip: str,
        vuln_type: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add a vulnerability to the KG for a host."""
        if self._knowledge_graph is None:
            return
        try:
            host_id = self._knowledge_graph.add_host(host_ip)
            vuln_id = self._knowledge_graph.add_vulnerability(
                host_id, vuln_type, severity="medium"
            )
            kg_updates.append({
                "action": "add_vulnerability",
                "data": {"host": host_ip, "vuln_type": vuln_type, "vuln_id": vuln_id},
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_vulnerability failed: %s", self.name, exc)

    @staticmethod
    def _is_potentially_vulnerable(service: str, version: str) -> bool:
        """Heuristic check for obviously outdated service versions."""
        outdated_patterns = [
            ("apache", "2.2"),
            ("apache", "2.0"),
            ("nginx", "1.0"),
            ("nginx", "1.2"),
            ("openssh", "5."),
            ("openssh", "6."),
            ("vsftpd", "2."),
            ("proftpd", "1.2"),
            ("iis", "6.0"),
            ("iis", "5."),
        ]
        svc_lower = service.lower()
        ver_lower = version.lower()
        return any(
            svc_lower.startswith(svc) and ver_lower.startswith(ver)
            for svc, ver in outdated_patterns
        )
