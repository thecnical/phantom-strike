"""
PhantomStrike v3.0 — SliverC2Engine Unit Tests
Run with: pytest tests/test_v3_sliver.py -v

Tests cover:
  - Sliver-not-installed path (Requirement 15.2, 19.2)
  - Invalid lport validation (Requirement 15.4)
  - Fallback to phantom-c2 when Sliver unavailable (Requirement 15.3)
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from phantom.core.events import EventBus
from phantom.modules.c2.sliver_engine import SliverC2Engine


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_event_bus() -> EventBus:
    return EventBus()


def make_engine(sliver_available: bool = False) -> SliverC2Engine:
    """
    Create a SliverC2Engine with controlled availability.

    We patch shutil.which so no real binary lookup occurs.
    """
    bus = make_event_bus()
    engine = SliverC2Engine(event_bus=bus)

    # Run _setup() synchronously
    with patch("shutil.which", return_value="/usr/bin/sliver-client" if sliver_available else None):
        asyncio.get_event_loop().run_until_complete(engine.initialize())

    # Belt-and-suspenders: override the cached flag directly
    engine._sliver_available = sliver_available
    return engine


# ─── Sliver-not-installed path ────────────────────────────────────────────────

class TestSliverNotInstalled:
    """
    Requirements 15.2, 19.2:
    When sliver-client is not in PATH, generate_implant() must return
    {"success": False, "error": str} without raising.
    """

    @pytest.fixture
    def engine(self):
        return make_engine(sliver_available=False)

    def test_generate_implant_returns_failure_dict(self, engine):
        """generate_implant() returns a dict with success=False when Sliver absent."""
        result = engine.generate_implant(lhost="10.0.0.1", lport=443)
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_generate_implant_includes_error_key(self, engine):
        """The failure dict must contain a non-empty 'error' key."""
        result = engine.generate_implant(lhost="10.0.0.1", lport=443)
        assert "error" in result
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0

    def test_generate_implant_error_mentions_sliver(self, engine):
        """The error message should reference Sliver so the operator knows what's missing."""
        result = engine.generate_implant(lhost="10.0.0.1", lport=443)
        assert "sliver" in result["error"].lower() or "install" in result["error"].lower()

    def test_generate_implant_does_not_raise(self, engine):
        """Requirement 15.2: no exception must escape generate_implant()."""
        try:
            engine.generate_implant(lhost="10.0.0.1", lport=443)
        except Exception as exc:
            pytest.fail(f"generate_implant() raised an unexpected exception: {exc}")

    def test_is_available_returns_false_when_not_installed(self):
        """is_available() returns False when sliver-client is absent from PATH."""
        with patch("shutil.which", return_value=None):
            bus = make_event_bus()
            engine = SliverC2Engine(event_bus=bus)
            assert engine.is_available() is False

    def test_generate_implant_no_implant_path_in_failure(self, engine):
        """A failure result must not contain implant_path (no partial success)."""
        result = engine.generate_implant(lhost="10.0.0.1", lport=443)
        assert result.get("implant_path") is None

    def test_generate_implant_various_params_all_fail(self, engine):
        """All parameter combinations fail when Sliver is absent."""
        cases = [
            dict(lhost="192.168.1.1", lport=4444, os="linux", arch="amd64", format="elf"),
            dict(lhost="192.168.1.1", lport=8443, os="windows", arch="amd64", format="exe"),
            dict(lhost="192.168.1.1", lport=443, os="macos", arch="arm64", format="macho"),
        ]
        for kwargs in cases:
            result = engine.generate_implant(**kwargs)
            assert result["success"] is False, f"Expected failure for {kwargs}"


# ─── Invalid lport validation ─────────────────────────────────────────────────

