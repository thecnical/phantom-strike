"""
PhantomStrike v3.0 — BaseAgent Property Tests
Run with: pytest tests/test_v3_agents.py -v

Includes:
  - Property 4: Agent Context Isolation (task 3.2)

Requirements: 8.1, 8.2
"""

import pytest
from hypothesis import given, assume, settings
import hypothesis.strategies as st
from typing import List, Dict, Any

from phantom.agents.base_agent import BaseAgent, AgentResult
from phantom.core.opplan import Objective, ObjPhase, ObjStatus


# ─── Test Agent Implementation ────────────────────────────────────────────────

class RecordingTestAgent(BaseAgent):
    """
    Concrete test agent that records all AI calls made during execution.
    
    This agent captures the messages list passed to the AI engine for each
    objective, allowing us to verify context isolation between runs.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # List of all message lists sent to AI, one per run() call
        self.ai_call_history: List[List[Dict[str, Any]]] = []
    
    @property
    def name(self) -> str:
        return "RecordingTestAgent"
    
    @property
    def system_prompt(self) -> str:
        return "Test agent for context isolation verification."
    
    def run(self, objective: Objective) -> AgentResult:
        """
        Execute the objective and record the AI call.
        
        This implementation calls _query_ai() which will construct a fresh
        message list. We intercept and record that message list to verify
        isolation.
        """
        # Build a fresh context for this objective
        context = {
            "objective_id": objective.id,
            "objective_title": objective.title,
            "phase": objective.phase,
        }
        
        # Query the AI - this will construct a fresh message list
        prompt = f"Execute objective: {objective.title}"
        response = self._query_ai(context, prompt)
        
        # Return a successful result
        return AgentResult(
            success=True,
            agent_name=self.name,
            objective_id=objective.id,
            findings=[{"response": response}],
        )


class MockAIEngine:
    """
    Mock AI engine that records all message lists it receives.
    
    This allows us to inspect what messages were sent to the AI for each
    objective execution.
    """
    
    def __init__(self, recording_agent: RecordingTestAgent):
        self.recording_agent = recording_agent
    
    def chat(self, messages: List[Dict[str, Any]]) -> str:
        """
        Record the messages list and return a simple response.
        
        The messages list is what we need to inspect to verify context
        isolation - it should contain no history from previous objectives.
        """
        # Record this call's message list
        self.recording_agent.ai_call_history.append(messages)
        
        # Return a simple response
        return f"Executed with {len(messages)} messages"


# ─── Strategies ───────────────────────────────────────────────────────────────

# Strategy for generating objective prompts/titles
objective_title_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters="-_"),
    min_size=5,
    max_size=50,
)

# Strategy for generating objective IDs
objective_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=4,
    max_size=12,
)


# ─── Property 4: Agent Context Isolation ──────────────────────────────────────
# Validates: Requirements 8.1, 8.2
#
# When a BaseAgent runs multiple objectives, each run() call MUST use a fresh
# context with NO conversation history from previous objectives. The messages
# list sent to the AI for objective N+1 must NOT contain any user/assistant
# messages from objective N.

@given(
    obj1_id=objective_id_strategy,
    obj1_title=objective_title_strategy,
    obj2_id=objective_id_strategy,
    obj2_title=objective_title_strategy,
)
@settings(max_examples=200)
def test_agent_context_isolation(
    obj1_id: str,
    obj1_title: str,
    obj2_id: str,
    obj2_title: str,
):
    """
    **Validates: Requirements 8.1, 8.2**

    Property 4: Agent Context Isolation

    For any two distinct objectives executed by the same agent instance:
    1. The AI messages for objective 2 MUST NOT contain any content from
       objective 1's conversation
    2. Each run() call constructs a fresh context dict
    3. No cross-objective memory leakage occurs

    This test:
    - Creates a concrete test agent that records all AI calls
    - Runs it with two different objectives
    - Asserts that the messages sent to the AI for objective 2 contain
      NO content from objective 1's conversation
    """
    # Ensure the two objectives are distinct
    assume(obj1_id != obj2_id)
    assume(obj1_title != obj2_title)
    
    # Create the recording agent with a mock AI engine
    agent = RecordingTestAgent(
        ai_engine=None,  # Will be set below
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    )
    
    # Create and attach the mock AI engine
    mock_ai = MockAIEngine(agent)
    agent._ai_engine = mock_ai
    
    # Create two distinct objectives
    objective1 = Objective(
        id=obj1_id,
        title=obj1_title,
        phase=ObjPhase.RECON,
        status=ObjStatus.PENDING,
    )
    
    objective2 = Objective(
        id=obj2_id,
        title=obj2_title,
        phase=ObjPhase.SCAN,
        status=ObjStatus.PENDING,
    )
    
    # Run objective 1
    result1 = agent.run(objective1)
    assert result1.success, "Objective 1 should complete successfully"
    
    # Run objective 2
    result2 = agent.run(objective2)
    assert result2.success, "Objective 2 should complete successfully"
    
    # Verify we recorded exactly 2 AI calls
    assert len(agent.ai_call_history) == 2, (
        f"Expected 2 AI calls (one per objective), got {len(agent.ai_call_history)}"
    )
    
    messages_obj1 = agent.ai_call_history[0]
    messages_obj2 = agent.ai_call_history[1]
    
    # Extract all content from objective 1's messages
    obj1_content = set()
    for msg in messages_obj1:
        if "content" in msg:
            obj1_content.add(msg["content"])
    
    # Verify objective 2's messages contain NO content from objective 1
    # (except for the system prompt which is the same for all calls)
    obj2_user_assistant_content = []
    for msg in messages_obj2:
        if msg.get("role") in ("user", "assistant") and "content" in msg:
            obj2_user_assistant_content.append(msg["content"])
    
    # Check that none of objective 1's user/assistant messages appear in objective 2
    obj1_user_assistant_content = [
        msg["content"]
        for msg in messages_obj1
        if msg.get("role") in ("user", "assistant") and "content" in msg
    ]
    
    for content in obj1_user_assistant_content:
        assert content not in obj2_user_assistant_content, (
            f"Context isolation violated: content from objective 1 "
            f"({content[:50]}...) appears in objective 2's messages. "
            f"Each run() must use a fresh context with no cross-objective history."
        )
    
    # Verify that objective 2's messages reference objective 2, not objective 1
    obj2_messages_str = " ".join(
        msg.get("content", "") for msg in messages_obj2
    )
    
    # The messages for objective 2 should mention objective 2's ID or title
    assert obj2_id in obj2_messages_str or obj2_title in obj2_messages_str, (
        f"Objective 2's messages should reference objective 2 "
        f"(id={obj2_id}, title={obj2_title})"
    )
    
    # The messages for objective 2 should NOT mention objective 1's specific details
    # (system prompt may be shared, but user messages should be fresh)
    obj2_user_messages = [
        msg["content"]
        for msg in messages_obj2
        if msg.get("role") == "user" and "content" in msg
    ]
    
    for user_msg in obj2_user_messages:
        # User messages for objective 2 should not contain objective 1's title
        # (unless by random chance they're the same, which we've excluded with assume)
        assert obj1_title not in user_msg, (
            f"Context isolation violated: objective 2's user message contains "
            f"objective 1's title ({obj1_title}). Each run() must construct "
            f"a fresh context specific to the current objective."
        )


# ─── Unit Tests ───────────────────────────────────────────────────────────────

def test_recording_agent_basic():
    """
    Basic unit test: verify the RecordingTestAgent works as expected.
    """
    agent = RecordingTestAgent(
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    )
    
    mock_ai = MockAIEngine(agent)
    agent._ai_engine = mock_ai
    
    objective = Objective(
        id="test_001",
        title="Test Objective",
        phase=ObjPhase.RECON,
    )
    
    result = agent.run(objective)
    
    assert result.success
    assert result.agent_name == "RecordingTestAgent"
    assert result.objective_id == "test_001"
    assert len(agent.ai_call_history) == 1


def test_agent_fresh_context_per_run():
    """
    Unit test: verify that each run() call creates a fresh context.
    
    This is a simpler, deterministic version of the property test.
    """
    agent = RecordingTestAgent(
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    )
    
    mock_ai = MockAIEngine(agent)
    agent._ai_engine = mock_ai
    
    # Run two objectives with distinct titles
    obj1 = Objective(id="obj1", title="First Objective", phase=ObjPhase.RECON)
    obj2 = Objective(id="obj2", title="Second Objective", phase=ObjPhase.SCAN)
    
    agent.run(obj1)
    agent.run(obj2)
    
    # Verify we have 2 separate AI calls
    assert len(agent.ai_call_history) == 2
    
    # Verify the messages are different
    messages1 = agent.ai_call_history[0]
    messages2 = agent.ai_call_history[1]
    
    # Extract user messages
    user_msg1 = [m["content"] for m in messages1 if m.get("role") == "user"]
    user_msg2 = [m["content"] for m in messages2 if m.get("role") == "user"]
    
    # User messages should be different (one mentions "First", other "Second")
    assert "First Objective" in " ".join(user_msg1)
    assert "Second Objective" in " ".join(user_msg2)
    
    # Objective 2's messages should NOT contain "First Objective"
    obj2_content = " ".join(m.get("content", "") for m in messages2)
    assert "First Objective" not in obj2_content, (
        "Context isolation violated: objective 2's messages contain "
        "content from objective 1"
    )


# ─── Task 3.3 Unit Tests ──────────────────────────────────────────────────────
# Requirements: 8.1–8.6
#
# Five focused unit tests covering:
#   1. Fresh context per run (Req 8.1, 8.2)
#   2. RoE check before module execution (Req 8.3)
#   3. AgentResult structure — all required fields present (Req 8.4)
#   4. AI unavailable fallback (Req 8.5)
#   5. KG update after run (Req 8.6)


# ─── Helpers ──────────────────────────────────────────────────────────────────

class SimpleTestAgent(BaseAgent):
    """
    Minimal concrete agent used by the unit tests.

    Behaviour is controlled by constructor flags so each test can exercise
    a specific code path without subclassing again.
    """

    def __init__(self, *args, run_module: bool = False, update_kg: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._run_module = run_module
        self._update_kg = update_kg
        # Track every context dict built during run()
        self.contexts_built: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "SimpleTestAgent"

    @property
    def system_prompt(self) -> str:
        return "Simple test agent."

    def run(self, objective) -> "AgentResult":
        import time as _time

        start = _time.monotonic()

        # Build a fresh context for this objective (Req 8.1)
        context: Dict[str, Any] = {
            "objective_id": objective.id,
            "objective_title": objective.title,
            "phase": str(objective.phase),
        }
        self.contexts_built.append(context)

        findings: List[Dict[str, Any]] = []
        errors: List[str] = []
        kg_updates: List[Dict[str, Any]] = []

        # Optionally exercise _execute_module (Req 8.3)
        if self._run_module:
            module_result = self._execute_module(
                "phantom-test",
                target=getattr(objective, "target", "127.0.0.1"),
                technique="T1046",
            )
            if module_result.get("success"):
                findings.append(module_result)
            else:
                errors.append(module_result.get("error", "module blocked"))

        # Query AI (Req 8.5)
        response = self._query_ai(context, f"Execute: {objective.title}")
        findings.append({"ai_response": response})

        # Optionally update KG (Req 8.6)
        if self._update_kg and self._knowledge_graph is not None:
            host_id = self._knowledge_graph.add_host(
                ip=getattr(objective, "target", "10.0.0.1"),
                properties={"source": self.name, "objective_id": objective.id},
            )
            kg_updates.append({"action": "add_host", "data": {"host_id": host_id}})

        duration = _time.monotonic() - start

        return AgentResult(
            success=True,
            agent_name=self.name,
            objective_id=objective.id,
            findings=findings,
            errors=errors,
            kg_updates=kg_updates,
            duration_seconds=duration,
        )


def _make_objective(obj_id: str, title: str, phase: str = "recon") -> "Objective":
    """Helper: create a minimal Objective."""
    return Objective(
        id=obj_id,
        title=title,
        phase=ObjPhase(phase),
        status=ObjStatus.PENDING,
    )


# ─── Test 1: Fresh context per run (Req 8.1, 8.2) ────────────────────────────

def test_fresh_context_per_run():
    """
    Each run() call must build a fresh context dict containing only the
    current objective's data — no history from previous runs.

    Requirements: 8.1, 8.2
    """
    agent = SimpleTestAgent(
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    )

    obj1 = _make_objective("ctx-001", "Recon Alpha", "recon")
    obj2 = _make_objective("ctx-002", "Scan Beta", "scan")

    agent.run(obj1)
    agent.run(obj2)

    # Two separate context dicts must have been built
    assert len(agent.contexts_built) == 2, (
        "Expected one context dict per run() call"
    )

    ctx1, ctx2 = agent.contexts_built

    # Each context references its own objective
    assert ctx1["objective_id"] == "ctx-001"
    assert ctx2["objective_id"] == "ctx-002"

    # Context 2 must NOT contain any data from context 1
    assert ctx2.get("objective_id") != ctx1.get("objective_id"), (
        "Context isolation violated: both contexts share the same objective_id"
    )
    assert "ctx-001" not in str(ctx2), (
        "Context isolation violated: context 2 contains data from context 1"
    )
    assert "Recon Alpha" not in str(ctx2), (
        "Context isolation violated: context 2 contains title from context 1"
    )


# ─── Test 2: RoE check before module execution (Req 8.3) ─────────────────────

def test_roe_check_before_module_execution():
    """
    _execute_module() must call RoE.check_action() before invoking the module.
    When the RoE check returns False (violation), the module must be skipped
    and a failure dict returned.

    Requirements: 8.3
    """
    from phantom.core.roe import RoEConfig, RoEMiddleware

    # Configure RoE to forbid the target we'll use
    roe_config = RoEConfig(
        forbidden_targets=["10.0.0.1"],
        allowed_targets=[],
    )
    roe = RoEMiddleware(roe_config)

    agent = SimpleTestAgent(
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=roe,
        skill_library=None,
        sandbox=None,
        run_module=True,  # will call _execute_module internally
    )

    # Attach a target to the objective so _execute_module uses the forbidden IP
    obj = _make_objective("roe-001", "Scan forbidden target")
    obj.target = "10.0.0.1"  # type: ignore[attr-defined]

    result = agent.run(obj)

    # The run itself should still succeed (agent handles the blocked module)
    assert result.success is True

    # The module should have been blocked — error list should mention RoE
    assert len(result.errors) > 0, "Expected an error entry for the blocked module"
    assert any("roe" in e.lower() or "violation" in e.lower() or "blocked" in e.lower()
               for e in result.errors), (
        f"Expected RoE-related error, got: {result.errors}"
    )

    # Verify the violation was logged by the RoE middleware
    violations = roe.get_violation_log()
    assert len(violations) > 0, "RoE middleware should have logged a violation"
    assert violations[0]["target"] == "10.0.0.1"


def test_roe_allows_permitted_target():
    """
    When the RoE check passes, _execute_module() should proceed (or fail for
    a different reason — no engine — but NOT because of RoE).

    Requirements: 8.3
    """
    from phantom.core.roe import RoEConfig, RoEMiddleware

    roe_config = RoEConfig(
        allowed_targets=["192.168.1.0/24"],
        forbidden_targets=[],
    )
    roe = RoEMiddleware(roe_config)

    agent = SimpleTestAgent(
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=roe,
        skill_library=None,
        sandbox=None,
        run_module=True,
    )

    obj = _make_objective("roe-002", "Scan allowed target")
    obj.target = "192.168.1.50"  # type: ignore[attr-defined]

    result = agent.run(obj)

    # No RoE violations should have been logged
    violations = roe.get_violation_log()
    assert len(violations) == 0, (
        f"Unexpected RoE violation for allowed target: {violations}"
    )

    # The error (if any) should be about missing engine, not RoE
    for err in result.errors:
        assert "roe" not in err.lower() and "violation" not in err.lower(), (
            f"Unexpected RoE error for allowed target: {err}"
        )


# ─── Test 3: AgentResult structure — all required fields present (Req 8.4) ───

def test_agent_result_structure():
    """
    run() must return an AgentResult with all required fields populated:
    agent_name, objective_id, success, findings, errors, kg_updates,
    duration_seconds, and raw_output.

    Requirements: 8.4
    """
    agent = SimpleTestAgent(
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    )

    obj = _make_objective("struct-001", "Structure test objective")
    result = agent.run(obj)

    # Verify all required fields are present and have the correct types
    assert isinstance(result, AgentResult), "run() must return an AgentResult"
    assert isinstance(result.success, bool), "success must be a bool"
    assert isinstance(result.agent_name, str) and result.agent_name, (
        "agent_name must be a non-empty string"
    )
    assert isinstance(result.objective_id, str) and result.objective_id, (
        "objective_id must be a non-empty string"
    )
    assert isinstance(result.findings, list), "findings must be a list"
    assert isinstance(result.errors, list), "errors must be a list"
    assert isinstance(result.kg_updates, list), "kg_updates must be a list"
    assert isinstance(result.mitre_techniques_used, list), (
        "mitre_techniques_used must be a list"
    )
    assert isinstance(result.duration_seconds, float), (
        "duration_seconds must be a float"
    )
    assert isinstance(result.raw_output, str), "raw_output must be a str"

    # Verify values are correct for this run
    assert result.agent_name == "SimpleTestAgent"
    assert result.objective_id == "struct-001"
    assert result.success is True
    assert result.duration_seconds >= 0.0


# ─── Test 4: AI unavailable fallback (Req 8.5) ───────────────────────────────

def test_ai_unavailable_fallback():
    """
    When ai_engine=None, _query_ai() must return a rule-based fallback string
    and must NOT raise any exception.

    Requirements: 8.5
    """
    agent = SimpleTestAgent(
        ai_engine=None,  # explicitly no AI
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    )

    # Direct call to _query_ai with no AI engine
    context = {"objective_id": "fallback-001", "phase": "recon"}
    response = agent._query_ai(context, "What should I do next?")

    # Must return a non-empty string (not raise)
    assert isinstance(response, str), "_query_ai must return a string"
    assert len(response) > 0, "_query_ai must return a non-empty fallback string"

    # The fallback string should mention the agent name or indicate AI is unavailable
    assert "SimpleTestAgent" in response or "unavailable" in response.lower() or \
           "rule-based" in response.lower() or "fallback" in response.lower(), (
        f"Fallback response should indicate AI is unavailable, got: {response!r}"
    )


def test_ai_unavailable_fallback_via_run():
    """
    When ai_engine=None, run() must complete successfully and include the
    rule-based fallback in findings — no exception raised.

    Requirements: 8.5
    """
    agent = SimpleTestAgent(
        ai_engine=None,
        knowledge_graph=None,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
    )

    obj = _make_objective("fallback-002", "Fallback test objective")
    result = agent.run(obj)

    # run() must succeed even without AI
    assert result.success is True, "run() must succeed even when AI is unavailable"

    # The findings should contain the fallback AI response
    ai_responses = [
        f["ai_response"]
        for f in result.findings
        if "ai_response" in f
    ]
    assert len(ai_responses) > 0, "findings should contain the AI response"
    assert all(isinstance(r, str) and len(r) > 0 for r in ai_responses), (
        "AI response in findings must be a non-empty string"
    )


# ─── Test 5: KG update after run (Req 8.6) ───────────────────────────────────

def test_kg_update_after_run():
    """
    When run() completes successfully, the agent must update the Knowledge
    Graph with findings discovered during the objective.

    Requirements: 8.6
    """
    from phantom.db.knowledge_graph import KnowledgeGraph

    # Use an in-memory KG so the test is self-contained
    kg = KnowledgeGraph()
    kg.connect(":memory:")

    agent = SimpleTestAgent(
        ai_engine=None,
        knowledge_graph=kg,
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
        update_kg=True,  # agent will call kg.add_host() during run()
    )

    obj = _make_objective("kg-001", "KG update test objective")
    obj.target = "10.10.10.1"  # type: ignore[attr-defined]

    result = agent.run(obj)

    # run() must succeed
    assert result.success is True

    # The result must report KG updates
    assert len(result.kg_updates) > 0, (
        "AgentResult.kg_updates must be non-empty after a successful run"
    )

    # Verify the host was actually written to the KG
    rows = kg.query(
        "SELECT id, label FROM nodes WHERE type = 'host' AND label LIKE ?",
        ("%10.10.10.1%",),
    )
    assert len(rows) > 0, (
        "KG should contain a host node for the target after run() completes"
    )

    kg.close()


def test_kg_update_skipped_when_no_kg():
    """
    When knowledge_graph=None, run() must still succeed without raising.
    No KG updates are expected, but the agent must not crash.

    Requirements: 8.6
    """
    agent = SimpleTestAgent(
        ai_engine=None,
        knowledge_graph=None,  # no KG
        opplan=None,
        roe=None,
        skill_library=None,
        sandbox=None,
        update_kg=True,  # agent will try to update KG but KG is None
    )

    obj = _make_objective("kg-002", "KG absent test objective")
    obj.target = "10.10.10.2"  # type: ignore[attr-defined]

    # Must not raise even though KG is None
    result = agent.run(obj)
    assert result.success is True
    # No KG updates since there's no KG
    assert result.kg_updates == [], (
        "kg_updates should be empty when no KG is configured"
    )
