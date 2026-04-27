"""
PhantomStrike Test Suite — Core module tests.
Run with: pytest tests/ -v
"""
import asyncio
import hashlib
import pytest

# ─── Config Tests ─────────────────────────────────────────────

def test_config_loads():
    """Config loads without error."""
    from phantom.core.config import load_config
    config = load_config()
    assert config.project_name == "PhantomStrike"
    assert config.version == "1.0.0-alpha"

def test_config_has_ai_providers():
    """Config loads default AI providers."""
    from phantom.core.config import load_config
    config = load_config()
    assert len(config.ai_providers) >= 9
    assert "groq" in config.ai_providers

def test_config_groq_is_priority():
    """Groq is the highest priority provider."""
    from phantom.core.config import load_config, AIProviderType
    config = load_config()
    assert config.ai_primary_provider == AIProviderType.GROQ
    groq = config.ai_providers["groq"]
    assert groq.priority == 0

def test_config_data_dir_created():
    """Data directory is created on config load."""
    from phantom.core.config import load_config
    config = load_config()
    assert config.data_dir.exists()

def test_config_threading_defaults():
    """Thread config has sensible defaults."""
    from phantom.core.config import load_config
    config = load_config()
    assert config.threading.max_scan_threads >= 50
    assert config.threading.max_workers >= 10


# ─── Event Bus Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_bus_start_stop():
    """Event bus starts and stops cleanly."""
    from phantom.core.events import EventBus
    bus = EventBus()
    await bus.start()
    assert bus._running
    await bus.stop()
    assert not bus._running

@pytest.mark.asyncio
async def test_event_bus_emit():
    """Events can be emitted and processed."""
    from phantom.core.events import EventBus, Event, EventType
    bus = EventBus()
    await bus.start()

    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe(EventType.ENGINE_START, handler)
    await bus.emit(Event(type=EventType.ENGINE_START, data="test"))
    await asyncio.sleep(0.2)  # Let processor run

    assert len(received) == 1
    assert received[0].data == "test"
    await bus.stop()

@pytest.mark.asyncio
async def test_event_bus_stats():
    """Event stats are tracked."""
    from phantom.core.events import EventBus, Event, EventType
    bus = EventBus()
    await bus.start()
    await bus.emit(Event(type=EventType.TARGET_ADDED, data="example.com"))
    await asyncio.sleep(0.1)
    stats = bus.get_stats()
    assert stats.get("target.added", 0) >= 1
    await bus.stop()


# ─── Module Base Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_module_loader():
    """Module loader loads all modules."""
    from phantom.core.events import EventBus
    from phantom.core.loader import load_all_modules
    bus = EventBus()
    await bus.start()
    modules = await load_all_modules(bus)
    assert len(modules) >= 8  # At least 8 modules should load
    await bus.stop()

@pytest.mark.asyncio
async def test_all_modules_have_name():
    """All modules have name, description, category."""
    from phantom.core.events import EventBus
    from phantom.core.loader import load_all_modules
    bus = EventBus()
    await bus.start()
    modules = await load_all_modules(bus)
    for name, mod in modules.items():
        assert mod.name, f"Module {name} has no name"
        assert mod.description, f"Module {name} has no description"
        assert mod.category, f"Module {name} has no category"
    await bus.stop()


# ─── Stealth Engine Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_stealth_xss_generation():
    """Stealth engine generates unique XSS payloads."""
    from phantom.core.events import EventBus
    from phantom.modules.stealth.engine import StealthEngine
    bus = EventBus()
    await bus.start()
    stealth = StealthEngine(event_bus=bus)
    await stealth.initialize()
    result = await stealth.run("test.com", {"type": "xss"})
    assert result.success
    assert result.findings_count > 0
    assert len(result.data["payloads"]) == 20
    await bus.stop()

@pytest.mark.asyncio
async def test_stealth_sqli_generation():
    """Stealth engine generates unique SQLi payloads."""
    from phantom.core.events import EventBus
    from phantom.modules.stealth.engine import StealthEngine
    bus = EventBus()
    await bus.start()
    stealth = StealthEngine(event_bus=bus)
    await stealth.initialize()
    result = await stealth.run("test.com", {"type": "sqli"})
    assert result.success
    assert len(result.data["payloads"]) == 20
    await bus.stop()

@pytest.mark.asyncio
async def test_stealth_reverse_shells():
    """Stealth engine generates reverse shell payloads."""
    from phantom.core.events import EventBus
    from phantom.modules.stealth.engine import StealthEngine
    bus = EventBus()
    await bus.start()
    stealth = StealthEngine(event_bus=bus)
    await stealth.initialize()
    result = await stealth.run("", {"type": "reverse_shell", "lhost": "10.0.0.1", "lport": 4444})
    assert result.success
    shells = result.data["payloads"]
    assert len(shells) >= 5
    languages = [s["language"] for s in shells]
    assert "bash" in languages
    assert "python" in languages
    await bus.stop()

