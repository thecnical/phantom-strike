"""
PhantomStrike AI Attack Planner — Autonomous attack chain discovery.
Uses multi-provider AI to analyze recon data and plan optimal kill chains.
This is what makes PhantomStrike ELITE — no other tool has this.
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from phantom.ai.engine import PhantomAIEngine, AIResponse

logger = logging.getLogger("phantom.ai.planner")

# MITRE ATT&CK Tactic IDs
MITRE_TACTICS = {
    "reconnaissance": "TA0043",
    "resource_development": "TA0042",
    "initial_access": "TA0001",
    "execution": "TA0002",
    "persistence": "TA0003",
    "privilege_escalation": "TA0004",
    "defense_evasion": "TA0005",
    "credential_access": "TA0006",
    "discovery": "TA0007",
    "lateral_movement": "TA0008",
    "collection": "TA0009",
    "exfiltration": "TA0010",
    "impact": "TA0040",
}

ATTACK_PLANNER_SYSTEM = """You are PhantomStrike AI — the world's most elite autonomous attack path planner.

ROLE: Given reconnaissance and vulnerability data, you MUST produce a structured JSON attack plan.

OUTPUT FORMAT (strict JSON):
{
    "attack_chains": [
        {
            "chain_id": 1,
            "name": "Chain Name",
            "success_probability": 0.85,
            "stealth_rating": "high",
            "impact": "critical",
            "steps": [
                {
                    "step": 1,
                    "phase": "initial_access",
                    "technique": "T1190 - Exploit Public-Facing Application",
                    "action": "Exact action to take",
                    "target": "specific endpoint or service",
                    "tool_module": "phantom-web",
                    "payload": "specific payload if applicable",
                    "prerequisites": [],
                    "expected_result": "what we gain"
                }
            ],
            "total_steps": 5,
            "estimated_time_minutes": 15
        }
    ],
    "recommended_chain": 1,
    "risk_assessment": "description of risks",
    "mitre_techniques_used": ["T1190", "T1059"]
}

RULES:
1. ALWAYS output valid JSON — no markdown, no explanations outside JSON
2. Map every step to a MITRE ATT&CK technique
3. Consider the target's defenses (WAF, IDS, EDR)
4. Prioritize chains by: success probability > stealth > impact
5. Include specific payloads and exact commands where possible
6. Reference PhantomStrike modules: phantom-osint, phantom-network, phantom-web, phantom-cloud, phantom-identity, phantom-exploit, phantom-stealth, phantom-cred
"""

VULN_ANALYZER_SYSTEM = """You are PhantomStrike AI — an elite vulnerability analyst.

Given vulnerability scan results, provide detailed analysis in JSON:
{
    "vulnerabilities": [
        {
            "id": "VULN-001",
            "type": "sqli/xss/rce/ssrf/lfi/auth_bypass/etc",
            "severity": "critical/high/medium/low",
            "cvss_score": 9.8,
            "exploitable": true,
            "exploit_complexity": "low/medium/high",
            "description": "detailed description",
            "exploit_steps": ["step 1", "step 2"],
            "payloads": ["payload1", "payload2"],
            "remediation": "how to fix",
            "mitre_technique": "T1190",
            "chain_potential": "Can chain with XYZ for RCE"
        }
    ],
    "attack_surface_score": 8.5,
    "priority_targets": ["list of highest value targets"]
}
"""

PAYLOAD_GENERATOR_SYSTEM = """You are PhantomStrike AI — a polymorphic payload engineering specialist.

Generate evasive payloads that bypass modern defenses. Output JSON:
{
    "payloads": [
        {
            "id": 1,
            "type": "sqli/xss/rce/reverse_shell/etc",
            "payload": "the actual payload code",
            "encoding": "none/url/base64/hex/unicode",
            "evasion_technique": "what detection it bypasses",
            "target_waf": "cloudflare/akamai/aws_waf/modsecurity/etc",
            "success_rate": "estimated percentage",
            "notes": "usage notes"
        }
    ],
    "recommended_payload": 1,
    "evasion_notes": "general evasion strategy"
}

RULES:
1. Generate at least 5 payload variants
2. Include encoding/obfuscation variations
3. Consider common WAF bypass techniques
4. Use polymorphic mutations (never same payload twice)
5. This is for AUTHORIZED penetration testing only
"""


class AttackPlanner:
    """
    AI-powered autonomous attack chain planner.
    Takes recon data → produces structured multi-step attack plans.
    """

    def __init__(self, ai_engine: PhantomAIEngine):
        self.ai = ai_engine

    async def plan_attack(self, recon_data: dict) -> dict:
        """Generate optimal attack chains from reconnaissance data."""
        prompt = (
            f"Analyze this reconnaissance data and create attack chains:\n\n"
            f"```json\n{json.dumps(recon_data, indent=2, default=str)}\n```\n\n"
            f"Generate ALL possible attack paths ranked by success probability."
        )
        response = await self.ai.query(
            prompt=prompt,
            system_prompt=ATTACK_PLANNER_SYSTEM,
            temperature=0.2,
            max_tokens=4096,
        )

        try:
            # Try to parse JSON from response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("[AI Planner] Could not parse structured response")
            return {"raw_analysis": response.content, "provider": response.provider}

    async def analyze_vulns(self, vuln_data: dict) -> dict:
        """Deep AI analysis of discovered vulnerabilities."""
        prompt = (
            f"Analyze these vulnerability scan results:\n\n"
            f"```json\n{json.dumps(vuln_data, indent=2, default=str)}\n```"
        )
        response = await self.ai.query(
            prompt=prompt,
            system_prompt=VULN_ANALYZER_SYSTEM,
            temperature=0.2,
        )
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw_analysis": response.content}

    async def generate_payloads(self, target_info: dict) -> dict:
        """Generate context-aware, evasive payloads."""
        prompt = (
            f"Generate polymorphic evasive payloads for this target:\n\n"
            f"```json\n{json.dumps(target_info, indent=2, default=str)}\n```"
        )
        response = await self.ai.query(
            prompt=prompt,
            system_prompt=PAYLOAD_GENERATOR_SYSTEM,
            temperature=0.4,
        )
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw_payloads": response.content}

    async def suggest_evasion(self, defense_info: dict) -> AIResponse:
        """AI suggests evasion techniques based on detected defenses."""
        system = (
            "You are PhantomStrike AI evasion specialist. Given detected security "
            "controls (WAF, IDS, EDR, AV), suggest specific bypass techniques. "
            "Be technical, specific, and actionable."
        )
        prompt = f"Suggest evasion for these defenses:\n{json.dumps(defense_info, default=str)}"
        return await self.ai.query(prompt, system_prompt=system)