class TestInvalidLport:
    """
    Requirement 15.4:
    generate_implant() with lport outside 1–65535 must return
    {"success": False, "error": str} with a descriptive validation message.
    """

    @pytest.fixture
    def engine(self):
        # Availability doesn't matter for lport validation — it's checked first.
        return make_engine(sliver_available=False)

    def test_lport_zero_returns_failure(self, engine):
        result = engine.generate_implant(lhost="10.0.0.1", lport=0)
        assert result["success"] is False
        assert "error" in result

    def test_lport_negative_one_returns_failure(self, engine):
        result = engine.generate_implant(lhost="10.0.0.1", lport=-1)
        assert result["success"] is False
        assert "error" in result

    def test_lport_65536_returns_failure(self, engine):
        result = engine.generate_implant(lhost="10.0.0.1", lport=65536)
        assert result["success"] is False
        assert "error" in result

    def test_lport_zero_error_is_descriptive(self, engine):
        """The error message must describe the validation failure."""
        result = engine.generate_implant(lhost="10.0.0.1", lport=0)
        error = result["error"].lower()
        # Must mention the port range or the invalid value
        assert "65535" in error or "range" in error or "invalid" in error or "lport" in error

    def test_lport_negative_error_is_descriptive(self, engine):
        result = engine.generate_implant(lhost="10.0.0.1", lport=-1)
        error = result["error"].lower()
        assert "65535" in error or "range" in error or "invalid" in error or "lport" in error

    def test_lport_65536_error_is_descriptive(self, engine):
        result = engine.generate_implant(lhost="10.0.0.1", lport=65536)
        error = result["error"].lower()
        assert "65535" in error or "range" in error or "invalid" in error or "lport" in error

    def test_lport_zero_does_not_raise(self, engine):
        try:
            engine.generate_implant(lhost="10.0.0.1", lport=0)
        except Exception as exc:
            pytest.fail(f"generate_implant(lport=0) raised: {exc}")

    def test_lport_negative_does_not_raise(self, engine):
        try:
            engine.generate_implant(lhost="10.0.0.1", lport=-1)
        except Exception as exc:
            pytest.fail(f"generate_implant(lport=-1) raised: {exc}")

    def test_lport_65536_does_not_raise(self, engine):
        try:
            engine.generate_implant(lhost="10.0.0.1", lport=65536)
        except Exception as exc:
            pytest.fail(f"generate_implant(lport=65536) raised: {exc}")

    def test_lport_boundary_1_is_valid(self, engine):
        """lport=1 is the minimum valid port — validation must not reject it."""
        # With Sliver absent and no fallback, it will fail for a different reason
        # (Sliver not installed), but the lport itself must not be the cause.
        result = engine.generate_implant(lhost="10.0.0.1", lport=1)
        # The error (if any) must NOT be about lport range
        if not result["success"]:
            error = result.get("error", "").lower()
            assert "range" not in error or "1" not in error, (
                "lport=1 should be valid but was rejected by range check"
            )

    def test_lport_boundary_65535_is_valid(self, engine):
        """lport=65535 is the maximum valid port — validation must not reject it."""
        result = engine.generate_implant(lhost="10.0.0.1", lport=65535)
        if not result["success"]:
            error = result.get("error", "").lower()
            assert "65535" not in error or "range" not in error, (
                "lport=65535 should be valid but was rejected by range check"
            )

    def test_lport_large_negative_returns_failure(self, engine):
        result = engine.generate_implant(lhost="10.0.0.1", lport=-9999)
        assert result["success"] is False
        assert "error" in result

    def test_lport_very_large_returns_failure(self, engine):
        result = engine.generate_implant(lhost="10.0.0.1", lport=99999)
        assert result["success"] is False
        assert "error" in result


# ─── Fallback to phantom-c2 ───────────────────────────────────────────────────

