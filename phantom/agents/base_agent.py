"""
PhantomStrike BaseAgent — abstract base class for all 13 specialist agents.

Provides:
- AgentResult dataclass: structured return type from every agent run()
- BaseAgent abstract class: fresh context per objective, RoE enforcement,
  KG context retrieval, module execution, and skill loading.

Requirements: 8.1–8.6
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger("phantom.agents.base_agent")


# ---------------------------------------------------------------------------
# AgentResult
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """
    Structured return type from every agent run() call.

    Fields
    ------
    success:
        Whether the objective was completed successfully.
    agent_name:
        Name of the agent that produced this result.
    objective_id:
        ID of the Objective that was executed.
    findings:
        Raw findings list (dicts) discovered during the objective.
    errors:
        List of error strings encountered during execution.
    kg_updates:
        Nodes/edges added to the Knowledge Graph during this run.
        Each entry is a dict with at least ``{"action": ..., "data": {...}}``.
    mitre_techniques_used:
        MITRE ATT&CK technique IDs exercised during this run.
    duration_seconds:
        Wall-clock time taken by run().
    raw_output:
        Raw string output captured from modules or AI reasoning.

    Requirements: 8.4
    """

    success: bool
    agent_name: str
    objective_id: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    kg_updates: List[Dict[str, Any]] = field(default_factory=list)
    mitre_techniques_used: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    raw_output: str = ""


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------


class BaseAgent(ABC):
    """
    Abstract base class for all PhantomStrike specialist agents.

    Each concrete agent must implement:
    - ``name`` property (str)
    - ``system_prompt`` property (str)
    - ``run(objective)`` method returning AgentResult

    The base class provides helper methods for AI querying, KG context
    retrieval, module execution with RoE enforcement, and skill loading.

    Parameters
    ----------
    ai_engine:
        EnhancedPhantomAIEngine or RemoteAIClient instance, or None.
    knowledge_graph:
        KnowledgeGraph instance, or None.
    opplan:
        OPPLAN instance, or None.
    roe:
        RoEMiddleware instance, or None.
    skill_library:
        SkillLibrary instance, or None.
    sandbox:
        DockerSandbox instance, or None.

    Requirements: 8.1–8.6
    """

    def __init__(
        self,
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    ) -> None:
        self._ai_engine = ai_engine
        self._knowledge_graph = knowledge_graph
        self._opplan = opplan
        self._roe = roe
        self._skill_library = skill_library
        self._sandbox = sandbox

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement these
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name (e.g. "ReconAgent")."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt injected into every AI call made by this agent."""
        ...

    @abstractmethod
    def run(self, objective) -> AgentResult:
        """
        Execute the given Objective and return an AgentResult.

        Implementations must:
        1. Build a fresh context dict for this objective (Req 8.1, 8.2).
        2. Perform the required actions, calling _execute_module() for any
           module invocations (Req 8.3).
        3. Update the Knowledge Graph with all findings (Req 8.6).
        4. Return a fully populated AgentResult (Req 8.4).

        Parameters
        ----------
        objective:
            An Objective instance from the OPPLAN.

        Returns
        -------
        AgentResult
        """
        ...

    # ------------------------------------------------------------------
    # Helper: AI querying
    # ------------------------------------------------------------------

    def _query_ai(self, context: Dict[str, Any], prompt: str) -> str:
        """
        Query the AI engine with a fresh context per call.

        No cross-objective conversation history is maintained — each call
        constructs a brand-new message list (Req 8.1, 8.2).

        The *context* dict is serialised as JSON and injected into the system
        message alongside the agent's own system_prompt.

        If the AI engine is unavailable (None) or raises any exception, a
        rule-based fallback string is returned instead (Req 8.5).

        Parameters
        ----------
        context:
            Arbitrary dict of contextual data for this call (KG findings,
            OPPLAN state, target info, etc.).
        prompt:
            The user-facing prompt / question for the AI.

        Returns
        -------
        str
            AI response string, or a fallback string on failure.
        """
        if self._ai_engine is None:
            logger.debug("[%s] AI engine not available — using rule-based fallback", self.name)
            return self._rule_based_fallback(prompt)

        try:
            # Build a fresh message list — no history from previous calls
            context_json = json.dumps(context, default=str, indent=2)
            system_content = (
                f"{self.system_prompt}\n\n"
                f"## Current Context\n```json\n{context_json}\n```"
            )
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]

            import inspect

            # ── chat() interface (preferred) ──────────────────────────
            if hasattr(self._ai_engine, "chat"):
                result = self._ai_engine.chat(messages)
                if inspect.isawaitable(result):
                    response = self._run_async(result)
                else:
                    response = result

            # ── query() interface (fallback) ──────────────────────────
            elif hasattr(self._ai_engine, "query"):
                result = self._ai_engine.query(
                    prompt=prompt, system_prompt=system_content
                )
                if inspect.isawaitable(result):
                    ai_resp = self._run_async(result)
                    response = ai_resp.content if hasattr(ai_resp, "content") else str(ai_resp)
                else:
                    response = result.content if hasattr(result, "content") else str(result)

            else:
                logger.warning(
                    "[%s] AI engine has no recognised interface — using fallback", self.name
                )
                return self._rule_based_fallback(prompt)

            return str(response) if response is not None else self._rule_based_fallback(prompt)

        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] AI query failed (%s) — using rule-based fallback", self.name, exc)
            return self._rule_based_fallback(prompt)

    @staticmethod
    def _run_async(coro) -> Any:
        """
        Run an async coroutine from a synchronous context.

        Agents' run() methods are synchronous but the AI engine (RemoteAIClient)
        is async.  This helper runs the coroutine safely regardless of whether
        an event loop is already running.
        """
        import asyncio
        import concurrent.futures

        try:
            # If there's already a running loop (we're inside asyncio.run()),
            # submit the coroutine to a fresh thread with its own loop.
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=120)
            else:
                return loop.run_until_complete(coro)
        except Exception as exc:
            logger.warning("[BaseAgent] _run_async failed: %s", exc)
            raise

    def _rule_based_fallback(self, prompt: str) -> str:
        """
        Return a simple rule-based response when the AI engine is unavailable.

        Requirements: 8.5
        """
        return (
            f"[{self.name}] AI unavailable. "
            f"Rule-based response for prompt: {prompt[:120]}"
        )

    # ------------------------------------------------------------------
    # Helper: Knowledge Graph context
    # ------------------------------------------------------------------

    def _get_kg_context(self, target: str) -> Dict[str, Any]:
        """
        Query the Knowledge Graph for hosts, vulnerabilities, and credentials
        relevant to *target*.

        Returns an empty dict if the KG is None or an error occurs.

        Parameters
        ----------
        target:
            IP address or hostname to look up in the KG.

        Returns
        -------
        dict
            Keys: ``hosts``, ``vulnerabilities``, ``credentials``.
            Each value is a list of dicts from the KG.

        Requirements: 8.1
        """
        if self._knowledge_graph is None:
            return {}

        try:
            kg = self._knowledge_graph

            # Hosts matching the target label
            hosts = kg.query(
                "SELECT id, type, label, properties FROM nodes "
                "WHERE type = 'host' AND label LIKE ?",
                (f"%{target}%",),
            )

            # Vulnerabilities linked to those hosts
            host_ids = [h["id"] for h in hosts]
            vulnerabilities: List[Dict[str, Any]] = []
            credentials: List[Dict[str, Any]] = []

            for host_id in host_ids:
                vulns = kg.query(
                    """
                    SELECT n.id, n.label, n.properties
                    FROM edges e
                    JOIN nodes n ON n.id = e.target_id
                    WHERE e.source_id = ? AND e.edge_type = 'has_vuln'
                    """,
                    (host_id,),
                )
                vulnerabilities.extend(vulns)

                creds = kg.query(
                    """
                    SELECT n.id, n.label, n.properties
                    FROM edges e
                    JOIN nodes n ON n.id = e.target_id
                    WHERE e.source_id = ? AND e.edge_type = 'has_cred'
                    """,
                    (host_id,),
                )
                credentials.extend(creds)

            return {
                "hosts": hosts,
                "vulnerabilities": vulnerabilities,
                "credentials": credentials,
            }

        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] KG context query failed: %s", self.name, exc)
            return {}

    # ------------------------------------------------------------------
    # Helper: Module execution with RoE enforcement
    # ------------------------------------------------------------------

    def _execute_module(self, module_name: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute a named module after checking Rules of Engagement.

        If a RoE instance is present, ``roe.check_action()`` is called first.
        If the check returns False (violation), the module is NOT invoked and
        a failure dict is returned instead (Req 8.3).

        If no RoE is configured, the module is invoked without a check.

        The module is looked up on ``self._opplan`` (if it exposes a module
        registry) or via the engine attached to the agent.  Concrete agents
        may override this method to use their own module dispatch.

        Parameters
        ----------
        module_name:
            Logical name of the module to invoke (e.g. "phantom-osint").
        **kwargs:
            Keyword arguments forwarded to the module.

        Returns
        -------
        dict
            Module result dict, or ``{"success": False, "error": "..."}`` on
            RoE violation or execution failure.

        Requirements: 8.3
        """
        target = kwargs.get("target", "")
        technique = kwargs.get("technique", "")

        # RoE check before any module invocation
        if self._roe is not None:
            try:
                allowed = self._roe.check_action(target=target, technique=technique)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] RoE check raised unexpectedly: %s", self.name, exc)
                allowed = False

            if not allowed:
                logger.info(
                    "[%s] Module '%s' blocked by RoE (target=%r, technique=%r)",
                    self.name,
                    module_name,
                    target,
                    technique,
                )
                return {"success": False, "error": "RoE violation"}

        # Attempt to invoke the module
        try:
            # Concrete agents typically have access to an engine with modules.
            # BaseAgent provides a best-effort lookup; subclasses may override.
            engine = getattr(self, "_engine", None)
            if engine is not None and hasattr(engine, "execute_module"):
                return engine.execute_module(module_name, **kwargs) or {}

            # No engine available — return a not-implemented result
            logger.debug(
                "[%s] No engine available to execute module '%s'", self.name, module_name
            )
            return {
                "success": False,
                "error": f"Module '{module_name}' not available (no engine configured)",
            }

        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Module '%s' raised: %s", self.name, module_name, exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Helper: Skill loading
    # ------------------------------------------------------------------

    def _load_skills(self, phase: str) -> List[Any]:
        """
        Load skill frontmatter objects for the given attack phase.

        Delegates to ``skill_library.filter_by_phase(phase)``.
        Returns an empty list if no skill library is configured.

        Parameters
        ----------
        phase:
            Attack phase string (e.g. "recon", "exploit").

        Returns
        -------
        list[SkillFrontmatter]
            Matching skill frontmatter objects, or [] if unavailable.

        Requirements: 8.1
        """
        if self._skill_library is None:
            return []

        try:
            return self._skill_library.filter_by_phase(phase)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Skill loading failed for phase '%s': %s", self.name, phase, exc)
            return []
