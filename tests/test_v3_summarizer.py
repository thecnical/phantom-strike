"""
PhantomStrike v3.0 — ConversationSummarizer Tests
Run with: pytest tests/test_v3_summarizer.py -v

Includes:
  - Unit tests for ConversationSummarizer (task 1.14)
  - Property 5: Summarizer Verbatim Preservation (task 1.13)

Requirements: 12.1–12.6
"""

import pytest
from hypothesis import given, assume, settings
import hypothesis.strategies as st

from phantom.ai.summarizer import ConversationSummarizer, estimate_tokens


# ─── Strategies ───────────────────────────────────────────────────────────────

# A single message dict with "role" and "content" keys.
# Content is at least 1 character so token estimates are non-trivial.
message_strategy = st.fixed_dictionaries(
    {
        "role": st.sampled_from(["user", "assistant", "system"]),
        "content": st.text(min_size=1, max_size=200),
    }
)


def _make_engine(summary_text: str = "SUMMARY"):
    """Return a minimal callable AI engine that returns a fixed summary string."""

    class _MockEngine:
        def chat(self, messages):
            return summary_text

    return _MockEngine()


# ─── Property 5: Summarizer Verbatim Preservation ─────────────────────────────
# Validates: Requirements 12.3, 12.4
#
# When compression is triggered (>10 messages, token count >= threshold),
# the last 10 messages from the original list MUST appear unchanged and in
# their original order at the end of the compressed output.


@given(
    messages=st.lists(message_strategy, min_size=11, max_size=60),
)
@settings(max_examples=200)
def test_summarizer_verbatim_preservation(messages):
    """
    **Validates: Requirements 12.3, 12.4**

    Property 5: Summarizer Verbatim Preservation

    For any message list with more than 10 messages whose estimated token count
    is at or above the compression threshold, maybe_compress() MUST:
      - Return compressed=True
      - Preserve the last 10 messages verbatim (same dict contents)
      - Preserve the last 10 messages in their original order at the tail of
        the returned list
    """
    # We need the token count to be >= threshold.
    # Use a low threshold so that any list of >10 messages with non-trivial
    # content will trigger compression.  We pick a threshold that is guaranteed
    # to be <= the actual token estimate for the generated messages.
    token_count = estimate_tokens(messages)

    # If the generated messages happen to have very short content the token
    # count might be 0; skip those degenerate cases.
    assume(token_count > 0)

    # Set threshold to at most the actual token count so compression fires.
    threshold = token_count

    engine = _make_engine("This is a fixed summary of the older messages.")
    summarizer = ConversationSummarizer(ai_engine=engine, token_threshold=threshold)

    result_messages, compressed = summarizer.maybe_compress(messages)

    # Compression must have been triggered (>10 messages, tokens >= threshold).
    assert compressed is True, (
        f"Expected compressed=True for {len(messages)} messages with "
        f"token_count={token_count} >= threshold={threshold}, "
        f"but got compressed=False."
    )

    # The result must contain at least 11 entries: 1 summary + 10 verbatim.
    assert len(result_messages) >= 11, (
        f"Expected at least 11 messages in result (1 summary + 10 verbatim), "
        f"got {len(result_messages)}."
    )

    # The last 10 messages in the result must be exactly the last 10 from the
    # original list — same content, same order.
    expected_tail = messages[-10:]
    actual_tail = result_messages[-10:]

    assert actual_tail == expected_tail, (
        f"Last 10 messages were not preserved verbatim.\n"
        f"Expected: {expected_tail}\n"
        f"Got:      {actual_tail}"
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_messages(n: int, content: str = "x" * 100) -> list:
    """Return a list of *n* simple user messages with the given content."""
    return [{"role": "user", "content": content} for _ in range(n)]


def _make_engine_with_summary(summary_text: str = "SUMMARY"):
    """Return a minimal AI engine that returns a fixed summary string."""

    class _MockEngine:
        def chat(self, messages):
            return summary_text

    return _MockEngine()


# ─── Unit Tests ───────────────────────────────────────────────────────────────


class TestEstimateTokens:
    """Unit tests for the module-level estimate_tokens() helper (Req 12.5)."""

    def test_empty_list_returns_zero(self):
        assert estimate_tokens([]) == 0

    def test_single_message_four_chars(self):
        # 4 chars / 4 = 1 token
        assert estimate_tokens([{"content": "abcd"}]) == 1

    def test_single_message_three_chars(self):
        # 3 chars / 4 = 0 (integer division)
        assert estimate_tokens([{"content": "abc"}]) == 0

    def test_multiple_messages_summed(self):
        msgs = [{"content": "aaaa"}, {"content": "bbbbbbbb"}]
        # (4 + 8) // 4 = 3
        assert estimate_tokens(msgs) == 3

    def test_instance_method_matches_module_function(self):
        msgs = _make_messages(5, "hello world!")
        s = ConversationSummarizer()
        assert s.estimate_tokens(msgs) == estimate_tokens(msgs)


class TestBelowThreshold:
    """
    Req 12.1 — token count < threshold → (messages, False), no compression.
    """

    def test_below_threshold_returns_original_unchanged(self):
        # 5 messages × 4 chars = 20 chars → 5 tokens; threshold = 1000
        msgs = _make_messages(5, "abcd")
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=1000)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result is msgs  # same object — not a copy

    def test_below_threshold_with_many_messages(self):
        # 20 messages × 4 chars = 80 chars → 20 tokens; threshold = 10000
        msgs = _make_messages(20, "abcd")
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=10000)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs

    def test_token_count_exactly_one_below_threshold(self):
        # content = 40 chars → 10 tokens per message; 15 messages → 150 tokens
        # threshold = 151 → below threshold
        msgs = _make_messages(15, "a" * 40)
        token_count = estimate_tokens(msgs)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=token_count + 1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs


