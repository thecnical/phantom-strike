"""
PhantomStrike v3.0 — RoE Middleware Tests (Property + Unit)
Run with: pytest tests/test_v3_roe.py -v
"""
import asyncio
import time
import pytest
from datetime import datetime, timedelta
from hypothesis import given, assume, settings
import hypothesis.strategies as st

from phantom.core.roe import RoEConfig, RoEMiddleware


# ─── Property 1: RoE Forbidden Precedence ─────────────────────────────────────
# Validates: Requirements 4.1
#
# For any target that matches a pattern in forbidden_targets, check_target()
# MUST return False — regardless of what is in allowed_targets.

@given(
    forbidden_targets=st.lists(st.text(min_size=1), min_size=1),
    allowed_targets=st.lists(st.text(min_size=1)),
)
@settings(max_examples=200)
def test_forbidden_precedence(forbidden_targets: list[str], allowed_targets: list[str]):
    """
    **Validates: Requirements 4.1**

    Property 1: RoE Forbidden Precedence

    For every target T that appears literally in forbidden_targets,
    check_target(T) must return False regardless of what is in allowed_targets.
    This holds even when T also appears in allowed_targets (forbidden wins).
    """
    config = RoEConfig(
        forbidden_targets=forbidden_targets,
        allowed_targets=allowed_targets,
    )
    middleware = RoEMiddleware(config)

    for target in forbidden_targets:
        result = middleware.check_target(target)
        assert result is False, (
            f"check_target({target!r}) returned True but {target!r} is in "
            f"forbidden_targets={forbidden_targets!r}. "
            f"Forbidden must always take precedence over allowed."
        )


# ─── Property 1: RoE Forbidden Precedence ─────────────────────────────────────
# Validates: Requirements 4.1
#
# For any target that matches a pattern in forbidden_targets, check_target()
# MUST return False — regardless of what is in allowed_targets.

@given(
    forbidden_targets=st.lists(st.text(min_size=1), min_size=1),
    allowed_targets=st.lists(st.text(min_size=1)),
)
@settings(max_examples=200)
def test_forbidden_precedence(forbidden_targets: list[str], allowed_targets: list[str]):
    """
    **Validates: Requirements 4.1**

    Property 1: RoE Forbidden Precedence

    For every target T that appears literally in forbidden_targets,
    check_target(T) must return False regardless of what is in allowed_targets.
    This holds even when T also appears in allowed_targets (forbidden wins).
    """
    config = RoEConfig(
        forbidden_targets=forbidden_targets,
        allowed_targets=allowed_targets,
    )
    middleware = RoEMiddleware(config)

    for target in forbidden_targets:
        result = middleware.check_target(target)
        assert result is False, (
            f"check_target({target!r}) returned True but {target!r} is in "
            f"forbidden_targets={forbidden_targets!r}. "
            f"Forbidden must always take precedence over allowed."
        )


# ─── Unit Tests ────────────────────────────────────────────────────────────────

