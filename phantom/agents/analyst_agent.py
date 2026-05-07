"""
PhantomStrike AnalystAgent — intelligence synthesis and strategic planning specialist.

Synthesizes all KG findings to identify attack paths, prioritize targets,
and suggest next objectives for the orchestrator.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.analyst")


class AnalystAgent(BaseAgent):
    """
    Intelligence synthesis and strategic planning specialist agent.

    Responsibilities:
    - Synthesize all KG findings into actionable intelligence
    - Identify high-value targets and attack paths
    - Prioritize next exploitation steps
    - Identify gaps in coverage
    - Suggest new objectives for the orchestrator
    - Does NOT execute modules — purely analytical
    """

    @property
    def name(self) -> str:
        return "AnalystAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are AnalystAgent, an intelligence synthesis and strategic planning specialist "
            "for PhantomStrike. "
            "Your role is to analyze all accumulated findings in the Knowledge Graph and "
            "provide strategic guidance for the engagement. "
            "Tasks include: identifying the highest-value targets based on vulnerability count, "
            "credential access, and network position; mapping attack paths from current access "
            "to high-value targets; identifying coverage gaps (unscanned hosts, untested services); "
            "and recommending the next set of objectives to maximize engagement impact. "
            "You do NOT execute modules — your output is pure analysis and recommendations. "
            "Provide clear, prioritized recommendations with supporting evidence from the KG."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute intelligence synthesis objective.

        1. Build fresh context from full KG state.
        2. Analyze high-value targets and attack paths.
        3. Query AI for strategic recommendations.
        4. Return AgentResult with analysis findings and next objectives.
        """
        start_time = time.time()
        findings: List[Dict[str, Any]] = []
        errors: List[str] = []
        kg_updates: List[Dict[str, Any]] = []
        mitre_techniques: List[str] = []

        target = getattr(objective, "target", None) or (
            self._opplan.target if self._opplan else "unknown"
        )

        # 1. Build fresh context with full KG state (Req 8.1, 8.2)
        kg_context = self._get_kg_context(target)
        context: Dict[str, Any] = {
            "agent": self.name,
            "objective_id": objective.id,
            "objective_title": objective.title,
            "target": target,
            "phase": str(objective.phase),
            "kg_context": kg_context,
        }

        # Enrich context with KG analytics
        if self._knowledge_graph is not None:
            try:
                hvt = self._knowledge_graph.get_high_value_targets()
                attack_paths = self._knowledge_graph.get_attack_paths()
                lateral_paths = self._knowledge_graph.get_lateral_movement_paths()

                context["high_value_targets"] = hvt[:10]  # Top 10
                context["attack_paths"] = attack_paths[:5]  # Top 5
                context["lateral_movement_paths"] = lateral_paths[:5]

                # Add HVT findings
                for hvt_entry in hvt[:5]:
                    findings.append({
                        "type": "high_value_target",
                        "host": hvt_entry.get("label", ""),
                        "score": hvt_entry.get("score", 0),
                        "num_vulns": hvt_entry.get("num_vulns", 0),
                        "num_creds": hvt_entry.get("num_creds", 0),
                        "num_services": hvt_entry.get("num_services", 0),
                    })

                # Add attack path findings
                for path in attack_paths[:3]:
                    findings.append({
                        "type": "attack_path",
                        "path": path.get("path", []),
                        "score": path.get("score", 0),
                        "description": path.get("description", ""),
                    })

                # Add lateral movement findings
                for lm_path in lateral_paths[:3]:
                    findings.append({
                        "type": "lateral_movement_path",
                        "from": lm_path.get("source_id"),
                        "to": lm_path.get("target_id"),
                    })

            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] KG analytics failed: %s", self.name, exc)
                errors.append(f"KG analytics: {exc}")

        # 2. Get OPPLAN context for gap analysis
        if self._opplan is not None:
            try:
                all_objectives = self._opplan.list_objectives()
                completed = [o for o in all_objectives if str(o.status) == "completed"]
                pending = [o for o in all_objectives if str(o.status) == "pending"]
                failed = [o for o in all_objectives if str(o.status) == "failed"]

                context["opplan_summary"] = {
                    "total": len(all_objectives),
                    "completed": len(completed),
                    "pending": len(pending),
                    "failed": len(failed),
                    "completed_phases": list({str(o.phase) for o in completed}),
                    "pending_phases": list({str(o.phase) for o in pending}),
                }

                findings.append({
                    "type": "engagement_progress",
                    "total_objectives": len(all_objectives),
                    "completed": len(completed),
                    "pending": len(pending),
                    "failed": len(failed),
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] OPPLAN analysis failed: %s", self.name, exc)

        # 3. Query AI for strategic analysis and next objectives
        ai_response = self._query_ai(
            context,
            f"Analyze the current engagement state for target: {target}. "
            "Identify: (1) the highest-priority next actions, "
            "(2) coverage gaps that need attention, "
            "(3) the most promising attack paths to high-value targets, "
            "(4) any new objectives that should be added to the OPPLAN.",
        )

        # Parse AI recommendations into structured findings
        if ai_response and not ai_response.startswith("[AnalystAgent] AI unavailable"):
            findings.append({
                "type": "strategic_analysis",
                "recommendations": ai_response,
                "target": target,
            })

        duration = time.time() - start_time
        success = len(findings) > 0

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
