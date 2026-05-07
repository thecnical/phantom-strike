"""
PhantomStrike ReportAgent — engagement report generation specialist.

Uses the phantom-report module to generate a comprehensive final engagement
report from the full Knowledge Graph state.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.report")


class ReportAgent(BaseAgent):
    """
    Engagement report generation specialist agent.

    Responsibilities:
    - Compile all KG findings into a structured report
    - Generate executive summary and technical findings
    - Produce remediation recommendations
    - Export report in multiple formats (Markdown, JSON)
    - Uses phantom-report module for formatting
    """

    @property
    def name(self) -> str:
        return "ReportAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are ReportAgent, an engagement report generation specialist for PhantomStrike. "
            "Your role is to compile all findings from the Knowledge Graph into a comprehensive "
            "penetration testing report. "
            "The report must include: "
            "(1) Executive Summary — high-level findings and business impact, "
            "(2) Scope and Methodology — what was tested and how, "
            "(3) Technical Findings — detailed vulnerability descriptions with CVEs, "
            "CVSS scores, and proof-of-concept evidence, "
            "(4) Attack Path Narrative — step-by-step account of the attack chain, "
            "(5) Remediation Recommendations — prioritized, actionable fixes, "
            "(6) Appendices — raw tool output, KG export, MITRE ATT&CK mapping. "
            "Use the phantom-report module for formatting. "
            "Ensure the report is professional, accurate, and actionable."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute report generation objective.

        1. Build fresh context from full KG state.
        2. Execute phantom-report module.
        3. Generate fallback report if module unavailable.
        4. Return AgentResult with report path.
        """
        start_time = time.time()
        findings: List[Dict[str, Any]] = []
        errors: List[str] = []
        kg_updates: List[Dict[str, Any]] = []
        mitre_techniques: List[str] = []

        target = getattr(objective, "target", None) or (
            self._opplan.target if self._opplan else "unknown"
        )

        engagement_id = (
            self._opplan.engagement_id if self._opplan else "unknown"
        )

        # 1. Build fresh context with full KG export (Req 8.1, 8.2)
        kg_export: Dict[str, Any] = {}
        if self._knowledge_graph is not None:
            try:
                kg_export = self._knowledge_graph.export_to_json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] KG export failed: %s", self.name, exc)
                errors.append(f"KG export: {exc}")

        context: Dict[str, Any] = {
            "agent": self.name,
            "objective_id": objective.id,
            "objective_title": objective.title,
            "target": target,
            "engagement_id": engagement_id,
            "phase": str(objective.phase),
            "kg_summary": {
                "node_count": len(kg_export.get("nodes", [])),
                "edge_count": len(kg_export.get("edges", [])),
                "attack_path_count": len(kg_export.get("attack_paths", [])),
            },
        }

        # Add HVT summary to context
        if self._knowledge_graph is not None:
            try:
                hvt = self._knowledge_graph.get_high_value_targets()
                context["high_value_targets"] = hvt[:10]
                context["attack_paths"] = self._knowledge_graph.get_attack_paths()[:5]
            except Exception as exc:  # noqa: BLE001
                logger.debug("[%s] KG analytics for report failed: %s", self.name, exc)

        # 2. Query AI for report narrative
        ai_response = self._query_ai(
            context,
            f"Generate a comprehensive penetration testing report for engagement {engagement_id} "
            f"against target: {target}. "
            "Include executive summary, key findings, attack narrative, and remediation recommendations.",
        )

        # 3. Execute phantom-report module
        report_result = self._execute_module(
            "phantom-report",
            target=target,
            technique="",  # Reporting is not a MITRE technique
            engagement_id=engagement_id,
            kg_data=kg_export,
        )

        report_path: str = ""

        if report_result.get("success"):
            report_data = report_result.get("data", report_result.get("results", {}))
            if isinstance(report_data, dict):
                report_path = report_data.get("report_path", "")
                findings.append({
                    "type": "report",
                    "path": report_path,
                    "format": report_data.get("format", "markdown"),
                    "engagement_id": engagement_id,
                })
        else:
            err = report_result.get("error", "phantom-report not available")
            logger.warning("[%s] phantom-report: %s — generating fallback report", self.name, err)
            errors.append(f"phantom-report: {err}")

            # 4. Generate fallback report when module is unavailable
            report_path = self._generate_fallback_report(
                target, engagement_id, kg_export, ai_response
            )
            if report_path:
                findings.append({
                    "type": "report",
                    "path": report_path,
                    "format": "markdown",
                    "engagement_id": engagement_id,
                    "generated_by": "fallback",
                })

        duration = time.time() - start_time
        success = bool(report_path)

        logger.info(
            "[%s] Completed objective %s: report_path=%s in %.1fs",
            self.name, objective.id, report_path, duration,
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

    def _generate_fallback_report(
        self,
        target: str,
        engagement_id: str,
        kg_export: Dict[str, Any],
        ai_narrative: str,
    ) -> str:
        """
        Generate a basic Markdown report when phantom-report is unavailable.

        Returns the path to the generated report file, or empty string on failure.
        """
        try:
            report_dir = os.path.expanduser("~/.phantom-strike/reports")
            os.makedirs(report_dir, exist_ok=True)
            report_path = os.path.join(report_dir, f"report_{engagement_id}.md")

            nodes = kg_export.get("nodes", [])
            edges = kg_export.get("edges", [])
            attack_paths = kg_export.get("attack_paths", [])

            hosts = [n for n in nodes if n.get("type") == "host"]
            vulns = [n for n in nodes if n.get("type") == "vulnerability"]
            creds = [n for n in nodes if n.get("type") == "credential"]

            lines = [
                f"# PhantomStrike Engagement Report",
                f"",
                f"**Engagement ID:** {engagement_id}  ",
                f"**Target:** {target}  ",
                f"",
                f"---",
                f"",
                f"## Executive Summary",
                f"",
                ai_narrative if ai_narrative else "_AI narrative unavailable._",
                f"",
                f"---",
                f"",
                f"## Knowledge Graph Summary",
                f"",
                f"| Metric | Count |",
                f"|--------|-------|",
                f"| Hosts discovered | {len(hosts)} |",
                f"| Vulnerabilities found | {len(vulns)} |",
                f"| Credentials harvested | {len(creds)} |",
                f"| Attack paths mapped | {len(attack_paths)} |",
                f"| Total graph edges | {len(edges)} |",
                f"",
                f"---",
                f"",
                f"## Discovered Hosts",
                f"",
            ]

            for host in hosts:
                props = host.get("properties", {})
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except Exception:
                        props = {}
                hostname = props.get("hostname", "")
                os_info = props.get("os", "")
                lines.append(
                    f"- **{host.get('label', 'unknown')}**"
                    + (f" ({hostname})" if hostname else "")
                    + (f" — {os_info}" if os_info else "")
                )

            lines += [
                f"",
                f"---",
                f"",
                f"## Vulnerabilities",
                f"",
            ]

            for vuln in vulns:
                props = vuln.get("properties", {})
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except Exception:
                        props = {}
                severity = props.get("severity", "unknown")
                cve = props.get("cve", "")
                lines.append(
                    f"- **{vuln.get('label', 'unknown')}** "
                    f"[{severity.upper()}]"
                    + (f" — {cve}" if cve else "")
                )

            lines += [
                f"",
                f"---",
                f"",
                f"## Attack Paths",
                f"",
            ]

            for path in attack_paths:
                lines.append(
                    f"- Score: {path.get('score', 0):.1f} — "
                    f"{path.get('description', 'No description')}"
                )

            lines += [
                f"",
                f"---",
                f"",
                f"## Remediation Recommendations",
                f"",
                f"1. Patch all critical and high severity vulnerabilities immediately.",
                f"2. Rotate all compromised credentials.",
                f"3. Review and harden network segmentation.",
                f"4. Implement multi-factor authentication on all remote access services.",
                f"5. Deploy endpoint detection and response (EDR) on all hosts.",
                f"",
                f"---",
                f"",
                f"*Report generated by PhantomStrike ReportAgent (fallback mode)*",
            ]

            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))

            logger.info("[%s] Fallback report written to %s", self.name, report_path)
            return report_path

        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Fallback report generation failed: %s", self.name, exc)
            return ""
