"""
PhantomStrike v3.0 — Property Test: Graceful Degradation Completeness
Run with: pytest tests/test_v3_sandbox.py -v

Property 8: Graceful Degradation Completeness

For each optional component (DockerSandbox, SliverC2Engine, ADModule), when
the component is mocked as unavailable, every public method must:
  - Return a result with success=False
  - Include a non-empty error string
  - Never raise an unhandled exception

Validates: Requirements 13.2, 15.2, 14.3, 19.1, 19.2, 19.3
"""
from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from phantom.core.events import EventBus
from phantom.modules.ad.engine import ADModule
from phantom.modules.base import ModuleResult
from phantom.modules.c2.sliver_engine import SliverC2Engine
from phantom.sandbox.docker_sandbox import DockerSandbox


# ─── Helpers ──────────────────────────────────────────────────────────────────

def run(coro):
    """Run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


def make_event_bus() -> EventBus:
    return EventBus()


def make_docker_sandbox_unavailable() -> DockerSandbox:
    """Return a DockerSandbox whose is_available() always returns False."""
    sandbox = DockerSandbox()
    # Patch is_available to always return False
    sandbox.is_available = AsyncMock(return_value=False)
    sandbox._docker_available = False
    return sandbox


def make_sliver_engine_unavailable() -> SliverC2Engine:
    """Return a SliverC2Engine with _sliver_available=False and no fallback."""
    bus = make_event_bus()
    engine = SliverC2Engine(event_bus=bus)
    # Bypass initialize() — set flags directly
    engine._sliver_available = False
    engine._c2_fallback = None
    return engine


def make_ad_module_unavailable() -> ADModule:
    """Return an ADModule with _impacket_available=False."""
    bus = make_event_bus()
    module = ADModule(event_bus=bus)
    # Bypass initialize() — set flags directly
    module._impacket_available = False
    module._ldap3_available = False
    module._bloodhound_available = False
    module._sharphound_available = False
    return module


# ─── Strategies ───────────────────────────────────────────────────────────────

# Safe printable text for use as string arguments (no null bytes)
safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters=".-_:/",
    ),
    min_size=0,
    max_size=50,
)

# Integer strategy for ports and modes
safe_int = st.integers(min_value=-1000, max_value=100000)

# Non-negative integer for hashcat mode
safe_mode = st.integers(min_value=0, max_value=20000)


def _assert_graceful_failure(result, context: str) -> None:
    """
    Assert that *result* represents a graceful failure:
      - result["success"] is False  (for dict results)
      - result["error"] is a non-empty string  (for dict results)
    OR
      - result.success is False  (for ModuleResult)
      - result.errors is non-empty  (for ModuleResult)
    """
    if isinstance(result, dict):
        assert result.get("success") is False, (
            f"{context}: expected success=False, got {result!r}"
        )
        error = result.get("error", "")
        assert isinstance(error, str) and len(error) > 0, (
            f"{context}: expected non-empty error string, got {error!r}"
        )
    elif isinstance(result, ModuleResult):
        assert result.success is False, (
            f"{context}: expected success=False, got {result!r}"
        )
        assert len(result.errors) > 0, (
            f"{context}: expected non-empty errors list, got {result.errors!r}"
        )
    else:
        pytest.fail(f"{context}: unexpected result type {type(result)!r}: {result!r}")


# ─── Property 8: Graceful Degradation Completeness ────────────────────────────
# Validates: Requirements 13.2, 15.2, 14.3, 19.1, 19.2, 19.3


class TestDockerSandboxGracefulDegradation:
    """
    **Validates: Requirements 13.2, 19.1**

    Property 8 (DockerSandbox): When Docker is unavailable, every public
    method returns success=False with a non-empty error string and never raises.
    """

    @given(target=safe_text, flags=safe_text)
    @settings(max_examples=50)
    def test_run_nmap_unavailable_never_raises_and_returns_failure(
        self, target: str, flags: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_nmap() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_nmap(target=target, flags=flags))
        except Exception as exc:
            pytest.fail(f"run_nmap() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_nmap")

    @given(target_url=safe_text, flags=safe_text)
    @settings(max_examples=50)
    def test_run_sqlmap_unavailable_never_raises_and_returns_failure(
        self, target_url: str, flags: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_sqlmap() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_sqlmap(target_url=target_url, flags=flags))
        except Exception as exc:
            pytest.fail(f"run_sqlmap() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_sqlmap")

    @given(target=safe_text, service=safe_text, wordlist=safe_text)
    @settings(max_examples=50)
    def test_run_hydra_unavailable_never_raises_and_returns_failure(
        self, target: str, service: str, wordlist: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_hydra() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_hydra(target=target, service=service, wordlist=wordlist))
        except Exception as exc:
            pytest.fail(f"run_hydra() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_hydra")

    @given(hash_file=safe_text, wordlist=safe_text)
    @settings(max_examples=50)
    def test_run_john_unavailable_never_raises_and_returns_failure(
        self, hash_file: str, wordlist: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_john() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_john(hash_file=hash_file, wordlist=wordlist))
        except Exception as exc:
            pytest.fail(f"run_john() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_john")

    @given(hash_file=safe_text, mode=safe_mode, wordlist=safe_text)
    @settings(max_examples=50)
    def test_run_hashcat_unavailable_never_raises_and_returns_failure(
        self, hash_file: str, mode: int, wordlist: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_hashcat() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_hashcat(hash_file=hash_file, mode=mode, wordlist=wordlist))
        except Exception as exc:
            pytest.fail(f"run_hashcat() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_hashcat")

    @given(resource_script=safe_text)
    @settings(max_examples=50)
    def test_run_metasploit_unavailable_never_raises_and_returns_failure(
        self, resource_script: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_metasploit() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_metasploit(resource_script=resource_script))
        except Exception as exc:
            pytest.fail(f"run_metasploit() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_metasploit")

    @given(tool=safe_text, args=safe_text)
    @settings(max_examples=50)
    def test_run_impacket_unavailable_never_raises_and_returns_failure(
        self, tool: str, args: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_impacket() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_impacket(tool=tool, args=args))
        except Exception as exc:
            pytest.fail(f"run_impacket() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_impacket")

    @given(cmd=safe_text, timeout=st.integers(min_value=1, max_value=300))
    @settings(max_examples=50)
    def test_run_command_unavailable_never_raises_and_returns_failure(
        self, cmd: str, timeout: int
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        run_command() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.run_command(cmd=cmd, timeout=timeout))
        except Exception as exc:
            pytest.fail(f"run_command() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "run_command")

    @given(local_path=safe_text, container_path=safe_text)
    @settings(max_examples=50)
    def test_upload_file_unavailable_never_raises_and_returns_failure(
        self, local_path: str, container_path: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        upload_file() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.upload_file(local_path=local_path, container_path=container_path))
        except Exception as exc:
            pytest.fail(f"upload_file() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "upload_file")

    @given(container_path=safe_text, local_path=safe_text)
    @settings(max_examples=50)
    def test_download_file_unavailable_never_raises_and_returns_failure(
        self, container_path: str, local_path: str
    ):
        """
        **Validates: Requirements 13.2, 19.1**

        download_file() with Docker unavailable must return success=False with
        a non-empty error string and must never raise.
        """
        sandbox = make_docker_sandbox_unavailable()
        try:
            result = run(sandbox.download_file(container_path=container_path, local_path=local_path))
        except Exception as exc:
            pytest.fail(f"download_file() raised unexpectedly: {exc}")
        _assert_graceful_failure(result, "download_file")


class TestSliverC2EngineGracefulDegradation:
    """
    **Validates: Requirements 15.2, 19.2**

    Property 8 (SliverC2Engine): When _sliver_available=False and no fallback
    is set, generate_implant() must return success=False with a non-empty
    error string and must never raise.
    """

    @given(
        lhost=safe_text,
        lport=safe_int,
        target_os=st.sampled_from(["linux", "windows", "macos", "darwin"]),
        arch=st.sampled_from(["amd64", "386", "arm64", "arm"]),
        fmt=st.sampled_from(["elf", "exe", "dll", "macho", "shellcode", "shared_lib"]),
    )
    @settings(max_examples=100)
    def test_generate_implant_unavailable_never_raises_and_returns_failure(
        self, lhost: str, lport: int, target_os: str, arch: str, fmt: str
    ):
        """
        **Validates: Requirements 15.2, 19.2**

        Property 8 (SliverC2Engine): generate_implant() with Sliver unavailable
        must return {"success": False, "error": <non-empty str>} and never raise,
        for arbitrary lhost, lport, os, arch, and format values.

        Note: valid lport values (1–65535) will hit the "Sliver not installed"
        error path; invalid lport values will hit the validation error path.
        Both paths must satisfy the graceful failure contract.
        """
        engine = make_sliver_engine_unavailable()
        try:
            result = engine.generate_implant(
                lhost=lhost,
                lport=lport,
                os=target_os,
                arch=arch,
                format=fmt,
            )
        except Exception as exc:
            pytest.fail(f"generate_implant() raised unexpectedly: {exc}")

        assert isinstance(result, dict), (
            f"generate_implant() must return a dict, got {type(result)!r}"
        )
        assert result.get("success") is False, (
            f"generate_implant() with Sliver unavailable must return success=False, "
            f"got {result!r}"
        )
        error = result.get("error", "")
        assert isinstance(error, str) and len(error) > 0, (
            f"generate_implant() must include a non-empty error string, got {error!r}"
        )


class TestADModuleGracefulDegradation:
    """
    **Validates: Requirements 14.3, 19.3**

    Property 8 (ADModule): When _impacket_available=False, kerberoast() and
    asreproast() must return ModuleResult(success=False, errors=[non-empty])
    and must never raise, for arbitrary method call arguments.
    """

    @given(
        dc_ip=safe_text,
        domain=safe_text,
        username=safe_text,
        password=safe_text,
        hash_val=safe_text,
    )
    @settings(max_examples=100)
    def test_kerberoast_unavailable_never_raises_and_returns_failure(
        self,
        dc_ip: str,
        domain: str,
        username: str,
        password: str,
        hash_val: str,
    ):
        """
        **Validates: Requirements 14.3, 19.3**

        Property 8 (ADModule / kerberoast): With impacket unavailable,
        kerberoast() must return ModuleResult(success=False) with a non-empty
        errors list and must never raise, for arbitrary argument values.
        """
        module = make_ad_module_unavailable()
        try:
            result = run(module.kerberoast(
                dc_ip=dc_ip,
                domain=domain,
                username=username,
                password=password,
                hash_val=hash_val,
            ))
        except Exception as exc:
            pytest.fail(f"kerberoast() raised unexpectedly: {exc}")

        assert isinstance(result, ModuleResult), (
            f"kerberoast() must return a ModuleResult, got {type(result)!r}"
        )
        assert result.success is False, (
            f"kerberoast() with impacket unavailable must return success=False, "
            f"got {result!r}"
        )
        assert len(result.errors) > 0, (
            f"kerberoast() must include at least one error string, got {result.errors!r}"
        )
        assert all(isinstance(e, str) and len(e) > 0 for e in result.errors), (
            f"All errors must be non-empty strings, got {result.errors!r}"
        )

    @given(
        dc_ip=safe_text,
        domain=safe_text,
        username=safe_text,
        password=safe_text,
    )
    @settings(max_examples=100)
    def test_asreproast_unavailable_never_raises_and_returns_failure(
        self,
        dc_ip: str,
        domain: str,
        username: str,
        password: str,
    ):
        """
        **Validates: Requirements 14.3, 19.3**

        Property 8 (ADModule / asreproast): With impacket unavailable,
        asreproast() must return ModuleResult(success=False) with a non-empty
        errors list and must never raise, for arbitrary argument values.
        """
        module = make_ad_module_unavailable()
        try:
            result = run(module.asreproast(
                dc_ip=dc_ip,
                domain=domain,
                username=username,
                password=password,
            ))
        except Exception as exc:
            pytest.fail(f"asreproast() raised unexpectedly: {exc}")

        assert isinstance(result, ModuleResult), (
            f"asreproast() must return a ModuleResult, got {type(result)!r}"
        )
        assert result.success is False, (
            f"asreproast() with impacket unavailable must return success=False, "
            f"got {result!r}"
        )
        assert len(result.errors) > 0, (
            f"asreproast() must include at least one error string, got {result.errors!r}"
        )
        assert all(isinstance(e, str) and len(e) > 0 for e in result.errors), (
            f"All errors must be non-empty strings, got {result.errors!r}"
        )


# ─── Unit Tests: DockerSandbox Docker-not-available path ──────────────────────
# Validates: Requirements 13.1, 13.2


class TestDockerSandboxUnavailableUnit:
    """
    Unit tests for DockerSandbox when Docker is not available.

    Validates: Requirements 13.1, 13.2

    When is_available() returns False, every public method must:
      - Return {"success": False, "error": <non-empty str>}
      - Never raise an exception
    """

    def _make_sandbox(self) -> DockerSandbox:
        """Return a DockerSandbox whose is_available() always returns False."""
        sandbox = DockerSandbox()
        sandbox.is_available = AsyncMock(return_value=False)
        sandbox._docker_available = False
        return sandbox

    # ------------------------------------------------------------------
    # is_available() — Requirement 13.1
    # ------------------------------------------------------------------

    def test_is_available_returns_false_when_docker_not_installed(self):
        """
        Validates: Requirement 13.1

        When Docker is not installed, is_available() must return False
        without raising an exception.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.is_available())
        assert result is False

    # ------------------------------------------------------------------
    # run_nmap() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_nmap_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_nmap() must return {"success": False, "error": ...} when Docker
        is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_nmap(target="192.168.1.1", flags="-sV"))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_run_nmap_error_message_mentions_docker(self):
        """
        Validates: Requirement 13.2

        The error message from run_nmap() when Docker is unavailable must
        mention Docker so the operator knows what to install.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_nmap(target="10.0.0.1"))
        assert "docker" in result["error"].lower() or "Docker" in result["error"]

    # ------------------------------------------------------------------
    # run_sqlmap() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_sqlmap_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_sqlmap() must return {"success": False, "error": ...} when Docker
        is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_sqlmap(target_url="http://example.com/login"))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_run_sqlmap_with_flags_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_sqlmap() with extra flags must still return failure gracefully.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_sqlmap(
            target_url="http://example.com/page?id=1",
            flags="--dbs --level=3",
        ))
        assert result["success"] is False
        assert len(result.get("error", "")) > 0

    # ------------------------------------------------------------------
    # run_hydra() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_hydra_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_hydra() must return {"success": False, "error": ...} when Docker
        is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_hydra(
            target="192.168.1.100",
            service="ssh",
            wordlist="/phantom-data/passwords.txt",
        ))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    # ------------------------------------------------------------------
    # run_john() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_john_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_john() must return {"success": False, "error": ...} when Docker
        is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_john(
            hash_file="/phantom-data/hashes.txt",
            wordlist="/phantom-data/rockyou.txt",
        ))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_run_john_without_wordlist_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_john() without a wordlist must still return failure gracefully.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_john(hash_file="/phantom-data/hashes.txt"))
        assert result["success"] is False
        assert len(result.get("error", "")) > 0

    # ------------------------------------------------------------------
    # run_hashcat() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_hashcat_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_hashcat() must return {"success": False, "error": ...} when Docker
        is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_hashcat(
            hash_file="/phantom-data/hashes.txt",
            mode=0,
            wordlist="/phantom-data/rockyou.txt",
        ))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_run_hashcat_with_different_mode_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_hashcat() with a non-default mode must still return failure gracefully.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_hashcat(
            hash_file="/phantom-data/ntlm.txt",
            mode=1000,
            wordlist="/phantom-data/rockyou.txt",
        ))
        assert result["success"] is False
        assert len(result.get("error", "")) > 0

    # ------------------------------------------------------------------
    # run_metasploit() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_metasploit_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_metasploit() must return {"success": False, "error": ...} when
        Docker is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_metasploit(
            resource_script="/phantom-data/exploit.rc"
        ))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    # ------------------------------------------------------------------
    # run_impacket() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_impacket_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_impacket() must return {"success": False, "error": ...} when
        Docker is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_impacket(
            tool="GetUserSPNs",
            args="-dc-ip 192.168.1.1 domain/user:pass",
        ))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_run_impacket_secretsdump_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_impacket() with secretsdump tool must still return failure gracefully.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_impacket(
            tool="secretsdump",
            args="domain/admin:password@192.168.1.1",
        ))
        assert result["success"] is False
        assert len(result.get("error", "")) > 0

    # ------------------------------------------------------------------
    # run_command() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_run_command_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_command() must return {"success": False, "error": ...} when
        Docker is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_command(cmd="whoami", timeout=30))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    def test_run_command_with_default_timeout_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        run_command() with default timeout must still return failure gracefully.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.run_command(cmd="id"))
        assert result["success"] is False
        assert len(result.get("error", "")) > 0

    # ------------------------------------------------------------------
    # upload_file() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_upload_file_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        upload_file() must return {"success": False, "error": ...} when
        Docker is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.upload_file(
            local_path="/tmp/payload.bin",
            container_path="/phantom-data/payload.bin",
        ))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    # ------------------------------------------------------------------
    # download_file() — Requirement 13.2
    # ------------------------------------------------------------------

    def test_download_file_returns_failure_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        download_file() must return {"success": False, "error": ...} when
        Docker is unavailable, and must not raise.
        """
        sandbox = self._make_sandbox()
        result = run(sandbox.download_file(
            container_path="/phantom-data/output.txt",
            local_path="/tmp/output.txt",
        ))
        assert result["success"] is False
        assert isinstance(result.get("error"), str)
        assert len(result["error"]) > 0

    # ------------------------------------------------------------------
    # Graceful degradation — no exceptions raised (Requirement 13.2)
    # ------------------------------------------------------------------

    def test_no_method_raises_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        None of the public methods should raise any exception when Docker
        is unavailable. This test calls all methods and asserts no exception
        is raised from any of them.
        """
        sandbox = self._make_sandbox()

        methods_and_args = [
            ("run_nmap",       lambda: sandbox.run_nmap(target="10.0.0.1")),
            ("run_sqlmap",     lambda: sandbox.run_sqlmap(target_url="http://example.com")),
            ("run_hydra",      lambda: sandbox.run_hydra(target="10.0.0.1", service="ssh", wordlist="/tmp/wl.txt")),
            ("run_john",       lambda: sandbox.run_john(hash_file="/tmp/h.txt")),
            ("run_hashcat",    lambda: sandbox.run_hashcat(hash_file="/tmp/h.txt", mode=0)),
            ("run_metasploit", lambda: sandbox.run_metasploit(resource_script="/tmp/exploit.rc")),
            ("run_impacket",   lambda: sandbox.run_impacket(tool="GetUserSPNs", args="-dc-ip 1.2.3.4 d/u:p")),
            ("run_command",    lambda: sandbox.run_command(cmd="id")),
            ("upload_file",    lambda: sandbox.upload_file(local_path="/tmp/f.bin", container_path="/phantom-data/f.bin")),
            ("download_file",  lambda: sandbox.download_file(container_path="/phantom-data/f.bin", local_path="/tmp/f.bin")),
        ]

        for method_name, coro_factory in methods_and_args:
            try:
                result = run(coro_factory())
            except Exception as exc:
                pytest.fail(
                    f"{method_name}() raised an unexpected exception when Docker "
                    f"is unavailable: {type(exc).__name__}: {exc}"
                )
            assert result.get("success") is False, (
                f"{method_name}() must return success=False when Docker is unavailable"
            )

    def test_all_methods_return_dict_when_docker_unavailable(self):
        """
        Validates: Requirement 13.2

        All public methods must return a dict (not None, not a bool, not an
        exception) when Docker is unavailable.
        """
        sandbox = self._make_sandbox()

        results = {
            "run_nmap":       run(sandbox.run_nmap(target="10.0.0.1")),
            "run_sqlmap":     run(sandbox.run_sqlmap(target_url="http://example.com")),
            "run_hydra":      run(sandbox.run_hydra(target="10.0.0.1", service="ftp", wordlist="/tmp/wl.txt")),
            "run_john":       run(sandbox.run_john(hash_file="/tmp/h.txt")),
            "run_hashcat":    run(sandbox.run_hashcat(hash_file="/tmp/h.txt", mode=1000)),
            "run_metasploit": run(sandbox.run_metasploit(resource_script="/tmp/exploit.rc")),
            "run_impacket":   run(sandbox.run_impacket(tool="secretsdump", args="d/u:p@1.2.3.4")),
            "run_command":    run(sandbox.run_command(cmd="uname -a")),
            "upload_file":    run(sandbox.upload_file(local_path="/tmp/f.bin", container_path="/phantom-data/f.bin")),
            "download_file":  run(sandbox.download_file(container_path="/phantom-data/f.bin", local_path="/tmp/f.bin")),
        }

        for method_name, result in results.items():
            assert isinstance(result, dict), (
                f"{method_name}() must return a dict, got {type(result)!r}"
            )

    def test_error_message_is_consistent_across_all_methods(self):
        """
        Validates: Requirement 13.2

        All public methods must return the same standard error message when
        Docker is unavailable, so operators get a consistent experience.
        """
        expected_error = "Docker not available — install Docker for sandboxed execution"
        sandbox = self._make_sandbox()

        results = {
            "run_nmap":       run(sandbox.run_nmap(target="10.0.0.1")),
            "run_sqlmap":     run(sandbox.run_sqlmap(target_url="http://example.com")),
            "run_hydra":      run(sandbox.run_hydra(target="10.0.0.1", service="ssh", wordlist="/tmp/wl.txt")),
            "run_john":       run(sandbox.run_john(hash_file="/tmp/h.txt")),
            "run_hashcat":    run(sandbox.run_hashcat(hash_file="/tmp/h.txt", mode=0)),
            "run_metasploit": run(sandbox.run_metasploit(resource_script="/tmp/exploit.rc")),
            "run_impacket":   run(sandbox.run_impacket(tool="GetUserSPNs", args="-dc-ip 1.2.3.4 d/u:p")),
            "run_command":    run(sandbox.run_command(cmd="id")),
            "upload_file":    run(sandbox.upload_file(local_path="/tmp/f.bin", container_path="/phantom-data/f.bin")),
            "download_file":  run(sandbox.download_file(container_path="/phantom-data/f.bin", local_path="/tmp/f.bin")),
        }

        for method_name, result in results.items():
            assert result.get("error") == expected_error, (
                f"{method_name}() returned unexpected error message: {result.get('error')!r}"
            )