class TestForbiddenTakesPrecedence:
    """Requirement 4.1: forbidden_targets takes precedence over allowed_targets."""

    def test_target_in_both_forbidden_and_allowed_is_blocked(self):
        """A target in both lists must be blocked (forbidden wins)."""
        config = RoEConfig(
            forbidden_targets=["192.168.1.100"],
            allowed_targets=["192.168.1.100"],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("192.168.1.100") is False

    def test_target_only_in_forbidden_is_blocked(self):
        """A target only in forbidden_targets must be blocked."""
        config = RoEConfig(
            forbidden_targets=["10.0.0.1"],
            allowed_targets=["10.0.0.0/24"],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is False

    def test_target_only_in_allowed_is_permitted(self):
        """A target only in allowed_targets (not forbidden) must be allowed."""
        config = RoEConfig(
            forbidden_targets=["10.0.0.2"],
            allowed_targets=["10.0.0.1"],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is True

    def test_glob_pattern_in_forbidden_takes_precedence(self):
        """A glob pattern in forbidden_targets must block matching targets even if also in allowed."""
        config = RoEConfig(
            forbidden_targets=["*.evil.com"],
            allowed_targets=["host.evil.com"],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("host.evil.com") is False

    def test_cidr_in_forbidden_takes_precedence(self):
        """A CIDR in forbidden_targets must block IPs in that range even if also in allowed."""
        config = RoEConfig(
            forbidden_targets=["192.168.0.0/16"],
            allowed_targets=["192.168.1.50"],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("192.168.1.50") is False


class TestEmptyAllowedList:
    """Requirement 4.3: empty allowed_targets means all targets are allowed (except forbidden)."""

    def test_empty_allowed_permits_any_target(self):
        """With no allowed_targets, any non-forbidden target is allowed."""
        config = RoEConfig(
            forbidden_targets=[],
            allowed_targets=[],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is True
        assert mw.check_target("example.com") is True
        assert mw.check_target("172.16.0.1") is True

    def test_empty_allowed_still_blocks_forbidden(self):
        """With no allowed_targets, forbidden targets are still blocked."""
        config = RoEConfig(
            forbidden_targets=["10.0.0.1"],
            allowed_targets=[],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is False
        assert mw.check_target("10.0.0.2") is True

    def test_empty_allowed_blocks_forbidden_cidr(self):
        """With no allowed_targets, a forbidden CIDR still blocks matching IPs."""
        config = RoEConfig(
            forbidden_targets=["10.0.0.0/8"],
            allowed_targets=[],
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.1.2.3") is False
        assert mw.check_target("192.168.1.1") is True


class TestEngagementWindow:
    """Requirements 4.6, 4.7: engagement window enforcement."""

    def test_before_engagement_start_is_blocked(self):
        """A target check before engagement_start must return False."""
        future_start = datetime.now() + timedelta(hours=1)
        config = RoEConfig(
            allowed_targets=[],
            forbidden_targets=[],
            engagement_start=future_start,
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is False

    def test_after_engagement_end_is_blocked(self):
        """A target check after engagement_end must return False."""
        past_end = datetime.now() - timedelta(hours=1)
        config = RoEConfig(
            allowed_targets=[],
            forbidden_targets=[],
            engagement_end=past_end,
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is False

    def test_within_engagement_window_is_allowed(self):
        """A target check within the engagement window must be allowed (if not forbidden)."""
        past_start = datetime.now() - timedelta(hours=1)
        future_end = datetime.now() + timedelta(hours=1)
        config = RoEConfig(
            allowed_targets=[],
            forbidden_targets=[],
            engagement_start=past_start,
            engagement_end=future_end,
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is True

    def test_no_window_set_is_always_allowed(self):
        """When no engagement window is set, time-based checks do not block."""
        config = RoEConfig(
            allowed_targets=[],
            forbidden_targets=[],
            engagement_start=None,
            engagement_end=None,
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is True

    def test_before_start_blocks_even_if_in_allowed(self):
        """Engagement window check takes priority — even allowed targets are blocked before start."""
        future_start = datetime.now() + timedelta(hours=1)
        config = RoEConfig(
            allowed_targets=["10.0.0.1"],
            forbidden_targets=[],
            engagement_start=future_start,
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is False

    def test_after_end_blocks_even_if_in_allowed(self):
        """Engagement window check takes priority — even allowed targets are blocked after end."""
        past_end = datetime.now() - timedelta(hours=1)
        config = RoEConfig(
            allowed_targets=["10.0.0.1"],
            forbidden_targets=[],
            engagement_end=past_end,
        )
        mw = RoEMiddleware(config)
        assert mw.check_target("10.0.0.1") is False


class TestRateLimiting:
    """Requirements 5.1, 5.2: apply_rate_limit() enforces rate_limit_rps."""

    def test_rate_limit_zero_returns_immediately(self):
        """When rate_limit_rps=0, apply_rate_limit() should return without delay."""
        config = RoEConfig(rate_limit_rps=0.0)
        mw = RoEMiddleware(config)

        async def run():
            start = time.monotonic()
            await mw.apply_rate_limit()
            await mw.apply_rate_limit()
            await mw.apply_rate_limit()
            elapsed = time.monotonic() - start
            return elapsed

        elapsed = asyncio.get_event_loop().run_until_complete(run())
        # Should complete nearly instantly (well under 0.1s)
        assert elapsed < 0.1

    def test_rate_limit_positive_allows_first_call_immediately(self):
        """The first call to apply_rate_limit() should not block (bucket starts full)."""
        config = RoEConfig(rate_limit_rps=1.0)
        mw = RoEMiddleware(config)

        async def run():
            start = time.monotonic()
            await mw.apply_rate_limit()
            elapsed = time.monotonic() - start
            return elapsed

        elapsed = asyncio.get_event_loop().run_until_complete(run())
        # First call should be immediate
        assert elapsed < 0.1

    def test_rate_limit_high_rps_allows_multiple_calls_quickly(self):
        """With a high rate limit, multiple calls should complete quickly."""
        config = RoEConfig(rate_limit_rps=100.0)
        mw = RoEMiddleware(config)

        async def run():
            start = time.monotonic()
            for _ in range(5):
                await mw.apply_rate_limit()
            elapsed = time.monotonic() - start
            return elapsed

        elapsed = asyncio.get_event_loop().run_until_complete(run())
        # 5 calls at 100 rps should complete in well under 1 second
        assert elapsed < 1.0


class TestViolationLog:
    """Requirement 5.3: check_action() logs violations correctly."""

    def test_violation_logged_for_forbidden_target(self):
        """check_action() must log a violation when the target is forbidden."""
        config = RoEConfig(
            forbidden_targets=["10.0.0.1"],
            allowed_targets=[],
        )
        mw = RoEMiddleware(config)
        result = mw.check_action("10.0.0.1", "T1595")

        assert result is False
        log = mw.get_violation_log()
        assert len(log) == 1
        entry = log[0]
        assert "timestamp" in entry
        assert entry["target"] == "10.0.0.1"
        assert entry["technique"] == "T1595"
        assert "reason" in entry

    def test_violation_logged_for_forbidden_technique(self):
        """check_action() must log a violation when the technique is forbidden."""
        config = RoEConfig(
            allowed_targets=[],
            forbidden_techniques=["T1059"],
        )
        mw = RoEMiddleware(config)
        result = mw.check_action("10.0.0.1", "T1059")

        assert result is False
        log = mw.get_violation_log()
        assert len(log) == 1
        entry = log[0]
        assert entry["technique"] == "T1059"
        assert "reason" in entry

    def test_no_violation_logged_for_allowed_action(self):
        """check_action() must NOT log a violation when the action is allowed."""
        config = RoEConfig(
            allowed_targets=["10.0.0.1"],
            forbidden_targets=[],
            allowed_techniques=["T1595"],
            forbidden_techniques=[],
        )
        mw = RoEMiddleware(config)
        result = mw.check_action("10.0.0.1", "T1595")

        assert result is True
        log = mw.get_violation_log()
        assert len(log) == 0

    def test_multiple_violations_all_logged(self):
        """Multiple violations must all appear in the log."""
        config = RoEConfig(
            forbidden_targets=["10.0.0.1"],
            allowed_targets=[],
        )
        mw = RoEMiddleware(config)
        mw.check_action("10.0.0.1", "T1595")
        mw.check_action("10.0.0.1", "T1046")

        log = mw.get_violation_log()
        assert len(log) == 2

    def test_violation_log_contains_timestamp(self):
        """Each violation log entry must contain a timestamp string."""
        config = RoEConfig(forbidden_targets=["bad.host"])
        mw = RoEMiddleware(config)
        mw.check_action("bad.host", "T1000")

        log = mw.get_violation_log()
        assert len(log) == 1
        # Timestamp should be a non-empty string (ISO format)
        assert isinstance(log[0]["timestamp"], str)
        assert len(log[0]["timestamp"]) > 0

    def test_get_violation_log_returns_copy(self):
        """get_violation_log() must return a copy — mutating it must not affect internal state."""
        config = RoEConfig(forbidden_targets=["10.0.0.1"])
        mw = RoEMiddleware(config)
        mw.check_action("10.0.0.1", "T1595")

        log = mw.get_violation_log()
        log.clear()  # mutate the returned copy

        # Internal log must be unaffected
        assert len(mw.get_violation_log()) == 1

    def test_check_action_never_raises(self):
        """Requirement 4.8: check_action() must never raise an unhandled exception."""
        config = RoEConfig(
            forbidden_targets=["10.0.0.1"],
            forbidden_techniques=["T1059"],
        )
        mw = RoEMiddleware(config)
        # These should not raise
        try:
            mw.check_action("10.0.0.1", "T1059")
            mw.check_action("", "")
            mw.check_action("not-an-ip", "NOT-A-TECHNIQUE")
        except Exception as exc:
            pytest.fail(f"check_action() raised an unexpected exception: {exc}")


# ─── Property 7: RoE Rate Limit Enforcement ───────────────────────────────────
# Validates: Requirements 5.1, 5.2
#
# The number of actions executed per second must never exceed rate_limit_rps
# within a 1-second measurement window.

@given(
    rate_limit_rps=st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=5, deadline=30000)
def test_rate_limit_enforcement(rate_limit_rps: float):
    """
    **Validates: Requirements 5.1, 5.2**

    Property 7: RoE Rate Limit Enforcement

    For any rate_limit_rps value in [1, 5], making (floor(rps) + 2) calls to
    apply_rate_limit() must take at least 1/rps seconds total (after the
    initial bucket is exhausted).

    Strategy:
    - The bucket starts full (capacity = rps tokens).
    - We make floor(rps) + 2 calls total.
    - The first floor(rps) calls drain the bucket immediately.
    - The remaining 2 calls must each wait ~1/rps seconds.
    - Total elapsed must be >= 2/rps * 0.5 (50% tolerance for CI jitter).
    """
    import math

    config = RoEConfig(rate_limit_rps=rate_limit_rps)
    mw = RoEMiddleware(config)

    # Drain the initial bucket + make 2 extra calls that must wait
    initial_free_calls = max(1, int(math.floor(rate_limit_rps)))
    extra_calls = 2
    total_calls = initial_free_calls + extra_calls

    async def _run():
        start = asyncio.get_event_loop().time()
        for _ in range(total_calls):
            await mw.apply_rate_limit()
        return asyncio.get_event_loop().time() - start

    elapsed = asyncio.get_event_loop().run_until_complete(_run())

    # The 2 extra calls must each wait ~1/rps seconds
    min_expected = extra_calls / rate_limit_rps

    # Allow 50% tolerance for timing jitter on CI
    assert elapsed >= min_expected * 0.5, (
        f"Rate limiter too fast: {total_calls} calls at {rate_limit_rps} rps "
        f"completed in {elapsed:.3f}s, expected >= {min_expected * 0.5:.3f}s. "
        f"Initial free calls: {initial_free_calls}, extra calls: {extra_calls}"
    )


def test_rate_limit_zero_no_delay():
    """
    **Validates: Requirements 5.1**

    When rate_limit_rps=0 (unlimited), apply_rate_limit() must return
    immediately with no measurable delay.
    """
    config = RoEConfig(rate_limit_rps=0.0)
    mw = RoEMiddleware(config)

    async def _run():
        start = asyncio.get_event_loop().time()
        for _ in range(10):
            await mw.apply_rate_limit()
        return asyncio.get_event_loop().time() - start

    elapsed = asyncio.get_event_loop().run_until_complete(_run())
    assert elapsed < 0.5, (
        f"rate_limit_rps=0 should have no delay, but took {elapsed:.3f}s"
    )