class TestAboveThreshold:
    """
    Req 12.3, 12.4 — token count >= threshold AND >10 messages → compressed result.
    """

    def test_above_threshold_returns_compressed(self):
        # 15 messages × 400 chars = 6000 chars → 1500 tokens; threshold = 100
        msgs = _make_messages(15, "a" * 400)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary("SUMMARY"), token_threshold=100)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is True

    def test_above_threshold_result_has_summary_plus_last_10(self):
        msgs = _make_messages(15, "a" * 400)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary("MY SUMMARY"), token_threshold=100)
        result, compressed = s.maybe_compress(msgs)
        # Result = [summary_message] + last 10
        assert len(result) == 11
        assert result[0]["role"] == "system"
        assert "MY SUMMARY" in result[0]["content"]

    def test_above_threshold_last_10_preserved_verbatim(self):
        msgs = _make_messages(15, "a" * 400)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=100)
        result, compressed = s.maybe_compress(msgs)
        assert result[-10:] == msgs[-10:]

    def test_above_threshold_last_10_in_original_order(self):
        # Give each message a unique content so order is verifiable
        msgs = [{"role": "user", "content": f"message-{i}" + "x" * 200} for i in range(20)]
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is True
        assert result[-10:] == msgs[-10:]

    def test_token_count_exactly_at_threshold_triggers_compression(self):
        # Set threshold == token_count so the >= condition is met exactly
        msgs = _make_messages(15, "a" * 400)
        token_count = estimate_tokens(msgs)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=token_count)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is True


class TestExactly10Messages:
    """
    Req 12.2 — even if token count >= threshold, ≤10 messages → no compression.
    """

    def test_exactly_10_messages_no_compression(self):
        # 10 messages × 4000 chars = 40000 chars → 10000 tokens; threshold = 1
        msgs = _make_messages(10, "a" * 4000)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs

    def test_9_messages_no_compression(self):
        msgs = _make_messages(9, "a" * 4000)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs

    def test_1_message_no_compression(self):
        msgs = _make_messages(1, "a" * 4000)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs

    def test_empty_messages_no_compression(self):
        msgs = []
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs

    def test_11_messages_above_threshold_does_compress(self):
        # Confirm the boundary: 11 messages should compress when above threshold
        msgs = _make_messages(11, "a" * 4000)
        s = ConversationSummarizer(ai_engine=_make_engine_with_summary(), token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is True


class TestAIUnavailableFallback:
    """
    Req 12.6 — ai_engine=None (or raising engine) → (messages, False), no exception.
    """

    def test_none_ai_engine_returns_original(self):
        msgs = _make_messages(15, "a" * 400)
        s = ConversationSummarizer(ai_engine=None, token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs

    def test_none_ai_engine_does_not_raise(self):
        msgs = _make_messages(15, "a" * 400)
        s = ConversationSummarizer(ai_engine=None, token_threshold=1)
        # Must not raise any exception
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False

    def test_raising_ai_engine_returns_original(self):
        class _BrokenEngine:
            def chat(self, messages):
                raise RuntimeError("AI service unavailable")

        msgs = _make_messages(15, "a" * 400)
        s = ConversationSummarizer(ai_engine=_BrokenEngine(), token_threshold=1)
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False
        assert result == msgs

    def test_raising_ai_engine_does_not_propagate_exception(self):
        class _BrokenEngine:
            def chat(self, messages):
                raise ConnectionError("network error")

        msgs = _make_messages(15, "a" * 400)
        s = ConversationSummarizer(ai_engine=_BrokenEngine(), token_threshold=1)
        # Must not raise
        result, compressed = s.maybe_compress(msgs)
        assert compressed is False

    def test_default_constructor_has_none_engine(self):
        # ConversationSummarizer() with no args should default ai_engine=None
        s = ConversationSummarizer()
        assert s.ai_engine is None

    def test_default_threshold_is_4000(self):
        s = ConversationSummarizer()
        assert s.token_threshold == 4000
