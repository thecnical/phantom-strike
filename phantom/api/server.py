"""
PhantomStrike FastAPI Backend — Production-ready REST API.
Deploy on Render, Railway, or any cloud platform.
Provides full API access to all offensive modules.
"""
from __future__ import annotations
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field

from phantom.core.config import load_config, PhantomStrikeConfig
from phantom.core.engine import PhantomEngine
from phantom.core.events import EventBus

logger = logging.getLogger("phantom.api")

# ─── Global Engine Instance ───────────────────────────────────────
_engine: Optional[PhantomEngine] = None


def get_engine() -> PhantomEngine:
    """Dependency: get the global engine instance."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global _engine
    config = load_config()
    _engine = PhantomEngine(config)
    await _engine.start()
    logger.info("[API] PhantomStrike engine started")
    yield
    # Shutdown
    if _engine:
        await _engine.stop()
    logger.info("[API] PhantomStrike engine stopped")


# ─── FastAPI App ──────────────────────────────────────────────────
app = FastAPI(
    title="PhantomStrike API",
    description="Elite AI-powered offensive cybersecurity framework — REST API",
    version="1.0.0-alpha",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ─────────────────────────────────────

class ScanRequest(BaseModel):
    target: str = Field(..., description="Target domain or IP to scan")
    modules: list[str] = Field(default=[], description="Specific modules to run (empty = all recon)")
    options: dict = Field(default={}, description="Module-specific options")


class ModuleRunRequest(BaseModel):
    target: str = Field(..., description="Target domain or IP")
    options: dict = Field(default={}, description="Module options")


class FullChainRequest(BaseModel):
    target: str = Field(..., description="Target for full kill chain")
    auto_exploit: bool = Field(default=False, description="Enable auto-exploitation")


class AIQueryRequest(BaseModel):
    prompt: str = Field(..., description="Question or analysis request for AI")
    system_prompt: str = Field(default="", description="Optional system prompt")
    provider: str = Field(default="", description="Specific AI provider (empty = auto)")


class C2CheckinRequest(BaseModel):
    operation: str = Field(..., description="register, checkin, or result")
    hostname: str = Field(default="")
    agent_id: str = Field(default="")
    os_info: str = Field(default="")
    user: str = Field(default="")
    username: str = Field(default="")
    command_id: str = Field(default="")
    output: str = Field(default="")


# ─── API Routes ───────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Welcome page with API info."""
    return """
    <html>
    <head><title>PhantomStrike API</title>
    <style>
        body { background: #0a0e17; color: #e0e6ed; font-family: 'Segoe UI', sans-serif;
               display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { text-align: center; max-width: 600px; }
        h1 { color: #ff4444; font-size: 2.5em; }
        a { color: #00d4ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .badge { display: inline-block; padding: 4px 12px; border-radius: 4px;
                 background: #1a1f2e; border: 1px solid #00d4ff; margin: 5px; }
    </style>
    </head>
    <body>
    <div class="container">
        <h1>🔥 PhantomStrike</h1>
        <p style="color: #888; font-style: italic;">"See Everything. Strike Anywhere. Leave Nothing."</p>
        <p>AI-Powered Offensive Cybersecurity Framework</p>
        <p style="margin-top: 20px;">
            <a href="/docs" class="badge">📖 API Docs (Swagger)</a>
            <a href="/redoc" class="badge">📚 ReDoc</a>
            <a href="/api/status" class="badge">⚡ Status</a>
            <a href="/api/modules" class="badge">📦 Modules</a>
        </p>
        <p style="margin-top: 30px; color: #555; font-size: 0.9em;">
            ⚠️ Authorized penetration testing only
        </p>
    </div>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    """Health check for Render/deployment platforms."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/status")
async def get_status(engine: PhantomEngine = Depends(get_engine)):
    """Get full engine status — modules, AI providers, event stats."""
    status = engine.get_status()
    # Make it JSON-serializable
    return JSONResponse(content={
        "session_id": status["session_id"],
        "running": status["running"],
        "uptime_seconds": round(status["uptime_seconds"], 2),
        "modules_loaded": status["modules_loaded"],
        "modules": status["modules"],
        "results_stored": status["results_stored"],
    })


