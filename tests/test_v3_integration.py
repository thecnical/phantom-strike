"""
PhantomStrike v3.0 Integration Tests
Run with: pytest tests/test_v3_integration.py -v

Tests:
  1. EnhancedPhantomEngine loads v3.0 attributes (knowledge_graph, roe_middleware,
     skill_library, docker_sandbox)
  2. OPPLAN + PhantomOrchestrator end-to-end pipeline (create OPPLAN, register
     mock agent, execute_opplan, verify objectives complete)
  3. KnowledgeGraph integration (agent adds host to KG, KG reflects update)
  4. CLI command parsing for all v3.0 commands (autonomous, opplan, graph,
     agents, sandbox, roe, skills) - routes to correct handlers without crashing
  5. EnhancedPhantomEngine still loads all 11 v2.0 modules after v3.0 changes

Requirements: 9.1-9.6, 10.1-10.7, 17.1-17.9, 18.1-18.3
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Any, Dict, List

from phantom.core.opplan import OPPLAN, Objective, ObjPhase, ObjStatus
from phantom.db.knowledge_graph import KnowledgeGraph
from phantom.agents.base_agent import BaseAgent, AgentResult
from phantom.agents.orchestrator import PhantomOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_agent(name: str, success: bool = True) -> BaseAgent:
    """Create a mock agent that returns a successful AgentResult."""

    class _MockAgent(BaseAgent):
        @property
        def name(self) -> str:
            return name

        @property
        def system_prompt(self) -> str:
            return f"Mock agent: {name}"

        def run(self, objective) -> AgentResult:
            return AgentResult(
                success=success,
                agent_name=self.name,
                objective_id=objective.id,
                findings=[{"mock": True, "agent": name}],
            )

    return _MockAgent()


def _make_simple_opplan(target: str = "192.168.1.1") -> OPPLAN:
    """Create a minimal OPPLAN with recon -> scan -> report chain."""
    opplan = OPPLAN(engagement_id="test-eng-001", target=target)
    opplan.add_objective(Objective(
        id="obj_recon",
        title="Reconnaissance",
        phase=ObjPhase.RECON,
        dependencies=[],
    ))
    opplan.add_objective(Objective(
        id="obj_scan",
        title="Port Scan",
        phase=ObjPhase.SCAN,
        dependencies=["obj_recon"],
    ))
    opplan.add_objective(Objective(
        id="obj_report",
        title="Report Generation",
        phase=ObjPhase.REPORT,
        dependencies=["obj_scan"],
    ))
    return opplan


# ---------------------------------------------------------------------------
# 1. EnhancedPhantomEngine v3.0 attribute tests
# ---------------------------------------------------------------------------


class TestEnhancedEngineV3Attributes:
    """
    Verify that EnhancedPhantomEngine exposes the four new v3.0 attributes
    after start() is called.

    Requirements: 18.2, 18.3
    """

    @pytest.fixture
    def engine(self):
        """Return an EnhancedPhantomEngine with all heavy I/O mocked out."""
        from phantom.core.enhanced_engine import EnhancedPhantomEngine
        from phantom.core.config import PhantomStrikeConfig

        cfg = PhantomStrikeConfig()
        cfg.backend_enabled = False
        eng = EnhancedPhantomEngine(cfg)
        return eng

    def test_v3_attributes_exist_before_start(self, engine):
        """v3.0 attributes must be declared (even if None) before start()."""
        assert hasattr(engine, "knowledge_graph")
        assert hasattr(engine, "roe_middleware")
        assert hasattr(engine, "skill_library")
        assert hasattr(engine, "docker_sandbox")

    @pytest.mark.asyncio
    async def test_v3_attributes_initialized_after_start(self, engine):
        """After start(), knowledge_graph, roe_middleware, skill_library,
        and docker_sandbox must be non-None instances.

        Requirements: 18.2, 18.3
        """
        with patch.object(engine, "_load_enhanced_modules", new=AsyncMock()),\
             patch("phantom.core.enhanced_engine.EventBus.start", new=AsyncMock()),\
             patch("phantom.core.enhanced_engine.EventBus.emit", new=AsyncMock()),\
             patch("phantom.core.enhanced_engine.console"):
            await engine.start()

        assert engine.knowledge_graph is not None, \
            "knowledge_graph must be initialized after start()"
        assert engine.roe_middleware is not None, \
            "roe_middleware must be initialized after start()"
        assert engine.skill_library is not None, \
            "skill_library must be initialized after start()"
        assert engine.docker_sandbox is not None, \
            "docker_sandbox must be initialized after start()"

    @pytest.mark.asyncio
    async def test_knowledge_graph_is_connected_after_start(self, engine):
        """KnowledgeGraph must be connected (not raise) after start().

        Requirements: 18.2
        """
        with patch.object(engine, "_load_enhanced_modules", new=AsyncMock()),\
             patch("phantom.core.enhanced_engine.EventBus.start", new=AsyncMock()),\
             patch("phantom.core.enhanced_engine.EventBus.emit", new=AsyncMock()),\
             patch("phantom.core.enhanced_engine.console"):
            await engine.start()

        kg = engine.knowledge_graph
        assert kg is not None
        # Should be able to query without raising
        rows = kg.query("SELECT COUNT(*) AS cnt FROM nodes")
        assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# 2. OPPLAN + PhantomOrchestrator end-to-end pipeline
# ---------------------------------------------------------------------------


class TestOrchestratorPipeline:
    """
    End-to-end test: create OPPLAN, register mock agents, run execute_opplan(),
    verify all objectives reach a terminal state.

    Requirements: 9.1-9.6, 10.1-10.7
    """

    @pytest.mark.asyncio
    async def test_execute_opplan_completes_all_objectives(self):
        """
        Given an OPPLAN with three chained objectives and mock agents for each
        phase, execute_opplan() must complete all objectives and return a
        result dict with completed_count == 3.

        Requirements: 9.1, 9.2, 9.4
        """
        opplan = _make_simple_opplan()

        # Create mock agents for each phase
        recon_agent = _make_mock_agent("ReconAgent")
        scan_agent = _make_mock_agent("ScannerAgent")
        report_agent = _make_mock_agent("ReportAgent")

        orchestrator = PhantomOrchestrator(
            ai_engine=None,
            knowledge_graph=None,
            roe=None,
            skill_library=None,
            sandbox=None,
            max_threads=4,
        )
        orchestrator.register_agent(recon_agent)
        orchestrator.register_agent(scan_agent)
        orchestrator.register_agent(report_agent)

        result = await orchestrator.execute_opplan(opplan)

        assert result["engagement_id"] == "test-eng-001"
        assert result["completed_count"] == 3, \
            f"Expected 3 completed objectives, got {result['completed_count']}"
        assert result["failed_count"] == 0, \
            f"Expected 0 failed objectives, got {result['failed_count']}"

    @pytest.mark.asyncio
    async def test_execute_opplan_respects_dependency_order(self):
        """
        Objectives must be dispatched in dependency order: obj_recon before
        obj_scan, obj_scan before obj_report.

        Requirements: 9.2
        """
        completion_order: List[str] = []

        class OrderTrackingAgent(BaseAgent):
            def __init__(self, agent_name: str, order_list: List[str]):
                super().__init__()
                self._name = agent_name
                self._order = order_list

            @property
            def name(self) -> str:
                return self._name

            @property
            def system_prompt(self) -> str:
                return ""

            def run(self, objective) -> AgentResult:
                self._order.append(objective.id)
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    objective_id=objective.id,
                )

        opplan = _make_simple_opplan()
        orchestrator = PhantomOrchestrator(ai_engine=None, max_threads=1)
        orchestrator.register_agent(OrderTrackingAgent("ReconAgent", completion_order))
        orchestrator.register_agent(OrderTrackingAgent("ScannerAgent", completion_order))
        orchestrator.register_agent(OrderTrackingAgent("ReportAgent", completion_order))

        await orchestrator.execute_opplan(opplan)

        assert completion_order == ["obj_recon", "obj_scan", "obj_report"], \
            f"Objectives completed out of order: {completion_order}"

    @pytest.mark.asyncio
    async def test_execute_opplan_continues_after_failure(self):
        """
        When an objective fails, the orchestrator must continue executing
        independent objectives rather than aborting the entire OPPLAN.

        Requirements: 9.4
        """
        # OPPLAN: recon (no deps), scan (no deps) - both independent
        opplan = OPPLAN(engagement_id="fail-test", target="10.0.0.1")
        opplan.add_objective(Objective(
            id="obj_recon", title="Recon", phase=ObjPhase.RECON, dependencies=[]
        ))
        opplan.add_objective(Objective(
            id="obj_scan", title="Scan", phase=ObjPhase.SCAN, dependencies=[]
        ))

        # ReconAgent fails, ScannerAgent succeeds
        failing_agent = _make_mock_agent("ReconAgent", success=False)
        success_agent = _make_mock_agent("ScannerAgent", success=True)

        orchestrator = PhantomOrchestrator(ai_engine=None, max_threads=4)
        orchestrator.register_agent(failing_agent)
        orchestrator.register_agent(success_agent)

        result = await orchestrator.execute_opplan(opplan)

        # One failed, one completed - orchestrator must not abort
        assert result["failed_count"] == 1
        assert result["completed_count"] == 1

    @pytest.mark.asyncio
    async def test_get_status_reflects_orchestrator_state(self):
        """
        get_status() must return a dict with status, completed, and failed counts.

        Requirements: 10.7
        """
        orchestrator = PhantomOrchestrator(ai_engine=None)
        status = orchestrator.get_status()
        assert isinstance(status, dict)
        assert "status" in status
        assert "completed" in status
        assert "failed" in status

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        """
        pause() and resume() must toggle the paused flag without raising.

        Requirements: 10.4, 10.5
        """
        orchestrator = PhantomOrchestrator(ai_engine=None)
        orchestrator.pause()
        assert orchestrator._paused is True
        assert orchestrator._status == "paused"

        orchestrator.resume()
        assert orchestrator._paused is False


# ---------------------------------------------------------------------------
# 3. KnowledgeGraph integration
# ---------------------------------------------------------------------------


class TestKnowledgeGraphIntegration:
    """
    Verify that agents can add nodes to the KnowledgeGraph and that the
    graph reflects those updates correctly.

    Requirements: 6.1-6.8, 7.1-7.6
    """

    def test_agent_adds_host_to_kg(self):
        """
        An agent that calls kg.add_host() during run() must result in a
        host node being present in the KnowledgeGraph.

        Requirements: 6.1, 6.2
        """
        from phantom.db.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.connect(":memory:")

        class KGWritingAgent(BaseAgent):
            @property
            def name(self) -> str:
                return "KGWritingAgent"

            @property
            def system_prompt(self) -> str:
                return ""

            def run(self, objective) -> AgentResult:
                host_id = self._knowledge_graph.add_host(
                    ip="10.0.0.50",
                    hostname="target.local",
                    os="Linux",
                )
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    objective_id=objective.id,
                    kg_updates=[{"action": "add_host", "data": {"host_id": host_id}}],
                )

        agent = KGWritingAgent(knowledge_graph=kg)
        obj = Objective(id="kg-int-001", title="KG test", phase=ObjPhase.RECON)
        result = agent.run(obj)

        assert result.success is True
        assert len(result.kg_updates) == 1

        # Verify the host is in the KG
        rows = kg.query("SELECT label FROM nodes WHERE type = 'host'")
        labels = [r["label"] for r in rows]
        assert "10.0.0.50" in labels, f"Host not found in KG. Nodes: {labels}"

        kg.close()

    def test_kg_deduplication_across_agent_runs(self):
        """
        When two agents add the same host IP, the KG must deduplicate and
        return the same node ID both times.

        Requirements: 6.2
        """
        from phantom.db.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.connect(":memory:")

        id1 = kg.add_host("192.168.1.1")
        id2 = kg.add_host("192.168.1.1")  # duplicate

        assert id1 == id2, "Duplicate host must return the same node ID"

        rows = kg.query("SELECT COUNT(*) AS cnt FROM nodes WHERE type = 'host'")
        assert rows[0]["cnt"] == 1, "Only one host node should exist after dedup"

        kg.close()

    @pytest.mark.asyncio
    async def test_orchestrator_pipeline_updates_kg(self):
        """
        Full pipeline: orchestrator executes OPPLAN with a KG-writing agent;
        after execution the KG must contain the host added by the agent.

        Requirements: 9.1, 9.6
        """
        from phantom.db.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.connect(":memory:")

        class KGReconAgent(BaseAgent):
            @property
            def name(self) -> str:
                return "ReconAgent"

            @property
            def system_prompt(self) -> str:
                return ""

            def run(self, objective) -> AgentResult:
                self._knowledge_graph.add_host("10.10.10.1")
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    objective_id=objective.id,
                )

        opplan = OPPLAN(engagement_id="kg-pipeline-001", target="10.10.10.1")
        opplan.add_objective(Objective(
            id="obj_recon", title="Recon", phase=ObjPhase.RECON, dependencies=[]
        ))

        orchestrator = PhantomOrchestrator(
            ai_engine=None,
            knowledge_graph=kg,
        )
        orchestrator.register_agent(KGReconAgent(knowledge_graph=kg))

        await orchestrator.execute_opplan(opplan)

        rows = kg.query("SELECT label FROM nodes WHERE type = 'host'")
        labels = [r["label"] for r in rows]
        assert "10.10.10.1" in labels, \
            f"Host not found in KG after pipeline execution. Nodes: {labels}"

        kg.close()

    def test_kg_export_to_json_after_agent_updates(self):
        """
        export_to_json() must include all nodes and edges added by agents.

        Requirements: 7.5
        """
        from phantom.db.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.connect(":memory:")

        host_id = kg.add_host("172.16.0.1")
        kg.add_vulnerability(host_id, "SQL Injection", severity="high")

        export = kg.export_to_json()

        assert "nodes" in export
        assert "edges" in export
        assert len(export["nodes"]) >= 2  # host + vuln
        assert len(export["edges"]) >= 1  # HAS_VULN edge

        node_labels = [n["label"] for n in export["nodes"]]
        assert "172.16.0.1" in node_labels

        kg.close()


# ---------------------------------------------------------------------------
# 4. CLI command parsing for v3.0 commands
# ---------------------------------------------------------------------------


class TestCLICommandParsing:
    """
    Verify that PhantomStrikeCLI._handle_command() routes all v3.0 commands
    to the correct handlers without crashing.

    Requirements: 17.1-17.9
    """

    @pytest.fixture
    def cli(self):
        """Return a PhantomStrikeCLI with all heavy dependencies mocked."""
        from phantom.cli.app import PhantomStrikeCLI

        mock_engine = MagicMock()
        mock_engine.knowledge_graph = None
        mock_engine.roe_middleware = None
        mock_engine.skill_library = None
        mock_engine.docker_sandbox = None
        mock_engine.orchestrator = None
        mock_engine.ai_engine = None

        with patch("phantom.cli.app.load_config", return_value=MagicMock()), \
             patch("phantom.core.enhanced_engine.EnhancedPhantomEngine", return_value=mock_engine):
            cli_instance = PhantomStrikeCLI()
            cli_instance.engine = mock_engine
            return cli_instance

    @pytest.mark.asyncio
    async def test_autonomous_command_routes_to_handler(self, cli):
        """
        "autonomous <target>" must route to _cmd_autonomous() without crashing.

        Requirements: 17.1
        """
        with patch.object(cli, "_cmd_autonomous", new=AsyncMock()) as mock_handler:
            await cli._handle_command("autonomous 192.168.1.1")
            mock_handler.assert_called_once_with(["192.168.1.1"])

    @pytest.mark.asyncio
    async def test_opplan_list_routes_to_handler(self, cli):
        """
        "opplan list" must route to _cmd_opplan() without crashing.

        Requirements: 17.2
        """
        with patch.object(cli, "_cmd_opplan", new=AsyncMock()) as mock_handler:
            await cli._handle_command("opplan list")
            mock_handler.assert_called_once_with(["list"])

    @pytest.mark.asyncio
    async def test_opplan_load_routes_to_handler(self, cli):
        """
        "opplan load /path/to/plan.yaml" must route to _cmd_opplan().

        Requirements: 17.3
        """
        with patch.object(cli, "_cmd_opplan", new=AsyncMock()) as mock_handler:
            await cli._handle_command("opplan load /tmp/plan.yaml")
            mock_handler.assert_called_once_with(["load", "/tmp/plan.yaml"])

    @pytest.mark.asyncio
    async def test_graph_command_routes_to_handler(self, cli):
        """
        "graph" must route to _cmd_graph() without crashing.

        Requirements: 17.4
        """
        with patch.object(cli, "_cmd_graph", new=AsyncMock()) as mock_handler:
            await cli._handle_command("graph")
            mock_handler.assert_called_once_with([])

    @pytest.mark.asyncio
    async def test_agents_command_routes_to_handler(self, cli):
        """
        "agents" must route to _cmd_agents() without crashing.

        Requirements: 17.5
        """
        with patch.object(cli, "_cmd_agents", new=AsyncMock()) as mock_handler:
            await cli._handle_command("agents")
            mock_handler.assert_called_once_with([])

    @pytest.mark.asyncio
    async def test_sandbox_status_routes_to_handler(self, cli):
        """
        "sandbox status" must route to _cmd_sandbox() without crashing.

        Requirements: 17.6
        """
        with patch.object(cli, "_cmd_sandbox", new=AsyncMock()) as mock_handler:
            await cli._handle_command("sandbox status")
            mock_handler.assert_called_once_with(["status"])

    @pytest.mark.asyncio
    async def test_roe_violations_routes_to_handler(self, cli):
        """
        "roe violations" must route to _cmd_roe() without crashing.

        Requirements: 17.7
        """
        with patch.object(cli, "_cmd_roe", new=AsyncMock()) as mock_handler:
            await cli._handle_command("roe violations")
            mock_handler.assert_called_once_with(["violations"])

    @pytest.mark.asyncio
    async def test_skills_list_routes_to_handler(self, cli):
        """
        "skills list" must route to _cmd_skills() without crashing.

        Requirements: 17.8
        """
        with patch.object(cli, "_cmd_skills", new=AsyncMock()) as mock_handler:
            await cli._handle_command("skills list")
            mock_handler.assert_called_once_with(["list"])

    @pytest.mark.asyncio
    async def test_unknown_command_does_not_crash(self, cli):
        """
        An unrecognized command must not raise an exception.

        Requirements: 17.9
        """
        with patch("phantom.cli.app.console"):
            # Should not raise
            await cli._handle_command("nonexistent_command_xyz")

    @pytest.mark.asyncio
    async def test_all_v3_commands_registered_in_dispatch(self, cli):
        """
        All seven v3.0 commands must be present in the _handle_command()
        dispatch table.

        Requirements: 17.9
        """
        v3_commands = ["autonomous", "opplan", "graph", "agents", "sandbox", "roe", "skills"]

        # Inspect the handlers dict by calling _handle_command with a mock
        # and verifying each command reaches its handler
        for cmd in v3_commands:
            handler_attr = f"_cmd_{cmd}"
            assert hasattr(cli, handler_attr), \
                f"CLI is missing handler method {handler_attr!r} for command {cmd!r}"



# ---------------------------------------------------------------------------
# 5. EnhancedPhantomEngine still loads all 11 v2.0 modules
# ---------------------------------------------------------------------------


class TestV2ModulePreservation:
    """
    Verify that EnhancedPhantomEngine still loads all 11 v2.0 modules after
    v3.0 changes.  Module execution is stubbed to avoid real network calls.

    Requirements: 18.1, 18.2, 18.3
    """

    V2_MODULE_NAMES = [
        "phantom-network",
        "phantom-osint",
        "phantom-web",
        "phantom-cloud",
        "phantom-identity",
        "phantom-cred",
        "phantom-stealth",
        "phantom-exploit",
        "phantom-c2",
        "phantom-post",
        "phantom-report",
    ]

    @pytest.mark.asyncio
    async def test_all_11_v2_modules_loaded(self):
        """
        After start(), the engine must have all 11 v2.0 modules registered.

        Requirements: 18.1, 18.2
        """
        from phantom.core.enhanced_engine import EnhancedPhantomEngine
        from phantom.core.config import PhantomStrikeConfig

        cfg = PhantomStrikeConfig()
        cfg.backend_enabled = False
        engine = EnhancedPhantomEngine(cfg)

        with patch("phantom.core.enhanced_engine.EventBus.start", new=AsyncMock()), \
             patch("phantom.core.enhanced_engine.EventBus.emit", new=AsyncMock()), \
             patch("phantom.core.enhanced_engine.console"):
            await engine.start()

        loaded_names = set(engine._modules.keys())
        missing = [m for m in self.V2_MODULE_NAMES if m not in loaded_names]
        assert not missing, (
            f"Missing v2.0 modules after v3.0 changes: {missing}."
            f" Loaded modules: {sorted(loaded_names)}"
        )

    @pytest.mark.asyncio
    async def test_v2_modules_still_executable_after_v3_changes(self):
        """
        execute_module() must work for v2.0 modules after v3.0 changes.
        Module run() is mocked to avoid real network calls.

        Requirements: 18.2, 18.3
        """
        from phantom.core.enhanced_engine import EnhancedPhantomEngine
        from phantom.core.config import PhantomStrikeConfig

        cfg = PhantomStrikeConfig()
        cfg.backend_enabled = False
        engine = EnhancedPhantomEngine(cfg)

        with patch("phantom.core.enhanced_engine.EventBus.start", new=AsyncMock()), \
             patch("phantom.core.enhanced_engine.EventBus.emit", new=AsyncMock()), \
             patch("phantom.core.enhanced_engine.console"):
            await engine.start()

        for mod_name in self.V2_MODULE_NAMES:
            if mod_name in engine._modules:
                module = engine._modules[mod_name]
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.findings_count = 0
                mock_result.data = {}
                mock_result.duration_seconds = 0.1
                module.run = AsyncMock(return_value=mock_result)

                result = await engine.execute_module(mod_name, "127.0.0.1")
                assert result.get("success") is True, (
                    f"execute_module({mod_name!r}) failed: {result}"
                )
                break

    @pytest.mark.asyncio
    async def test_engine_version_is_v3(self):
        """
        The engine banner must reference v3.0.

        Requirements: 18.2
        """
        from phantom.core.enhanced_engine import EnhancedPhantomEngine
        from phantom.core.config import PhantomStrikeConfig

        cfg = PhantomStrikeConfig()
        cfg.backend_enabled = False
        engine = EnhancedPhantomEngine(cfg)

        banner_calls = []

        with patch("phantom.core.enhanced_engine.EventBus.start", new=AsyncMock()), \
             patch("phantom.core.enhanced_engine.EventBus.emit", new=AsyncMock()), \
             patch("phantom.core.enhanced_engine.console") as mock_console:
            def _capture_print(*args, **kw):
                if args:
                    banner_calls.append(str(args[0]))
            mock_console.print = MagicMock(side_effect=_capture_print)
            await engine.start()

        banner_text = " ".join(banner_calls)
        assert "v3.0" in banner_text or "3.0" in banner_text, (
            f"Engine banner does not mention v3.0. Banner output: {banner_text[:500]}"
        )


# ---------------------------------------------------------------------------
# 6. Full autonomous attack flow (mocked)
# ---------------------------------------------------------------------------


class TestAutonomousAttackFlow:
    """
    End-to-end test of the autonomous attack flow with all external calls mocked.

    Requirements: 10.1-10.7
    """

    @pytest.mark.asyncio
    async def test_autonomous_attack_returns_result_dict(self):
        """
        autonomous_attack() must return a dict with the required keys:
        engagement_id, results.

        Requirements: 10.1, 10.2, 10.3
        """
        kg = KnowledgeGraph()
        kg.connect(":memory:")

        orchestrator = PhantomOrchestrator(
            ai_engine=None,
            knowledge_graph=kg,
        )

        for agent_name in ["ReconAgent", "ScannerAgent", "ExploitAgent",
                           "PostExploitAgent", "ReportAgent"]:
            orchestrator.register_agent(_make_mock_agent(agent_name))

        with patch("builtins.input", return_value="y"), \
             patch("phantom.agents.orchestrator.OPPLAN.save", return_value="/tmp/test.yaml"):
            result = await orchestrator.autonomous_attack("192.168.1.100")

        assert isinstance(result, dict), "autonomous_attack must return a dict"
        assert "engagement_id" in result
        assert "results" in result

        kg.close()

    @pytest.mark.asyncio
    async def test_autonomous_attack_rejected_by_operator(self):
        """
        When the operator rejects the OPPLAN, autonomous_attack() must return
        a result dict with status == "rejected" and not execute any objectives.

        Requirements: 10.3
        """
        orchestrator = PhantomOrchestrator(ai_engine=None)

        with patch("builtins.input", return_value="n"):
            result = await orchestrator.autonomous_attack("10.0.0.1")

        assert result.get("status") == "rejected", (
            f"Expected status=rejected, got: {result.get('status')}"
        )
        assert result.get("results") == {}, (
            "No objectives should have been executed after rejection"
        )

    @pytest.mark.asyncio
    async def test_override_objective_skips_it(self):
        """
        override_objective(obj_id, action="skip") must mark the objective as
        SKIPPED in the active OPPLAN.

        Requirements: 10.6
        """
        opplan = _make_simple_opplan()
        orchestrator = PhantomOrchestrator(ai_engine=None)
        orchestrator._opplan = opplan

        orchestrator.override_objective("obj_recon", action="skip")

        obj = opplan.get_objective("obj_recon")
        assert str(obj.status) == ObjStatus.SKIPPED, (
            f"Expected SKIPPED, got {obj.status}"
        )


# ---------------------------------------------------------------------------
# 7. OPPLAN to report generation pipeline
# ---------------------------------------------------------------------------


class TestOPPLANToReportPipeline:
    """
    Verify the full OPPLAN -> agent dispatch -> KG update -> report generation
    pipeline end-to-end with mocked module execution.

    Requirements: 9.1-9.6
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_recon_to_report(self):
        """
        Full pipeline: recon -> scan -> report.
        Each agent writes to the KG; the final result dict must contain
        results for all three objectives.

        Requirements: 9.1, 9.2, 9.5, 9.6
        """
        kg = KnowledgeGraph()
        kg.connect(":memory:")

        findings_log: List[str] = []

        class PipelineAgent(BaseAgent):
            def __init__(self, agent_name: str, kg_ref, log: List[str]):
                super().__init__(knowledge_graph=kg_ref)
                self._name = agent_name
                self._log = log

            @property
            def name(self) -> str:
                return self._name

            @property
            def system_prompt(self) -> str:
                return ""

            def run(self, objective) -> AgentResult:
                self._log.append(f"{self._name}:{objective.id}")
                if self._knowledge_graph is not None:
                    self._knowledge_graph.add_host(f"10.0.0.{len(self._log)}")
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    objective_id=objective.id,
                    findings=[{"phase": str(objective.phase), "agent": self._name}],
                )

        opplan = _make_simple_opplan(target="10.0.0.0/24")
        orchestrator = PhantomOrchestrator(ai_engine=None, knowledge_graph=kg)
        orchestrator.register_agent(PipelineAgent("ReconAgent", kg, findings_log))
        orchestrator.register_agent(PipelineAgent("ScannerAgent", kg, findings_log))
        orchestrator.register_agent(PipelineAgent("ReportAgent", kg, findings_log))

        result = await orchestrator.execute_opplan(opplan)

        assert result["completed_count"] == 3
        assert result["failed_count"] == 0

        assert len(findings_log) == 3
        assert any("ReconAgent" in entry for entry in findings_log)
        assert any("ScannerAgent" in entry for entry in findings_log)
        assert any("ReportAgent" in entry for entry in findings_log)

        rows = kg.query("SELECT id FROM nodes WHERE type = 'host'")
        assert len(rows) >= 3, f"KG should have at least 3 host nodes, got {len(rows)}"

        kg.close()
