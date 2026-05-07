"""
PhantomStrike v3.0 — ADModule Unit Tests
Run with: pytest tests/test_v3_ad.py -v

Tests cover:
  - impacket-not-installed path (Requirements 14.3, 19.3)
  - unreachable DC path (Requirement 14.4)
  - graceful degradation — no unhandled exceptions from any public method (Requirement 14.5)
"""
from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from phantom.core.events import EventBus
from phantom.modules.ad.engine import ADModule
from phantom.modules.base import ModuleResult


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_event_bus() -> EventBus:
    """Return a real EventBus instance (no mocking needed)."""
    return EventBus()


async def make_ad_module(
    impacket_available: bool = True,
    ldap3_available: bool = True,
    bloodhound_available: bool = False,
) -> ADModule:
    """
    Instantiate and initialise an ADModule with controlled availability flags.

    We patch the import probes inside _setup() so the module never actually
    tries to import impacket or ldap3 from the environment.
    """
    bus = make_event_bus()
    module = ADModule(event_bus=bus)

    # Run _setup() with patched imports
    with patch.dict(sys.modules, _build_module_stubs(impacket_available, ldap3_available)):
        await module.initialize()

    # Override the flags directly after setup (belt-and-suspenders)
    module._impacket_available = impacket_available
    module._ldap3_available = ldap3_available
    module._bloodhound_available = bloodhound_available
    module._sharphound_available = False

    return module


def _build_module_stubs(impacket_ok: bool, ldap3_ok: bool) -> dict:
    """
    Build a sys.modules patch dict that makes impacket / ldap3 appear
    installed or missing depending on the flags.
    """
    stubs: dict = {}

    if impacket_ok:
        # Provide a minimal stub so `import impacket` succeeds
        stubs["impacket"] = types.ModuleType("impacket")
    else:
        # Force ImportError by setting the entry to None
        stubs["impacket"] = None  # type: ignore[assignment]

    if ldap3_ok:
        stubs["ldap3"] = types.ModuleType("ldap3")
    else:
        stubs["ldap3"] = None  # type: ignore[assignment]

    return stubs


