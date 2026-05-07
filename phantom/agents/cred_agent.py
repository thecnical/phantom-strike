"""
PhantomStrike CredAgent — credential harvesting and cracking specialist.

Uses the phantom-cred module to discover, harvest, and crack credentials,
adding them to the Knowledge Graph for use by other agents.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.cred")


class CredAgent(BaseAgent):
    """
    Credential harvesting and cracking specialist agent.

    Responsibilities:
    - Password spraying and brute-force attacks
    - Hash dumping and cracking
    - Credential stuffing from known breaches
    - Default credential testing
    - Adds discovered credentials to the Knowledge Graph
    """

    @property
    def name(self) -> str:
        return "CredAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are CredAgent, a credential harvesting and cracking specialist for PhantomStrike. "
            "Your role is to discover, harvest, and crack credentials across the target environment. "
            "Techniques include: password spraying against discovered services, "
            "hash dumping from compromised systems, default credential testing on network devices, "
            "and credential stuffing using known breach data. "
            "Use the phantom-cred module and sandbox tools (hydra, john, hashcat) for attacks. "
            "Store all discovered credentials in the Knowledge Graph for use by other agents. "
            "Never store plaintext passwords in logs — use hashes where possible."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute credential harvesting objective.

        1. Build fresh context from KG (hosts, services, existing creds).
        2. Execute phantom-cred module.
        3. Add credentials to KG.
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
            "known_services": [
                v.get("label") for v in kg_context.get("vulnerabilities", [])
            ],
        }

        # 2. Load cred skills
        skills = self._load_skills("cred")
        context["available_skills"] = [getattr(s, "name", str(s)) for s in skills]

        # 3. Query AI for credential attack strategy
        ai_response = self._query_ai(
            context,
            f"Plan credential harvesting for target: {target}. "
            "Identify the best credential attack vectors based on discovered services.",
        )
        context["ai_plan"] = ai_response

        # 4. Execute phantom-cred module
        cred_result = self._execute_module(
            "phantom-cred",
            target=target,
            technique="T1110",  # Brute Force
        )

        if cred_result.get("success"):
            cred_data = cred_result.get("data", cred_result.get("results", {}))
            if isinstance(cred_data, dict):
                # Process discovered credentials
                for cred in cred_data.get("credentials", []):
                    username = cred.get("username", "")
                    password_hash = cred.get("hash", "")
                    plaintext = cred.get("plaintext", "")
                    service = cred.get("service", "")

                    findings.append({
                        "type": "credential",
                        "username": username,
                        "service": service,
                        "has_plaintext": bool(plaintext),
                        "has_hash": bool(password_hash),
                    })

                    self._add_cred_to_kg(
                        username, password_hash, plaintext, target, kg_updates
                    )
                    mitre_techniques.append("T1110")

                # Process cracked hashes
                for cracked in cred_data.get("cracked_hashes", []):
                    username = cracked.get("username", "")
                    findings.append({
                        "type": "cracked_credential",
                        "username": username,
                        "hash_type": cracked.get("hash_type", ""),
                    })
                    self._add_cred_to_kg(
                        username,
                        cracked.get("hash", ""),
                        cracked.get("plaintext", ""),
                        target,
                        kg_updates,
                    )
                    mitre_techniques.append("T1110.002")  # Password Cracking

                # Process default credentials found
                for default_cred in cred_data.get("default_credentials", []):
                    findings.append({
                        "type": "default_credential",
                        "service": default_cred.get("service", ""),
                        "username": default_cred.get("username", ""),
                        "device": default_cred.get("device", ""),
                    })
                    mitre_techniques.append("T1078.001")  # Default Accounts
        else:
            err = cred_result.get("error", "phantom-cred not available")
            logger.warning("[%s] phantom-cred: %s", self.name, err)
            errors.append(f"phantom-cred: {err}")

        # 5. Try sandbox hydra for password spraying if available
        if self._sandbox is not None and target != "unknown":
            try:
                hydra_result = self._sandbox.run_hydra(
                    target, "ssh", "/usr/share/wordlists/rockyou.txt"
                )
                if isinstance(hydra_result, dict) and hydra_result.get("success"):
                    findings.append({
                        "type": "hydra_output",
                        "target": target,
                        "output": hydra_result.get("stdout", ""),
                    })
                    mitre_techniques.append("T1110.003")  # Password Spraying
            except Exception as exc:  # noqa: BLE001
                logger.debug("[%s] Sandbox hydra failed: %s", self.name, exc)

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

    def _add_cred_to_kg(
        self,
        username: str,
        password_hash: str,
        plaintext: str,
        source_host: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add a credential to the KG."""
        if self._knowledge_graph is None or not username:
            return
        try:
            # Get source host ID if available
            source_host_id = None
            if source_host and source_host != "unknown":
                source_host_id = self._knowledge_graph.add_host(source_host)

            cred_id = self._knowledge_graph.add_credential(
                username=username,
                password_hash=password_hash,
                plaintext=plaintext,
                source_host_id=source_host_id,
            )

            # Link credential to host if we have one
            if source_host_id is not None:
                from phantom.db.knowledge_graph import EdgeType
                self._knowledge_graph.link(source_host_id, cred_id, EdgeType.HAS_CRED)

            kg_updates.append({
                "action": "add_credential",
                "data": {
                    "username": username,
                    "source_host": source_host,
                    "cred_id": cred_id,
                },
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_credential failed: %s", self.name, exc)