@app.get("/api/modules")
async def list_modules(engine: PhantomEngine = Depends(get_engine)):
    """List all loaded offensive modules."""
    return {"modules": engine.list_modules(), "total": len(engine.list_modules())}


# ─── Scan Endpoints ──────────────────────────────────────────────

@app.post("/api/scan")
async def run_scan(request: ScanRequest, engine: PhantomEngine = Depends(get_engine)):
    """Run a scan with selected modules against a target."""
    results = await engine.execute_scan(
        target=request.target,
        module_names=request.modules if request.modules else None,
    )
    return {
        "target": request.target,
        "results": _serialize_results(results),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/scan/full")
async def run_full_chain(request: FullChainRequest, engine: PhantomEngine = Depends(get_engine)):
    """Execute the complete kill chain against a target."""
    # Temporarily set auto_exploit if requested
    original = engine.config.attack.auto_exploit
    engine.config.attack.auto_exploit = request.auto_exploit

    results = await engine.execute_full_chain(request.target)

    engine.config.attack.auto_exploit = original
    return {
        "target": request.target,
        "kill_chain_results": _serialize_results(results),
        "timestamp": datetime.now().isoformat(),
    }


# ─── Individual Module Endpoints ─────────────────────────────────

@app.post("/api/module/{module_name}")
async def run_module(module_name: str, request: ModuleRunRequest,
                     engine: PhantomEngine = Depends(get_engine)):
    """Run a specific module against a target."""
    result = await engine.execute_module(module_name, request.target, request.options)
    return {
        "module": module_name,
        "target": request.target,
        "result": _serialize_results(result),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/osint")
async def run_osint(request: ModuleRunRequest, engine: PhantomEngine = Depends(get_engine)):
    """OSINT scan — subdomains, emails, DNS, tech detection."""
    return _serialize_results(
        await engine.execute_module("phantom-osint", request.target, request.options)
    )


@app.post("/api/network")
async def run_network(request: ModuleRunRequest, engine: PhantomEngine = Depends(get_engine)):
    """Network scan — port scan, banner grab, service detection."""
    return _serialize_results(
        await engine.execute_module("phantom-network", request.target, request.options)
    )


@app.post("/api/web")
async def run_web(request: ModuleRunRequest, engine: PhantomEngine = Depends(get_engine)):
    """Web vuln scan — SQLi, XSS, LFI, SSRF, RCE."""
    return _serialize_results(
        await engine.execute_module("phantom-web", request.target, request.options)
    )


@app.post("/api/cloud")
async def run_cloud(request: ModuleRunRequest, engine: PhantomEngine = Depends(get_engine)):
    """Cloud scan — S3, Azure, GCP, metadata SSRF."""
    return _serialize_results(
        await engine.execute_module("phantom-cloud", request.target, request.options)
    )


@app.post("/api/identity")
async def run_identity(request: ModuleRunRequest, engine: PhantomEngine = Depends(get_engine)):
    """Identity attacks — JWT, OAuth, auth bypass."""
    return _serialize_results(
        await engine.execute_module("phantom-identity", request.target, request.options)
    )


@app.post("/api/cred")
async def run_cred(request: ModuleRunRequest, engine: PhantomEngine = Depends(get_engine)):
    """Credential attacks — password spray, brute force, hash crack."""
    return _serialize_results(
        await engine.execute_module("phantom-cred", request.target, request.options)
    )


@app.post("/api/stealth")
async def run_stealth(request: ModuleRunRequest, engine: PhantomEngine = Depends(get_engine)):
    """Stealth — generate polymorphic payloads."""
    return _serialize_results(
        await engine.execute_module("phantom-stealth", request.target, request.options)
    )


# ─── AI Endpoints ────────────────────────────────────────────────

@app.post("/api/ai/query")
async def ai_query(request: AIQueryRequest, engine: PhantomEngine = Depends(get_engine)):
    """Query the AI engine directly."""
    try:
        response = await engine.ai_engine.query(
            prompt=request.prompt,
            system_prompt=request.system_prompt or None,
            provider=request.provider or None,
        )
        return {
            "content": response.content,
            "provider": response.provider,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/status")
async def ai_status(engine: PhantomEngine = Depends(get_engine)):
    """Get AI provider status — active, requests, rate limits."""
    return {"providers": engine.ai_engine.get_status()}


@app.post("/api/ai/plan")
async def ai_plan_attack(request: ModuleRunRequest,
                         engine: PhantomEngine = Depends(get_engine)):
    """AI-powered attack chain planning."""
    try:
        from phantom.ai.attack_planner import AttackPlanner
        planner = AttackPlanner(engine.ai_engine)
        plan = await planner.plan_attack(request.options or {"target": request.target})
        return {"attack_plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── C2 Endpoints ────────────────────────────────────────────────

@app.post("/api/c2/checkin")
async def c2_checkin(request: C2CheckinRequest,
                     engine: PhantomEngine = Depends(get_engine)):
    """C2 agent check-in endpoint."""
    c2_module = engine.get_module("phantom-c2")
    if not c2_module:
        raise HTTPException(status_code=503, detail="C2 module not loaded")

    if request.operation == "register":
        result = await c2_module.run("", {
            "operation": "register_agent",
            "hostname": request.hostname or request.user,
            "os_info": request.os_info,
            "username": request.username or request.user,
        })
        data = result.data if hasattr(result, "data") else {}
        return {"agent_id": data.get("registered", ""), "commands": []}

    elif request.operation == "checkin":
        # Return pending commands for this agent
        agent = c2_module._agents.get(request.agent_id)
        if agent:
            agent.last_seen = datetime.now()
            commands = agent.pending_commands.copy()
            agent.pending_commands.clear()
            return {"commands": commands}
        return {"commands": []}

    elif request.operation == "result":
        # Agent sending command result
        agent = c2_module._agents.get(request.agent_id)
        if agent:
            agent.command_history.append({
                "command_id": request.command_id,
                "output": request.output,
                "received_at": datetime.now().isoformat(),
            })
        return {"status": "ok"}

    return {"status": "unknown_operation"}


@app.get("/api/c2/agents")
async def c2_list_agents(engine: PhantomEngine = Depends(get_engine)):
    """List all C2 agents."""
    c2_module = engine.get_module("phantom-c2")
    if not c2_module:
        return {"agents": {}}

    agents = {}
    for aid, agent in c2_module._agents.items():
        agents[aid] = {
            "hostname": agent.hostname,
            "ip": agent.ip_address,
            "os": agent.os_info,
            "user": agent.username,
            "status": agent.status.value,
            "last_seen": agent.last_seen.isoformat(),
            "pending_commands": len(agent.pending_commands),
            "command_history": agent.command_history[-10:],
        }
    return {"agents": agents, "total": len(agents)}


@app.post("/api/c2/command/{agent_id}")
async def c2_send_command(agent_id: str, request: dict,
                          engine: PhantomEngine = Depends(get_engine)):
    """Send a command to a C2 agent."""
    c2_module = engine.get_module("phantom-c2")
    if not c2_module:
        raise HTTPException(status_code=503, detail="C2 module not loaded")
    if agent_id not in c2_module._agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    cmd = c2_module._queue_command(agent_id, request.get("command", ""))
    return {"command_id": cmd.command_id, "status": "queued"}


@app.post("/api/c2/generate")
async def c2_generate_agent(request: dict,
                            engine: PhantomEngine = Depends(get_engine)):
    """Generate C2 agent payload."""
    c2_module = engine.get_module("phantom-c2")
    if not c2_module:
        raise HTTPException(status_code=503, detail="C2 module not loaded")

    result = await c2_module.run("", {
        "operation": "generate_agent",
        "lhost": request.get("lhost", "0.0.0.0"),
        "lport": request.get("lport", 8443),
        "channel": request.get("channel", "https"),
        "interval": request.get("interval", 30),
    })
    return result.data if hasattr(result, "data") else {}


# ─── Results Endpoints ───────────────────────────────────────────

@app.get("/api/results")
async def get_results(engine: PhantomEngine = Depends(get_engine)):
    """Get all stored scan results."""
    return {"results": _serialize_results(engine.get_results())}


# ─── Utility ─────────────────────────────────────────────────────

def _serialize_results(obj) -> dict | list:
    """Recursively make objects JSON-serializable."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _serialize_results(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_results(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return _serialize_results(obj.__dict__)
    return str(obj)