def run(coro):
    """Run a coroutine synchronously (pytest-asyncio not required)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── impacket-not-installed path ──────────────────────────────────────────────

class TestImpacketNotInstalled:
    """
    Requirements 14.3, 19.3:
    When impacket is not installed, kerberoast() and asreproast() must return
    ModuleResult(success=False, errors=["impacket not installed ..."]).
    """

    @pytest.fixture
    def ad(self):
        return run(make_ad_module(impacket_available=False))

    def test_kerberoast_returns_failure_when_impacket_missing(self, ad):
        result = run(ad.kerberoast(
            dc_ip="192.168.1.1",
            domain="corp.local",
            username="user",
            password="pass",
        ))
        assert isinstance(result, ModuleResult)
        assert result.success is False
        assert len(result.errors) > 0
        assert "impacket" in result.errors[0].lower()

    def test_kerberoast_error_message_contains_install_hint(self, ad):
        result = run(ad.kerberoast(
            dc_ip="10.0.0.1",
            domain="test.local",
            username="admin",
        ))
        # The error should mention pip install impacket
        assert any("pip install impacket" in e for e in result.errors)

    def test_asreproast_returns_failure_when_impacket_missing(self, ad):
        result = run(ad.asreproast(
            dc_ip="192.168.1.1",
            domain="corp.local",
            username="user",
        ))
        assert isinstance(result, ModuleResult)
        assert result.success is False
        assert len(result.errors) > 0
        assert "impacket" in result.errors[0].lower()

    def test_asreproast_error_message_contains_install_hint(self, ad):
        result = run(ad.asreproast(
            dc_ip="10.0.0.1",
            domain="test.local",
        ))
        assert any("pip install impacket" in e for e in result.errors)

    def test_kerberoast_result_has_correct_module_name(self, ad):
        result = run(ad.kerberoast(
            dc_ip="192.168.1.1",
            domain="corp.local",
            username="user",
        ))
        assert result.module_name == "phantom-ad"

    def test_asreproast_result_has_correct_module_name(self, ad):
        result = run(ad.asreproast(
            dc_ip="192.168.1.1",
            domain="corp.local",
        ))
        assert result.module_name == "phantom-ad"

    def test_kerberoast_result_has_correct_operation(self, ad):
        result = run(ad.kerberoast(
            dc_ip="192.168.1.1",
            domain="corp.local",
            username="user",
        ))
        assert result.operation == "kerberoast"

    def test_asreproast_result_has_correct_operation(self, ad):
        result = run(ad.asreproast(
            dc_ip="192.168.1.1",
            domain="corp.local",
        ))
        assert result.operation == "asreproast"

    def test_kerberoast_does_not_raise(self, ad):
        """Requirement 14.5: no unhandled exception must escape kerberoast()."""
        try:
            run(ad.kerberoast(dc_ip="192.168.1.1", domain="corp.local", username="u"))
        except Exception as exc:
            pytest.fail(f"kerberoast() raised an unexpected exception: {exc}")

    def test_asreproast_does_not_raise(self, ad):
        """Requirement 14.5: no unhandled exception must escape asreproast()."""
        try:
            run(ad.asreproast(dc_ip="192.168.1.1", domain="corp.local"))
        except Exception as exc:
            pytest.fail(f"asreproast() raised an unexpected exception: {exc}")


# ─── Unreachable DC path ──────────────────────────────────────────────────────

class TestUnreachableDC:
    """
    Requirement 14.4:
    When the DC is unreachable, methods must return ModuleResult(success=False)
    with a descriptive error message.
    """

    @pytest.fixture
    def ad(self):
        return run(make_ad_module(impacket_available=True, ldap3_available=True))

    def test_kerberoast_returns_failure_on_connection_error(self, ad):
        """Simulate a ConnectionError from the executor (DC unreachable)."""
        with patch.object(
            ad,
            "_run_kerberoast_sync",
            side_effect=ConnectionError("Cannot connect to 192.168.1.1: Connection refused"),
        ):
            result = run(ad.kerberoast(
                dc_ip="192.168.1.1",
                domain="corp.local",
                username="user",
                password="pass",
            ))

        assert isinstance(result, ModuleResult)
        assert result.success is False
        assert len(result.errors) > 0
        # Error must be descriptive — mention the DC IP or "unreachable"
        error_text = " ".join(result.errors).lower()
        assert "192.168.1.1" in error_text or "unreachable" in error_text or "connect" in error_text

    def test_asreproast_returns_failure_on_connection_error(self, ad):
        """Simulate a ConnectionError from the executor (DC unreachable)."""
        with patch.object(
            ad,
            "_run_asreproast_sync",
            side_effect=ConnectionError("Cannot connect to 10.0.0.1: timed out"),
        ):
            result = run(ad.asreproast(
                dc_ip="10.0.0.1",
                domain="corp.local",
                username="user",
            ))

        assert isinstance(result, ModuleResult)
        assert result.success is False
        assert len(result.errors) > 0
        error_text = " ".join(result.errors).lower()
        assert "10.0.0.1" in error_text or "unreachable" in error_text or "connect" in error_text

    def test_ldap_enum_returns_failure_on_connection_error(self, ad):
        """Simulate a ConnectionError from the executor (DC unreachable)."""
        with patch.object(
            ad,
            "_run_ldap_enum_sync",
            side_effect=ConnectionError("Cannot connect to 172.16.0.1: Connection refused"),
        ):
            result = run(ad.ldap_enum(
                dc_ip="172.16.0.1",
                domain="corp.local",
            ))

        assert isinstance(result, ModuleResult)
        assert result.success is False
        assert len(result.errors) > 0

    def test_kerberoast_error_is_descriptive_not_generic(self, ad):
        """The error message must describe the failure, not just say 'error'."""
        with patch.object(
            ad,
            "_run_kerberoast_sync",
            side_effect=ConnectionError("KDC unreachable at 192.168.100.1"),
        ):
            result = run(ad.kerberoast(
                dc_ip="192.168.100.1",
                domain="corp.local",
                username="user",
            ))

        assert result.success is False
        # Error must be non-trivially descriptive (more than just "error")
        assert len(result.errors[0]) > 5

    def test_kerberoast_does_not_raise_on_connection_error(self, ad):
        """Requirement 14.5: ConnectionError must be caught, not propagated."""
        with patch.object(
            ad,
            "_run_kerberoast_sync",
            side_effect=ConnectionError("DC unreachable"),
        ):
            try:
                run(ad.kerberoast(dc_ip="1.2.3.4", domain="x.local", username="u"))
            except Exception as exc:
                pytest.fail(f"kerberoast() propagated an exception: {exc}")

    def test_asreproast_does_not_raise_on_connection_error(self, ad):
        """Requirement 14.5: ConnectionError must be caught, not propagated."""
        with patch.object(
            ad,
            "_run_asreproast_sync",
            side_effect=ConnectionError("DC unreachable"),
        ):
            try:
                run(ad.asreproast(dc_ip="1.2.3.4", domain="x.local"))
            except Exception as exc:
                pytest.fail(f"asreproast() propagated an exception: {exc}")

    def test_kerberoast_result_has_timestamps(self, ad):
        """ModuleResult must have start_time and end_time set."""
        with patch.object(
            ad,
            "_run_kerberoast_sync",
            side_effect=ConnectionError("DC unreachable"),
        ):
            result = run(ad.kerberoast(dc_ip="1.2.3.4", domain="x.local", username="u"))

        assert result.start_time is not None
        assert result.end_time is not None


# ─── Graceful degradation — no exceptions from any public method ──────────────

class TestGracefulDegradation:
    """
    Requirement 14.5, 19.3, 19.4:
    No public method of ADModule may raise an unhandled exception under any
    circumstances — missing deps, bad inputs, unexpected runtime errors.
    """

    @pytest.fixture
    def ad_no_deps(self):
        """ADModule with all optional dependencies unavailable."""
        return run(make_ad_module(
            impacket_available=False,
            ldap3_available=False,
            bloodhound_available=False,
        ))

    @pytest.fixture
    def ad_with_deps(self):
        """ADModule with all optional dependencies available."""
        return run(make_ad_module(
            impacket_available=True,
            ldap3_available=True,
            bloodhound_available=False,
        ))

    # --- kerberoast ---

    def test_kerberoast_no_deps_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.kerberoast(dc_ip="1.2.3.4", domain="x.local", username="u"))
        except Exception as exc:
            pytest.fail(f"kerberoast() raised: {exc}")

    def test_kerberoast_empty_args_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.kerberoast(dc_ip="", domain="", username=""))
        except Exception as exc:
            pytest.fail(f"kerberoast() raised with empty args: {exc}")

    def test_kerberoast_unexpected_exception_does_not_propagate(self, ad_with_deps):
        """Even an unexpected RuntimeError from the sync helper must be caught."""
        with patch.object(
            ad_with_deps,
            "_run_kerberoast_sync",
            side_effect=RuntimeError("unexpected internal error"),
        ):
            try:
                result = run(ad_with_deps.kerberoast(
                    dc_ip="1.2.3.4", domain="x.local", username="u"
                ))
                assert result.success is False
            except Exception as exc:
                pytest.fail(f"kerberoast() propagated RuntimeError: {exc}")

    # --- asreproast ---

    def test_asreproast_no_deps_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.asreproast(dc_ip="1.2.3.4", domain="x.local"))
        except Exception as exc:
            pytest.fail(f"asreproast() raised: {exc}")

    def test_asreproast_empty_args_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.asreproast(dc_ip="", domain=""))
        except Exception as exc:
            pytest.fail(f"asreproast() raised with empty args: {exc}")

    def test_asreproast_unexpected_exception_does_not_propagate(self, ad_with_deps):
        with patch.object(
            ad_with_deps,
            "_run_asreproast_sync",
            side_effect=RuntimeError("unexpected internal error"),
        ):
            try:
                result = run(ad_with_deps.asreproast(dc_ip="1.2.3.4", domain="x.local"))
                assert result.success is False
            except Exception as exc:
                pytest.fail(f"asreproast() propagated RuntimeError: {exc}")

    # --- bloodhound_collect ---

    def test_bloodhound_collect_no_tools_does_not_raise(self, ad_no_deps):
        """bloodhound_collect() must not raise when no BloodHound tools are present."""
        try:
            result = run(ad_no_deps.bloodhound_collect(
                dc_ip="1.2.3.4", domain="x.local"
            ))
            # Should return a graceful skip result
            assert isinstance(result, ModuleResult)
        except Exception as exc:
            pytest.fail(f"bloodhound_collect() raised: {exc}")

    def test_bloodhound_collect_skips_gracefully_when_unavailable(self, ad_no_deps):
        """When no BloodHound tools are installed, result must indicate a graceful skip."""
        result = run(ad_no_deps.bloodhound_collect(
            dc_ip="1.2.3.4", domain="x.local"
        ))
        assert isinstance(result, ModuleResult)
        # Graceful skip: success=True with skipped=True in data, OR success=False with error
        # The design says "skip gracefully" — the implementation returns success=True + skipped
        assert result.data is not None
        assert result.data.get("skipped") is True

    def test_bloodhound_collect_unexpected_exception_does_not_propagate(self, ad_with_deps):
        """Even an unexpected error from the sync helper must be caught."""
        ad_with_deps._bloodhound_available = True  # pretend it's available
        with patch.object(
            ad_with_deps,
            "_run_bloodhound_sync",
            side_effect=RuntimeError("unexpected error"),
        ):
            try:
                result = run(ad_with_deps.bloodhound_collect(
                    dc_ip="1.2.3.4", domain="x.local"
                ))
                assert result.success is False
            except Exception as exc:
                pytest.fail(f"bloodhound_collect() propagated RuntimeError: {exc}")

    # --- ldap_enum ---

    def test_ldap_enum_no_ldap3_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.ldap_enum(dc_ip="1.2.3.4", domain="x.local"))
        except Exception as exc:
            pytest.fail(f"ldap_enum() raised: {exc}")

    def test_ldap_enum_no_ldap3_returns_failure(self, ad_no_deps):
        result = run(ad_no_deps.ldap_enum(dc_ip="1.2.3.4", domain="x.local"))
        assert result.success is False
        assert len(result.errors) > 0
        assert "ldap3" in result.errors[0].lower()

    def test_ldap_enum_unexpected_exception_does_not_propagate(self, ad_with_deps):
        with patch.object(
            ad_with_deps,
            "_run_ldap_enum_sync",
            side_effect=RuntimeError("unexpected error"),
        ):
            try:
                result = run(ad_with_deps.ldap_enum(dc_ip="1.2.3.4", domain="x.local"))
                assert result.success is False
            except Exception as exc:
                pytest.fail(f"ldap_enum() propagated RuntimeError: {exc}")

    # --- run() dispatcher ---

    def test_run_kerberoast_operation_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.run("1.2.3.4", {"operation": "kerberoast", "domain": "x.local", "username": "u"}))
        except Exception as exc:
            pytest.fail(f"run(kerberoast) raised: {exc}")

    def test_run_asreproast_operation_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.run("1.2.3.4", {"operation": "asreproast", "domain": "x.local"}))
        except Exception as exc:
            pytest.fail(f"run(asreproast) raised: {exc}")

    def test_run_bloodhound_operation_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.run("1.2.3.4", {"operation": "bloodhound", "domain": "x.local"}))
        except Exception as exc:
            pytest.fail(f"run(bloodhound) raised: {exc}")

    def test_run_ldap_enum_operation_does_not_raise(self, ad_no_deps):
        try:
            run(ad_no_deps.run("1.2.3.4", {"operation": "ldap_enum", "domain": "x.local"}))
        except Exception as exc:
            pytest.fail(f"run(ldap_enum) raised: {exc}")

    def test_run_unknown_operation_does_not_raise(self, ad_no_deps):
        """An unknown operation should fall through to ldap_enum without raising."""
        try:
            run(ad_no_deps.run("1.2.3.4", {"operation": "unknown_op", "domain": "x.local"}))
        except Exception as exc:
            pytest.fail(f"run(unknown_op) raised: {exc}")

    def test_run_no_options_does_not_raise(self, ad_no_deps):
        """run() with no options dict must not raise."""
        try:
            run(ad_no_deps.run("1.2.3.4"))
        except Exception as exc:
            pytest.fail(f"run() with no options raised: {exc}")

    # --- All public methods return ModuleResult ---

    def test_kerberoast_always_returns_module_result(self, ad_no_deps):
        result = run(ad_no_deps.kerberoast(dc_ip="1.2.3.4", domain="x.local", username="u"))
        assert isinstance(result, ModuleResult)

    def test_asreproast_always_returns_module_result(self, ad_no_deps):
        result = run(ad_no_deps.asreproast(dc_ip="1.2.3.4", domain="x.local"))
        assert isinstance(result, ModuleResult)

    def test_bloodhound_collect_always_returns_module_result(self, ad_no_deps):
        result = run(ad_no_deps.bloodhound_collect(dc_ip="1.2.3.4", domain="x.local"))
        assert isinstance(result, ModuleResult)

    def test_ldap_enum_always_returns_module_result(self, ad_no_deps):
        result = run(ad_no_deps.ldap_enum(dc_ip="1.2.3.4", domain="x.local"))
        assert isinstance(result, ModuleResult)
