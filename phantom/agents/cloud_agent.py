"""
PhantomStrike CloudAgent — cloud infrastructure exploitation specialist.

Uses the phantom-cloud module to discover and exploit cloud misconfigurations
(AWS, Azure, GCP), adding findings to the Knowledge Graph.

Requirements: 8.1–8.6, 9.1–9.6
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from phantom.agents.base_agent import AgentResult, BaseAgent

logger = logging.getLogger("phantom.agents.cloud")


class CloudAgent(BaseAgent):
    """
    Cloud infrastructure exploitation specialist agent.

    Responsibilities:
    - Cloud provider enumeration (AWS, Azure, GCP)
    - S3/blob storage misconfiguration discovery
    - IAM privilege escalation paths
    - Metadata service exploitation (SSRF → IMDS)
    - Exposed cloud credentials discovery
    - Adds cloud misconfigurations to the Knowledge Graph
    """

    @property
    def name(self) -> str:
        return "CloudAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are CloudAgent, a cloud infrastructure exploitation specialist for PhantomStrike. "
            "Your role is to discover and exploit cloud misconfigurations across AWS, Azure, and GCP. "
            "Focus on: publicly accessible S3 buckets and blob storage, overly permissive IAM roles, "
            "exposed metadata services (IMDS), leaked cloud credentials in code repositories, "
            "and insecure serverless function configurations. "
            "Use the phantom-cloud module to enumerate cloud resources and identify privilege "
            "escalation paths. Document all misconfigurations with their potential impact."
        )

    def run(self, objective) -> AgentResult:
        """
        Execute cloud exploitation objective.

        1. Build fresh context from KG.
        2. Execute phantom-cloud module.
        3. Add cloud misconfigurations to KG.
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

        # 2. Load cloud skills
        skills = self._load_skills("cloud")
        context["available_skills"] = [getattr(s, "name", str(s)) for s in skills]

        # 3. Query AI for cloud attack strategy
        ai_response = self._query_ai(
            context,
            f"Plan cloud infrastructure exploitation for target: {target}. "
            "Identify the most likely cloud misconfigurations to test.",
        )
        context["ai_plan"] = ai_response

        # 4. Execute phantom-cloud module
        cloud_result = self._execute_module(
            "phantom-cloud",
            target=target,
            technique="T1530",  # Data from Cloud Storage Object
        )

        if cloud_result.get("success"):
            cloud_data = cloud_result.get("data", cloud_result.get("results", {}))
            if isinstance(cloud_data, dict):
                # Process storage misconfigurations
                for bucket in cloud_data.get("public_buckets", []):
                    findings.append({
                        "type": "cloud_misconfiguration",
                        "subtype": "public_storage",
                        "resource": bucket,
                        "severity": "high",
                    })
                    self._add_cloud_finding_to_kg(
                        target, "Public Cloud Storage", bucket, "high", kg_updates
                    )
                    mitre_techniques.append("T1530")

                # Process IAM findings
                for iam_issue in cloud_data.get("iam_issues", []):
                    findings.append({
                        "type": "cloud_misconfiguration",
                        "subtype": "iam_misconfiguration",
                        "resource": iam_issue.get("resource", ""),
                        "issue": iam_issue.get("issue", ""),
                        "severity": iam_issue.get("severity", "medium"),
                    })
                    self._add_cloud_finding_to_kg(
                        target,
                        "IAM Misconfiguration",
                        iam_issue.get("resource", ""),
                        iam_issue.get("severity", "medium"),
                        kg_updates,
                    )
                    mitre_techniques.append("T1078.004")  # Valid Accounts: Cloud Accounts

                # Process metadata service findings
                for meta_finding in cloud_data.get("metadata_findings", []):
                    findings.append({
                        "type": "cloud_misconfiguration",
                        "subtype": "metadata_service",
                        "resource": meta_finding,
                        "severity": "critical",
                    })
                    self._add_cloud_finding_to_kg(
                        target, "Metadata Service Exposure", meta_finding, "critical", kg_updates
                    )
                    mitre_techniques.append("T1552.005")  # Cloud Instance Metadata API

                # Process leaked credentials
                for cred in cloud_data.get("leaked_credentials", []):
                    findings.append({
                        "type": "cloud_credential",
                        "provider": cred.get("provider", "unknown"),
                        "key_id": cred.get("key_id", ""),
                        "source": cred.get("source", ""),
                    })
                    self._add_cloud_cred_to_kg(
                        cred.get("key_id", "cloud_key"),
                        cred.get("provider", "unknown"),
                        kg_updates,
                    )
                    mitre_techniques.append("T1552.001")  # Credentials In Files
        else:
            err = cloud_result.get("error", "phantom-cloud not available")
            logger.warning("[%s] phantom-cloud: %s", self.name, err)
            errors.append(f"phantom-cloud: {err}")

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

    def _add_cloud_finding_to_kg(
        self,
        host: str,
        vuln_type: str,
        resource: str,
        severity: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add a cloud misconfiguration as a vulnerability in the KG."""
        if self._knowledge_graph is None:
            return
        try:
            host_id = self._knowledge_graph.add_host(host)
            vuln_id = self._knowledge_graph.add_vulnerability(
                host_id, vuln_type, url=resource, severity=severity
            )
            kg_updates.append({
                "action": "add_vulnerability",
                "data": {
                    "host": host,
                    "vuln_type": vuln_type,
                    "resource": resource,
                    "severity": severity,
                    "vuln_id": vuln_id,
                },
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_cloud_finding failed: %s", self.name, exc)

    def _add_cloud_cred_to_kg(
        self,
        key_id: str,
        provider: str,
        kg_updates: List[Dict[str, Any]],
    ) -> None:
        """Add a cloud credential to the KG."""
        if self._knowledge_graph is None:
            return
        try:
            cred_id = self._knowledge_graph.add_credential(
                username=key_id,
                properties={"provider": provider, "type": "cloud_key"},
            )
            kg_updates.append({
                "action": "add_credential",
                "data": {"key_id": key_id, "provider": provider, "cred_id": cred_id},
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG add_cloud_cred failed: %s", self.name, exc)
