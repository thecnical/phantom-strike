"""
PhantomStrike ADAgent — Active Directory exploitation specialist.

Uses the phantom-ad module to perform Kerberoasting, AS-REP roasting,
BloodHound enumeration, and LDAP enumeration, adding AD findings to the KG.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.ad")


class ADAgent(BaseAgent):
    """
    Active Directory exploitation specialist agent.

    Responsibilities:
    - Kerberoasting (TGS hash extraction)
    - AS-REP roasting (accounts without pre-auth)
    - BloodHound/SharpHound enumeration
    - LDAP enumeration
    - Domain trust mapping
    - Adds AD findings (users, groups, hashes) to the Knowledge Graph
    """

    @property
    def name(self) -> str:
        return "ADAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are ADAgent, an Active Directory exploitation specialist for PhantomStrike. "
            "Your role is to enumerate and exploit Active Directory environments. "
            "Techniques include: Kerberoasting to extract TGS hashes for offline cracking, "
            "AS-REP roasting for accounts without pre-authentication, "
            "BloodHound/SharpHound enumeration to map attack paths to Domain Admin, "
            "LDAP enumeration for users, groups, GPOs, and trust relationships, "
            "and Pass-the-Hash/Pass-the-Ticket attacks using harvested credentials. "
            "Use the phantom-ad module for all AD operations. "
            "Document all discovered users, groups, hashes, and privilege escalation paths."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute Active Directory exploitation objective.

        1. Build fresh context from KG.
        2. Execute phantom-ad module operations.
        3. Add AD findings to KG.
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
            "known_credentials": [
                c.get("label") for c in kg_context.get("credentials", [])
            ],
        }

        # 2. Load AD skills
        skills = self._load_skills("ad")
        context["available_skills"] = [getattr(s, "name", str(s)) for s in skills]

        # 3. Query AI for AD attack strategy
        ai_response = self._query_ai(
            context,
            f"Plan Active Directory exploitation for target: {target}. "
            "Identify the best AD attack vectors given the current credentials and network context.",
        )
        context["ai_plan"] = ai_response

        # 4. Execute phantom-ad module — Kerberoasting
        kerb_result = self._execute_module(
            "phantom-ad",
            target=target,
            technique="T1558.003",  # Steal or Forge Kerberos Tickets: Kerberoasting
            operation="kerberoast",
        )

        if kerb_result.get("success"):
            kerb_data = kerb_result.get("data", kerb_result.get("results", {}))
            if isinstance(kerb_data, dict):
                for hash_entry in kerb_data.get("hashes", []):
                    username = hash_entry.get("username", "")
                    spn = hash_entry.get("spn", "")
                    hash_val = hash_entry.get("hash", "")
                    hash_type = hash_entry.get("hash_type", "krb5tgs")

                    findings.append({
                        "type": "kerberoast_hash",
                        "username": username,
                        "spn": spn,
                        "hash_type": hash_type,
                        "has_hash": bool(hash_val),
                    })

                    self._add_ad_cred_to_kg(username, hash_val, target, kg_updates)
                    mitre_techniques.append("T1558.003")
        else:
            err = kerb_result.get("error", "phantom-ad kerberoast not available")
            logger.warning("[%s] phantom-ad kerberoast: %s", self.name, err)
            errors.append(f"phantom-ad kerberoast: {err}")

        # 5. Execute phantom-ad module — AS-REP Roasting
        asrep_result = self._execute_module(
            "phantom-ad",
            target=target,
            technique="T1558.004",  # AS-REP Roasting
            operation="asreproast",
        )

        if asrep_result.get("success"):
            asrep_data = asrep_result.get("data", asrep_result.get("results", {}))
            if isinstance(asrep_data, dict):
                for hash_entry in asrep_data.get("hashes", []):
                    username = hash_entry.get("username", "")
                    findings.append({
                        "type": "asrep_hash",
                        "username": username,
                        "hash_type": "krb5asrep",
                    })
                    self._add_ad_cred_to_kg(
                        username, hash_entry.get("hash", ""), target, kg_updates
                    )
                    mitre_techniques.append("T1558.004")
        else:
            err = asrep_result.get("error", "phantom-ad asreproast not available")
            logger.debug("[%s] phantom-ad asreproast: %s", self.name, err)

        # 6. Execute phantom-ad module — LDAP enumeration
        ldap_result = self._execute_module(
            "phantom-ad",
            target=target,
            technique="T1087.002",  # Account Discovery: Domain Account
            operation="ldap_enum",
        )

        if ldap_result.get("success"):
            ldap_data = ldap_result.get("data", ldap_result.get("results", {}))
            if isinstance(ldap_data, dict):
                for user in ldap_data.get("users", []):
                    findings.append({
                        "type": "ad_user",
                        "username": user.get("username", ""),
                        "groups": user.get("groups", []),
                        "is_admin": user.get("is_admin", False),
                    })
                    self._add_ad_user_to_kg(
                        user.get("username", ""), target, kg_updates
                    )

                for group in ldap_data.get("groups", []):
                    findings.append({
                        "type": "ad_group",
                        "name": group.get("name", ""),
                        "members": group.get("members", []),
                    })

                mitre_techniques.append("T1087.002")
        else:
            err = ldap_result.get("error", "phantom-ad ldap_enum not available")
            logger.debug("[%s] phantom-ad ldap_enum: %s", self.name, err)

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

    def _add_ad_cred_to_kg(
        self,
        username: str,
        password_hash: str,
        source_host: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add an AD credential (hash) to the KG."""
        if self._knowledge_graph is None or not username:
            return
        try:
            source_host_id = None
            if source_host and source_host != "unknown":
                source_host_id = self._knowledge_graph.add_host(source_host)

            cred_id = self._knowledge_graph.add_credential(
                username=username,
                password_hash=password_hash,
                source_host_id=source_host_id,
                properties={"type": "kerberos_hash"},
            )

            if source_host_id is not None:
                from phantom.db.knowledge_graph import EdgeType
                self._knowledge_graph.link(source_host_id, cred_id, EdgeType.HAS_CRED)

            kg_updates.append({
                "action": "add_credential",
                "data": {"username": username, "source_host": source_host, "cred_id": cred_id},
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_ad_cred failed: %s", self.name, exc)

    def _add_ad_user_to_kg(
        self,
        username: str,
        domain: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add an AD user node to the KG."""
        if self._knowledge_graph is None or not username:
            return
        try:
            from phantom.db.knowledge_graph import NodeType

            props = {"username": username, "domain": domain, "type": "ad_user"}
            user_id = self._knowledge_graph._insert_node(NodeType.USER, username, props)
            kg_updates.append({
                "action": "add_user",
                "data": {"username": username, "domain": domain, "user_id": user_id},
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_ad_user failed: %s", self.name, exc)