@pytest.mark.asyncio
async def test_stealth_payloads_unique():
    """Generated payloads should be unique."""
    from phantom.core.events import EventBus
    from phantom.modules.stealth.engine import StealthEngine
    bus = EventBus()
    await bus.start()
    stealth = StealthEngine(event_bus=bus)
    await stealth.initialize()
    result = await stealth.run("test.com", {"type": "xss"})
    hashes = [p["unique_hash"] for p in result.data["payloads"]]
    # Most should be unique (random mutation means occasional collision is OK)
    assert len(set(hashes)) >= len(hashes) * 0.7
    await bus.stop()


# ─── Credential Engine Tests ─────────────────────────────────

@pytest.mark.asyncio
async def test_cred_hash_crack():
    """Hash cracking works for known hashes."""
    from phantom.core.events import EventBus
    from phantom.modules.cred.engine import CredEngine
    bus = EventBus()
    await bus.start()
    cred = CredEngine(event_bus=bus)
    await cred.initialize()

    # Create a known md5 hash
    known_password = "password"
    known_hash = hashlib.md5(known_password.encode()).hexdigest()

    result = await cred.run("", {
        "type": "hash",
        "hashes": [known_hash],
        "hash_type": "md5",
    })
    assert result.success
    assert len(result.data["weak_hashes"]) == 1
    assert result.data["weak_hashes"][0]["plaintext"] == known_password
    await bus.stop()


# ─── Post-Exploit Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_post_exploit_enumerate():
    """Post-exploit enumeration returns scripts."""
    from phantom.core.events import EventBus
    from phantom.modules.post.engine import PostExploitEngine
    bus = EventBus()
    await bus.start()
    post = PostExploitEngine(event_bus=bus)
    await post.initialize()
    result = await post.run("10.0.0.1", {"operation": "enumerate"})
    assert result.success
    data = result.data
    assert len(data["privesc_vectors"]) > 0
    assert len(data["lateral_targets"]) > 0
    assert len(data["persistence_options"]) > 0
    assert "enumeration_script" in data
    assert "#!/bin/bash" in data["enumeration_script"]
    await bus.stop()


# ─── C2 Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_c2_register_agent():
    """C2 can register agents."""
    from phantom.core.events import EventBus
    from phantom.modules.c2.engine import C2Engine
    bus = EventBus()
    await bus.start()
    c2 = C2Engine(event_bus=bus)
    await c2.initialize()
    result = await c2.run("10.0.0.5", {
        "operation": "register_agent",
        "hostname": "victim-01",
        "os_info": "Linux 6.1",
        "username": "www-data",
    })
    assert result.success
    assert "registered" in result.data
    await bus.stop()

@pytest.mark.asyncio
async def test_c2_generate_payload():
    """C2 generates agent payloads."""
    from phantom.core.events import EventBus
    from phantom.modules.c2.engine import C2Engine
    bus = EventBus()
    await bus.start()
    c2 = C2Engine(event_bus=bus)
    await c2.initialize()
    result = await c2.run("", {
        "operation": "generate_agent", "lhost": "10.0.0.1", "lport": 4444,
    })
    assert result.success
    payload = result.data["agent_payload"]
    assert "python" in payload
    assert "bash" in payload
    assert "10.0.0.1" in payload["python"]
    assert "4444" in payload["python"]
    await bus.stop()


# ─── Database Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_db_connect():
    """Database connects and creates schema."""
    from phantom.db.store import PhantomDB
    from pathlib import Path
    import tempfile
    db_path = Path(tempfile.mktemp(suffix=".db"))
    db = PhantomDB(db_path)
    await db.connect()
    # Insert and retrieve a scan
    scan_id = await db.insert_scan("test_session", "example.com", "phantom-web")
    assert scan_id >= 1
    scans = await db.get_scans()
    assert len(scans) >= 1
    await db.close()
    db_path.unlink(missing_ok=True)

@pytest.mark.asyncio
async def test_db_vuln_crud():
    """Database vulnerability CRUD works."""
    from phantom.db.store import PhantomDB
    from pathlib import Path
    import tempfile
    db_path = Path(tempfile.mktemp(suffix=".db"))
    db = PhantomDB(db_path)
    await db.connect()
    scan_id = await db.insert_scan("s1", "test.com", "web")
    vuln_id = await db.insert_vuln(scan_id, "test.com", "sqli", severity="critical",
                                    url="https://test.com/?id=1", payload="' OR 1=1--")
    vulns = await db.get_vulns(target="test.com")
    assert len(vulns) == 1
    assert vulns[0]["vuln_type"] == "sqli"
    stats = await db.get_vuln_stats("test.com")
    assert stats["critical"] == 1
    await db.close()
    db_path.unlink(missing_ok=True)


# ─── API Server Tests ────────────────────────────────────────

def test_api_app_exists():
    """FastAPI app can be imported."""
    from phantom.api.server import app
    assert app is not None
    assert app.title == "PhantomStrike API"