class TestFallbackToPhantomC2:
    """
    Requirement 15.3:
    When Sliver is unavailable and a c2_fallback module is set,
    generate_implant() must delegate to phantom-c2 for payload generation.
    """

    @pytest.fixture
    def engine_with_fallback(self):
        """Engine with Sliver absent but a phantom-c2 fallback injected."""
        engine = make_engine(sliver_available=False)

        # Build a minimal phantom-c2 mock that returns a valid payload dict
        mock_c2 = MagicMock()
        mock_c2._generate_agent_payload.return_value = {
            "python": "# phantom-c2 agent\nprint('hello')\n",
            "bash": "#!/bin/bash\necho hello",
            "config": {"lhost": "10.0.0.1", "lport": 4444},
        }
        engine.set_c2_fallback(mock_c2)
        return engine, mock_c2

    def test_fallback_is_called_when_sliver_unavailable(self, engine_with_fallback, tmp_path):
        """generate_implant() must call phantom-c2's _generate_agent_payload()."""
        engine, mock_c2 = engine_with_fallback

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            engine.generate_implant(lhost="10.0.0.1", lport=4444)

        mock_c2._generate_agent_payload.assert_called_once()

    def test_fallback_called_with_correct_lhost_lport(self, engine_with_fallback):
        """The fallback must receive the same lhost and lport as generate_implant()."""
        engine, mock_c2 = engine_with_fallback

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            engine.generate_implant(lhost="192.168.1.100", lport=8443)

        call_kwargs = mock_c2._generate_agent_payload.call_args
        # Accept both positional and keyword arguments
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        args = call_kwargs.args if call_kwargs.args else ()
        assert kwargs.get("lhost") == "192.168.1.100" or "192.168.1.100" in args
        assert kwargs.get("lport") == 8443 or 8443 in args

    def test_fallback_result_indicates_phantom_c2_framework(self, engine_with_fallback):
        """The success result must identify phantom-c2 as the framework used."""
        engine, _ = engine_with_fallback

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            result = engine.generate_implant(lhost="10.0.0.1", lport=4444)

        assert result["success"] is True
        assert result.get("framework") == "phantom-c2"

    def test_fallback_result_has_fallback_flag(self, engine_with_fallback):
        """The result dict must include fallback=True to signal the fallback path was used."""
        engine, _ = engine_with_fallback

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            result = engine.generate_implant(lhost="10.0.0.1", lport=4444)

        assert result.get("fallback") is True

    def test_fallback_result_has_implant_path(self, engine_with_fallback):
        """The fallback result must include an implant_path."""
        engine, _ = engine_with_fallback

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            result = engine.generate_implant(lhost="10.0.0.1", lport=4444)

        assert result["success"] is True
        assert "implant_path" in result
        assert isinstance(result["implant_path"], str)

    def test_fallback_result_has_implant_name(self, engine_with_fallback):
        """The fallback result must include an implant_name."""
        engine, _ = engine_with_fallback

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            result = engine.generate_implant(lhost="10.0.0.1", lport=4444)

        assert result["success"] is True
        assert "implant_name" in result
        assert isinstance(result["implant_name"], str)

    def test_fallback_not_called_when_lport_invalid(self, engine_with_fallback):
        """lport validation runs before the fallback — phantom-c2 must NOT be called."""
        engine, mock_c2 = engine_with_fallback

        engine.generate_implant(lhost="10.0.0.1", lport=0)

        mock_c2._generate_agent_payload.assert_not_called()

    def test_fallback_error_when_c2_raises(self):
        """If phantom-c2 itself raises, generate_implant() must return success=False."""
        engine = make_engine(sliver_available=False)

        mock_c2 = MagicMock()
        mock_c2._generate_agent_payload.side_effect = RuntimeError("phantom-c2 internal error")
        engine.set_c2_fallback(mock_c2)

        result = engine.generate_implant(lhost="10.0.0.1", lport=4444)
        assert result["success"] is False
        assert "error" in result

    def test_no_fallback_set_returns_sliver_not_installed_error(self):
        """Without a fallback module, the canonical 'Sliver not installed' error is returned."""
        engine = make_engine(sliver_available=False)
        # No set_c2_fallback() call

        result = engine.generate_implant(lhost="10.0.0.1", lport=4444)
        assert result["success"] is False
        assert "sliver" in result["error"].lower() or "install" in result["error"].lower()

    def test_set_c2_fallback_stores_module(self):
        """set_c2_fallback() must store the module for later use."""
        engine = make_engine(sliver_available=False)
        mock_c2 = MagicMock()
        engine.set_c2_fallback(mock_c2)
        assert engine._c2_fallback is mock_c2
