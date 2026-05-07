"""
PhantomStrike StealthAgent — evasion and anti-forensics specialist.

Uses the phantom-stealth module to generate evasive payloads, clean up
artifacts, and maintain operational security throughout the engagement.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.stealth")


class StealthAgent(BaseAgent):
    """
    Evasion and anti-forensics specialist agent.

    Responsibilities:
    - AV/EDR evasion payload generation
    - Log clearing and artifact removal
    - Traffic obfuscation and tunneling
    - Living-off-the-land (LOLBin) technique selection
    - Timestomping and metadata manipulation
    - Generates evasive payloads for use by other agents
    """

    @property
    def name(self) -> str:
        return "StealthAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are StealthAgent, an evasion and anti-forensics specialist for PhantomStrike. "
            "Your role is to ensure the engagement maintains operational security and evades detection. "
            "Techniques include: AV/EDR evasion via payload obfuscation and encoding, "
            "log clearing and artifact removal to reduce forensic footprint, "
            "traffic obfuscation using legitimate protocols (DNS, HTTPS), "
            "living-off-the-land (LOLBin) techniques to avoid dropping binaries, "
            "and timestomping to manipulate file metadata. "
            "Use the phantom-stealth module to generate evasive payloads and cleanup scripts. "
            "Always assess the opsec level of each technique before recommending it."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute stealth/evasion objective.

        1. Build fresh context from KG.
        2. Execute phantom-stealth module.
        3. Generate evasive payloads.
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
        }

        # 2. Load stealth skills
        skills = self._load_skills("stealth")
        context["available_skills"] = [getattr(s, "name", str(s)) for s in skills]

        # 3. Query AI for evasion strategy
        ai_response = self._query_ai(
            context,
            f"Plan evasion and stealth techniques for target: {target}. "
            "Recommend the best AV/EDR evasion and anti-forensics techniques for this environment.",
        )
        context["ai_plan"] = ai_response

        # 4. Execute phantom-stealth module — payload obfuscation
        obfuscate_result = self._execute_module(
            "phantom-stealth",
            target=target,
            technique="T1027",  # Obfuscated Files or Information
            operation="obfuscate_payload",
        )

        if obfuscate_result.get("success"):
            obf_data = obfuscate_result.get("data", obfuscate_result.get("results", {}))
            if isinstance(obf_data, dict):
                for payload in obf_data.get("payloads", []):
                    findings.append({
                        "type": "evasive_payload",
                        "technique": payload.get("technique", ""),
                        "format": payload.get("format", ""),
                        "path": payload.get("path", ""),
                        "av_bypass_rate": payload.get("av_bypass_rate", 0),
                    })
                    mitre_techniques.append("T1027")
        else:
            err = obfuscate_result.get("error", "phantom-stealth not available")
            logger.warning("[%s] phantom-stealth obfuscate: %s", self.name, err)
            errors.append(f"phantom-stealth obfuscate: {err}")

        # 5. Execute phantom-stealth module — log clearing
        cleanup_result = self._execute_module(
            "phantom-stealth",
            target=target,
            technique="T1070",  # Indicator Removal
            operation="clear_logs",
        )

        if cleanup_result.get("success"):
            cleanup_data = cleanup_result.get("data", cleanup_result.get("results", {}))
            if isinstance(cleanup_data, dict):
                for cleared in cleanup_data.get("cleared_logs", []):
                    findings.append({
                        "type": "log_cleared",
                        "log_path": cleared.get("path", ""),
                        "host": target,
                    })
                    mitre_techniques.append("T1070")
        else:
            err = cleanup_result.get("error", "phantom-stealth cleanup not available")
            logger.debug("[%s] phantom-stealth cleanup: %s", self.name, err)

        # 6. Execute phantom-stealth module — LOLBin selection
        lolbin_result = self._execute_module(
            "phantom-stealth",
            target=target,
            technique="T1218",  # System Binary Proxy Execution
            operation="select_lolbins",
        )

        if lolbin_result.get("success"):
            lolbin_data = lolbin_result.get("data", lolbin_result.get("results", {}))
            if isinstance(lolbin_data, dict):
                for lolbin in lolbin_data.get("lolbins", []):
                    findings.append({
                        "type": "lolbin_technique",
                        "binary": lolbin.get("binary", ""),
                        "technique": lolbin.get("technique", ""),
                        "os": lolbin.get("os", ""),
                    })
                    mitre_techniques.append("T1218")

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
