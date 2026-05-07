"""
PhantomStrike PhantomOrchestrator — manages all 13 specialist agents, reads
OPPLAN, dispatches objectives in parallel respecting the dependency graph, and
drives autonomous decision-making.

Requirements: 9.1–9.6, 10.1–10.7
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from phantom.agents.base_agent import AgentResult, BaseAgent
from phantom.core.opplan import OPPLAN, Objective, ObjPhase, ObjStatus

logger = logging.getLogger("phantom.agents.orchestrator")

# ---------------------------------------------------------------------------
# Phase → agent name mapping (used when specialist agents are registered)
# ---------------------------------------------------------------------------

_PHASE_TO_AGENT: Dict[str, str] = {
    ObjPhase.RECON: "ReconAgent",
    ObjPhase.SCAN: "ScannerAgent",
    ObjPhase.EXPLOIT: "ExploitAgent",
    ObjPhase.POST_EXPLOIT: "PostExploitAgent",
    ObjPhase.LATERAL_MOVE: "PostExploitAgent",  # fallback
    ObjPhase.EXFIL: "PostExploitAgent",          # fallback
    ObjPhase.CLEANUP: "StealthAgent",
    ObjPhase.REPORT: "ReportAgent",
}

# Additional phase aliases used in the design doc
_PHASE_TO_AGENT.update(
    {
        "web": "WebExploitAgent",
        "cloud": "CloudAgent",
        "cred": "CredAgent",
        "ad": "ADAgent",
        "c2": "C2Agent",
        "stealth": "StealthAgent",
        "reverser": "ReverserAgent",
        "analyst": "AnalystAgent",
    }
)


# ---------------------------------------------------------------------------
# _NullAgent — placeholder used when a real agent is not yet registered
# ---------------------------------------------------------------------------


class _NullAgent(BaseAgent):
    """
    Placeholder agent returned when no specialist agent is registered for a
    given phase.  Always returns a failed AgentResult with a descriptive error.
    """

    def __init__(self, phase: str) -> None:
        super().__init__()
        self._phase = phase

    @property
    def name(self) -> str:
        return f"NullAgent({self._phase})"

    @property
    def system_prompt(self) -> str:
        return ""

    def run(self, objective: Objective) -> AgentResult:  # type: ignore[override]
        return AgentResult(
            success=False,
            agent_name=self.name,
            objective_id=objective.id,
            errors=[f"No agent registered for phase '{self._phase}'"],
        )


# ---------------------------------------------------------------------------
# PhantomOrchestrator
# ---------------------------------------------------------------------------


class PhantomOrchestrator:
    """
    Manages all 13 specialist agents, reads OPPLAN, dispatches objectives in
    parallel respecting the dependency graph, and drives autonomous
    decision-making.

    Parameters
    ----------
    ai_engine:
        EnhancedPhantomAIEngine or RemoteAIClient, or None.
    knowledge_graph:
        KnowledgeGraph instance, or None.
    roe:
        RoEMiddleware instance, or None.
    skill_library:
        SkillLibrary instance, or None.
    sandbox:
        DockerSandbox instance, or None.
    max_threads:
        Maximum number of concurrently in-progress objectives.

    Requirements: 9.1–9.6, 10.1–10.7
    """

    def __init__(
        self,
        ai_engine=None,
        knowledge_graph=None,
        roe=None,
        skill_library=None,
        sandbox=None,
        max_threads: int = 4,
    ) -> None:
        self._ai_engine = ai_engine
        self._knowledge_graph = knowledge_graph
        self._roe = roe
        self._skill_library = skill_library
        self._sandbox = sandbox
        self._max_threads = max_threads

        # Registry of all specialist agents keyed by agent name
        self._agents: Dict[str, BaseAgent] = {}

        # Current operational plan
        self._opplan: Optional[OPPLAN] = None

        # Operator control flags
        self._paused: bool = False
        self._status: str = "idle"  # "idle" | "running" | "paused" | "complete"

        # Tracking for get_status()
        self._current_objectives: List[str] = []
        self._completed: List[str] = []
        self._failed: List[str] = []

    # ------------------------------------------------------------------
    # Agent registry
    # ------------------------------------------------------------------

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a specialist agent by its name."""
        self._agents[agent.name] = agent
        logger.debug("[Orchestrator] Registered agent: %s", agent.name)

    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Return the registered agent with the given name, or None if not found.

        Requirements: 9.1
        """
        return self._agents.get(agent_name)

    def _select_agent_for_objective(self, objective: Objective) -> BaseAgent:
        """
        Select the best agent for an objective.

        Lookup order:
        1. objective.assigned_agent (if set and registered)
        2. Phase → agent name mapping
        3. _NullAgent (graceful fallback when no agent is registered)
        """
        # 1. Explicit assignment
        if objective.assigned_agent and objective.assigned_agent in self._agents:
            return self._agents[objective.assigned_agent]

        # 2. Phase mapping
        phase_str = str(objective.phase)
        agent_name = _PHASE_TO_AGENT.get(phase_str)
        if agent_name and agent_name in self._agents:
            return self._agents[agent_name]

        # 3. Graceful fallback
        logger.warning(
            "[Orchestrator] No agent registered for phase '%s' (objective %s) — using NullAgent",
            phase_str,
            objective.id,
        )
        return _NullAgent(phase_str)

    # ------------------------------------------------------------------
    # Core execution loop
    # ------------------------------------------------------------------

    async def execute_opplan(self, opplan: OPPLAN) -> Dict[str, Any]:
        """
        Execute an approved OPPLAN.

        Dispatch loop:
        - Calls opplan.get_ready_objectives() each iteration.
        - Dispatches up to max_threads objectives concurrently via asyncio.gather().
        - After each objective completes, calls ai_decide_next() to add new objectives.
        - Marks failed objectives and continues (does not stop on failure).
        - Returns a results dict when all objectives reach a terminal state.

        Requirements: 9.1–9.6
        """
        self._opplan = opplan
        self._status = "running"
        self._current_objectives = []
        self._completed = []
        self._failed = []

        results: Dict[str, AgentResult] = {}
        in_progress_tasks: Dict[str, asyncio.Task] = {}  # obj_id → Task

        logger.info(
            "[Orchestrator] Starting OPPLAN execution: engagement_id=%s target=%s",
            opplan.engagement_id,
            opplan.target,
        )

        def _all_terminal() -> bool:
            """True when every objective has a terminal status."""
            for obj in opplan.list_objectives():
                s = str(obj.status)
                if s not in (ObjStatus.COMPLETED, ObjStatus.FAILED, ObjStatus.SKIPPED):
                    return False
            return True

        def _count_in_progress() -> int:
            return len(in_progress_tasks)

        while not _all_terminal():
            # Honour pause flag — wait without dispatching new work
            if self._paused:
                self._status = "paused"
                await asyncio.sleep(0.5)
                continue

            self._status = "running"

            # Collect ready objectives that are not already in-progress
            ready = [
                obj
                for obj in opplan.get_ready_objectives()
                if obj.id not in in_progress_tasks
            ]

            # How many slots are available?
            slots = self._max_threads - _count_in_progress()

            if ready and slots > 0:
                batch = ready[:slots]

                for obj in batch:
                    agent = self._select_agent_for_objective(obj)
                    opplan.update_objective(
                        obj.id,
                        status=ObjStatus.IN_PROGRESS,
                        assigned_agent=agent.name,
                    )
                    self._current_objectives.append(obj.id)
                    logger.info(
                        "[Orchestrator] Dispatching objective %s (%s) → %s",
                        obj.id,
                        obj.title,
                        agent.name,
                    )

                    # Wrap synchronous run() in a thread executor so it doesn't
                    # block the event loop; async agents can override run() as
                    # a coroutine and we handle both cases.
                    task = asyncio.create_task(
                        self._run_agent(agent, obj)
                    )
                    in_progress_tasks[obj.id] = task

            # If nothing is in-progress and nothing is ready, we may be stuck
            # (all remaining objectives have unmet deps that will never be met).
            # Break to avoid an infinite loop.
            if not in_progress_tasks and not ready:
                logger.warning(
                    "[Orchestrator] No ready objectives and no in-progress tasks — "
                    "breaking execution loop (possible unresolvable dependencies)."
                )
                # Mark remaining PENDING objectives as SKIPPED
                for obj in opplan.list_objectives():
                    if str(obj.status) == ObjStatus.PENDING:
                        opplan.update_objective(obj.id, status=ObjStatus.SKIPPED)
                break

            # Wait for at least one task to complete before re-evaluating
            if in_progress_tasks:
                done, _ = await asyncio.wait(
                    list(in_progress_tasks.values()),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    # Find the obj_id for this task
                    obj_id = next(
                        oid for oid, t in in_progress_tasks.items() if t is task
                    )
                    del in_progress_tasks[obj_id]

                    if obj_id in self._current_objectives:
                        self._current_objectives.remove(obj_id)

                    try:
                        result: AgentResult = task.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "[Orchestrator] Task for objective %s raised: %s",
                            obj_id,
                            exc,
                        )
                        result = AgentResult(
                            success=False,
                            agent_name="unknown",
                            objective_id=obj_id,
                            errors=[str(exc)],
                        )

                    results[obj_id] = result

                    if result.success:
                        opplan.mark_complete(obj_id, {"findings": result.findings})
                        self._completed.append(obj_id)
                        logger.info(
                            "[Orchestrator] Objective %s completed successfully.", obj_id
                        )

                        # AI-driven dynamic objective expansion (Req 9.3)
                        try:
                            new_objs = await self.ai_decide_next(opplan, result)
                            for new_obj in new_objs:
                                try:
                                    opplan.add_objective(new_obj)
                                    logger.info(
                                        "[Orchestrator] AI added new objective: %s (%s)",
                                        new_obj.id,
                                        new_obj.title,
                                    )
                                except ValueError as ve:
                                    logger.warning(
                                        "[Orchestrator] Could not add AI objective %s: %s",
                                        new_obj.id,
                                        ve,
                                    )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "[Orchestrator] ai_decide_next raised: %s", exc
                            )
                    else:
                        # Mark failed and continue (Req 9.4)
                        error_msg = "; ".join(result.errors) if result.errors else "unknown error"
                        opplan.mark_failed(obj_id, error_msg)
                        self._failed.append(obj_id)
                        logger.warning(
                            "[Orchestrator] Objective %s failed: %s", obj_id, error_msg
                        )
            else:
                # Nothing in-progress, nothing ready — already handled above
                await asyncio.sleep(0.1)

        self._status = "complete"
        logger.info(
            "[Orchestrator] OPPLAN complete. completed=%d failed=%d",
            len(self._completed),
            len(self._failed),
        )

        return {
            "engagement_id": opplan.engagement_id,
            "results": {oid: self._agent_result_to_dict(r) for oid, r in results.items()},
            "completed_count": len(self._completed),
            "failed_count": len(self._failed),
        }

    async def _run_agent(self, agent: BaseAgent, objective: Objective) -> AgentResult:
        """
        Run an agent's run() method, handling both sync and async implementations.
        """
        try:
            result = agent.run(objective)
            # If the agent returned a coroutine (async run), await it
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[Orchestrator] Agent %s raised during run(): %s", agent.name, exc
            )
            return AgentResult(
                success=False,
                agent_name=agent.name,
                objective_id=objective.id,
                errors=[str(exc)],
            )

    # ------------------------------------------------------------------
    # Autonomous attack
    # ------------------------------------------------------------------

    async def autonomous_attack(
        self,
        target: str,
        roe_config=None,
    ) -> Dict[str, Any]:
        """
        Full autonomous attack flow:
        1. Generate OPPLAN via AI (or create a default one if AI unavailable).
        2. Display the plan to the operator.
        3. Wait for approval (input() prompt, default yes).
        4. Execute the OPPLAN.
        5. Export KG and generate report.
        6. Return result dict.

        Requirements: 10.1–10.7
        """
        logger.info("[Orchestrator] autonomous_attack() called for target: %s", target)

        # 1. Generate OPPLAN
        opplan = await self._generate_opplan(target, roe_config)

        # 2. Display to operator
        print("\n" + "=" * 60)
        print("  PHANTOM STRIKE — OPERATIONAL PLAN")
        print("=" * 60)
        print(f"  Engagement ID : {opplan.engagement_id}")
        print(f"  Target        : {opplan.target}")
        print(f"  Objectives    : {len(opplan.list_objectives())}")
        print("-" * 60)
        for obj in opplan.list_objectives():
            print(f"  [{obj.phase:>12}] {obj.id} — {obj.title}")
            if obj.dependencies:
                print(f"               deps: {', '.join(obj.dependencies)}")
        print("=" * 60)

        # 3. Operator approval
        try:
            answer = input("\nApprove this OPPLAN and begin execution? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "y"

        if answer in ("n", "no"):
            print("[Orchestrator] OPPLAN rejected by operator. Aborting.")
            logger.info("[Orchestrator] OPPLAN rejected by operator.")
            return {
                "engagement_id": opplan.engagement_id,
                "opplan_path": None,
                "results": {},
                "kg_export_path": None,
                "report_path": None,
                "status": "rejected",
            }

        # Save OPPLAN
        opplan_path: Optional[str] = None
        try:
            opplan_path = opplan.save()
            logger.info("[Orchestrator] OPPLAN saved to %s", opplan_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Orchestrator] Could not save OPPLAN: %s", exc)

        # 4. Execute
        exec_result = await self.execute_opplan(opplan)

        # 5. Export KG
        kg_export_path: Optional[str] = None
        if self._knowledge_graph is not None:
            try:
                kg_data = self._knowledge_graph.export_to_json()
                import os
                import json as _json
                kg_dir = os.path.expanduser("~/.phantom-strike")
                os.makedirs(kg_dir, exist_ok=True)
                kg_export_path = os.path.join(kg_dir, f"kg_{opplan.engagement_id}.json")
                with open(kg_export_path, "w", encoding="utf-8") as fh:
                    _json.dump(kg_data, fh, indent=2, default=str)
                logger.info("[Orchestrator] KG exported to %s", kg_export_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Orchestrator] KG export failed: %s", exc)

        # 6. Report path (placeholder — ReportAgent writes the actual report)
        report_path: Optional[str] = None
        for obj_id, result_dict in exec_result.get("results", {}).items():
            findings = result_dict.get("findings", [])
            for finding in findings:
                if finding.get("type") == "report":
                    report_path = finding.get("path")
                    break

        return {
            "engagement_id": opplan.engagement_id,
            "opplan_path": opplan_path,
            "results": exec_result.get("results", {}),
            "kg_export_path": kg_export_path,
            "report_path": report_path,
        }

    async def _generate_opplan(self, target: str, roe_config=None) -> OPPLAN:
        """
        Generate an OPPLAN via AI, or create a sensible default if AI is
        unavailable.
        """
        engagement_id = str(uuid.uuid4())[:12]
        opplan = OPPLAN(engagement_id=engagement_id, target=target)

        if self._ai_engine is not None:
            try:
                prompt = (
                    f"Generate a comprehensive penetration testing OPPLAN for target: {target}.\n"
                    "Return a JSON array of objectives with fields: id, title, description, "
                    "phase (recon/scan/exploit/post_exploit/lateral_move/exfil/cleanup/report), "
                    "dependencies (list of ids).\n"
                    "Start with recon, then scan, then exploit, etc."
                )
                context: Dict[str, Any] = {
                    "target": target,
                    "roe": str(roe_config) if roe_config else "default",
                }
                context_json = json.dumps(context, default=str)
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are PhantomStrike AI. Generate structured OPPLAN JSON. "
                            f"Context: {context_json}"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]

                if hasattr(self._ai_engine, "chat"):
                    response_text = await self._ai_engine.chat(messages)
                elif hasattr(self._ai_engine, "query"):
                    response_text = await self._ai_engine.query(prompt=prompt, system_prompt=messages[0]["content"])
                else:
                    response_text = None

                if response_text:
                    opplan = self._parse_ai_opplan(response_text, target, engagement_id)
                    logger.info("[Orchestrator] AI-generated OPPLAN with %d objectives.", len(opplan.list_objectives()))
                    return opplan
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Orchestrator] AI OPPLAN generation failed: %s — using default.", exc)

        # Default OPPLAN when AI is unavailable
        return self._default_opplan(target, engagement_id)

    def _parse_ai_opplan(
        self, response_text: str, target: str, engagement_id: str
    ) -> OPPLAN:
        """
        Parse AI-generated JSON into an OPPLAN.  Falls back to default on any
        parse error.
        """
        opplan = OPPLAN(engagement_id=engagement_id, target=target)
        try:
            # Extract JSON array from the response (may be wrapped in markdown)
            text = response_text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON array found in AI response.")
            objectives_data = json.loads(text[start:end])

            for obj_data in objectives_data:
                obj = Objective(
                    id=str(obj_data.get("id", str(uuid.uuid4())[:8])),
                    title=str(obj_data.get("title", "Unnamed objective")),
                    description=str(obj_data.get("description", "")),
                    phase=str(obj_data.get("phase", ObjPhase.RECON)),
                    dependencies=list(obj_data.get("dependencies", [])),
                )
                try:
                    opplan.add_objective(obj)
                except ValueError as ve:
                    logger.warning("[Orchestrator] Skipping AI objective %s: %s", obj.id, ve)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Orchestrator] Failed to parse AI OPPLAN: %s — using default.", exc)
            return self._default_opplan(target, engagement_id)

        if not opplan.list_objectives():
            return self._default_opplan(target, engagement_id)

        return opplan

    def _default_opplan(self, target: str, engagement_id: str) -> OPPLAN:
        """
        Create a sensible default OPPLAN covering the standard attack lifecycle.
        """
        opplan = OPPLAN(engagement_id=engagement_id, target=target)

        objectives = [
            Objective(
                id="obj_recon",
                title="Reconnaissance",
                description=f"Passive and active reconnaissance of {target}",
                phase=ObjPhase.RECON,
                dependencies=[],
            ),
            Objective(
                id="obj_scan",
                title="Port and Service Scan",
                description=f"Enumerate open ports and services on {target}",
                phase=ObjPhase.SCAN,
                dependencies=["obj_recon"],
            ),
            Objective(
                id="obj_exploit",
                title="Exploitation",
                description="Exploit discovered vulnerabilities",
                phase=ObjPhase.EXPLOIT,
                dependencies=["obj_scan"],
            ),
            Objective(
                id="obj_post",
                title="Post-Exploitation",
                description="Establish persistence and gather credentials",
                phase=ObjPhase.POST_EXPLOIT,
                dependencies=["obj_exploit"],
            ),
            Objective(
                id="obj_report",
                title="Report Generation",
                description="Generate final engagement report",
                phase=ObjPhase.REPORT,
                dependencies=["obj_post"],
            ),
        ]

        for obj in objectives:
            opplan.add_objective(obj)

        return opplan

    # ------------------------------------------------------------------
    # Operator control
    # ------------------------------------------------------------------

    def pause(self) -> None:
        """
        Pause objective dispatch.  In-progress objectives continue to completion.

        Requirements: 10.4
        """
        self._paused = True
        self._status = "paused"
        logger.info("[Orchestrator] Paused.")

    def resume(self) -> None:
        """
        Resume objective dispatch after a pause.

        Requirements: 10.5
        """
        self._paused = False
        if self._status == "paused":
            self._status = "running"
        logger.info("[Orchestrator] Resumed.")

    def override_objective(self, obj_id: str, **kwargs: Any) -> None:
        """
        Apply an override to an objective in the current OPPLAN.

        Supported kwargs:
        - status: new status string (e.g. "skipped", "completed")
        - action: "skip" | "retry" | "force_complete"
        - Any other Objective field to update directly.

        Requirements: 10.6
        """
        if self._opplan is None:
            logger.warning("[Orchestrator] override_objective called but no OPPLAN is active.")
            return

        # Handle convenience action shortcuts
        action = kwargs.pop("action", None)
        if action == "skip":
            kwargs["status"] = ObjStatus.SKIPPED
        elif action == "force_complete":
            kwargs["status"] = ObjStatus.COMPLETED
        elif action == "retry":
            kwargs["status"] = ObjStatus.PENDING

        try:
            self._opplan.update_objective(obj_id, **kwargs)
            logger.info("[Orchestrator] Override applied to objective %s: %s", obj_id, kwargs)
        except (KeyError, AttributeError) as exc:
            logger.warning("[Orchestrator] override_objective failed for %s: %s", obj_id, exc)

    # ------------------------------------------------------------------
    # AI-driven dynamic objective expansion
    # ------------------------------------------------------------------

    async def ai_decide_next(
        self, opplan: OPPLAN, last_result: AgentResult
    ) -> List[Objective]:
        """
        Query the AI with the current KG state and OPPLAN state to decide
        whether new objectives should be added.

        Returns a list of new Objective instances to add to the OPPLAN.
        Returns an empty list if AI is unavailable or returns nothing useful.

        Requirements: 9.3
        """
        if self._ai_engine is None:
            return []

        try:
            # Build context
            kg_state: Dict[str, Any] = {}
            if self._knowledge_graph is not None:
                try:
                    kg_state = {
                        "high_value_targets": self._knowledge_graph.get_high_value_targets(),
                        "attack_paths": self._knowledge_graph.get_attack_paths(),
                    }
                except Exception as exc:  # noqa: BLE001
                    logger.debug("[Orchestrator] KG state query failed: %s", exc)

            opplan_state = {
                "engagement_id": opplan.engagement_id,
                "target": opplan.target,
                "completed": [
                    obj.to_dict()
                    for obj in opplan.list_objectives()
                    if str(obj.status) == ObjStatus.COMPLETED
                ],
                "pending": [
                    obj.to_dict()
                    for obj in opplan.list_objectives()
                    if str(obj.status) == ObjStatus.PENDING
                ],
                "last_result": {
                    "agent": last_result.agent_name,
                    "objective_id": last_result.objective_id,
                    "success": last_result.success,
                    "findings_count": len(last_result.findings),
                },
            }

            prompt = (
                "Based on the current engagement state, should any new objectives be added? "
                "If yes, return a JSON array of new objectives with fields: "
                "id, title, description, phase, dependencies. "
                "If no new objectives are needed, return an empty array []."
            )
            context_json = json.dumps(
                {"kg_state": kg_state, "opplan_state": opplan_state},
                default=str,
                indent=2,
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are PhantomStrike AI. Analyse the engagement state and "
                        f"suggest new objectives if warranted.\n\nContext:\n{context_json}"
                    ),
                },
                {"role": "user", "content": prompt},
            ]

            if hasattr(self._ai_engine, "chat"):
                response_text = await self._ai_engine.chat(messages)
            elif hasattr(self._ai_engine, "query"):
                response_text = (await self._ai_engine.query(prompt=prompt, system_prompt=messages[0]["content"])).content
            else:
                return []

            if not response_text:
                return []

            # Parse JSON array from response
            text = str(response_text).strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start == -1 or end == 0:
                return []

            objectives_data = json.loads(text[start:end])
            new_objectives: List[Objective] = []
            for obj_data in objectives_data:
                obj = Objective(
                    id=str(obj_data.get("id", str(uuid.uuid4())[:8])),
                    title=str(obj_data.get("title", "AI-suggested objective")),
                    description=str(obj_data.get("description", "")),
                    phase=str(obj_data.get("phase", ObjPhase.RECON)),
                    dependencies=list(obj_data.get("dependencies", [])),
                )
                new_objectives.append(obj)

            return new_objectives

        except Exception as exc:  # noqa: BLE001
            logger.warning("[Orchestrator] ai_decide_next failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        Return a status dict describing the orchestrator's current state.

        Returns
        -------
        dict
            Keys: status, current_objectives, completed, failed
        """
        return {
            "status": self._status,
            "current_objectives": list(self._current_objectives),
            "completed": list(self._completed),
            "failed": list(self._failed),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _agent_result_to_dict(result: AgentResult) -> Dict[str, Any]:
        """Serialise an AgentResult to a plain dict for the results payload."""
        return {
            "agent_name": result.agent_name,
            "objective_id": result.objective_id,
            "success": result.success,
            "findings": result.findings,
            "errors": result.errors,
            "kg_updates": result.kg_updates,
            "mitre_techniques_used": result.mitre_techniques_used,
            "duration_seconds": result.duration_seconds,
            "raw_output": result.raw_output,
        }
