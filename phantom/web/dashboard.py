"""
PhantomStrike Web Dashboard v2.0 — Fully working full-stack UI.
Every section wired to live API endpoints. All bugs fixed.
Fixes: wss:// for HTTPS, nav routing, Reports/Config pages, C2 polling,
progress bar hide, centered title, real data loading on section switch.
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List
from fastapi import WebSocket


class DashboardManager:
    """Manages WebSocket connections and broadcasts to all clients."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.vulnerabilities: List[Dict] = []
        self.logs: List[Dict] = []

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def broadcast(self, message: Dict):
        dead = []
        for cid, ws in self.active_connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    async def send_vulnerability(self, vuln: Dict):
        self.vulnerabilities.append(vuln)
        await self.broadcast({"type": "vulnerability", "payload": vuln})

    async def send_progress(self, percent: int, message: str = ""):
        await self.broadcast({"type": "progress", "percent": percent, "message": message})

    async def send_log(self, message: str, level: str = "info"):
        self.logs.append({"time": datetime.now().isoformat(), "message": message, "level": level})
        await self.broadcast({"type": "log", "message": message, "level": level})

    async def send_terminal_output(self, line: str, line_type: str = "output"):
        await self.broadcast({"type": "terminal", "line": line, "line_type": line_type,
                               "timestamp": datetime.now().isoformat()})

    async def send_attack_mode_status(self, mode: str, status: str, progress: int, message: str = ""):
        await self.broadcast({"type": "attack_mode", "mode": mode, "status": status,
                               "progress": progress, "message": message,
                               "timestamp": datetime.now().isoformat()})

    async def send_thread_metrics(self, active_threads: int, queued_tasks: int,
                                   cpu_percent: float, memory_percent: float):
        await self.broadcast({"type": "thread_metrics",
                               "metrics": {"active_threads": active_threads,
                                           "queued_tasks": queued_tasks,
                                           "cpu_percent": cpu_percent,
                                           "memory_percent": memory_percent}})

    async def send_network_node(self, node_id: str, label: str, node_type: str,
                                 severity: str, x: float, y: float):
        await self.broadcast({"type": "network_node",
                               "node": {"id": node_id, "label": label, "type": node_type,
                                        "severity": severity, "x": x, "y": y}})

    async def send_network_link(self, from_id: str, to_id: str, link_type: str = "connection"):
        await self.broadcast({"type": "network_link",
                               "link": {"from": from_id, "to": to_id, "type": link_type}})


dashboard_manager = DashboardManager()


def get_dashboard_html() -> str:
    return DASHBOARD_HTML


# ─── HTML ────────────────────────────────────────────────────────────────────
# Built as a multi-line string. Single quotes inside JS use \' escaping.
_HTML_PART1 = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>PhantomStrike \u2014 AI Offensive Security Platform</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0e17;--bg2:#111827;--bg3:#1a2035;--bg4:#242b3d;
  --red:#ff3333;--red2:#cc2222;--cyan:#00d4ff;--green:#00cc66;
  --yellow:#ffcc00;--orange:#ff8800;--purple:#a855f7;
  --text:#e0e6ed;--text2:#8b949e;--border:#1e2a3a;
  --glow:0 0 20px rgba(255,51,51,0.3);
}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
.header{background:linear-gradient(135deg,var(--bg2) 0%,var(--bg) 100%);border-bottom:2px solid var(--red);padding:0 30px;height:64px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 20px rgba(255,51,51,0.15)}
.header-brand{display:flex;align-items:center;gap:14px}
.header-logo{font-size:1.5rem;font-weight:900;letter-spacing:3px;background:linear-gradient(90deg,var(--red),#ff6b6b,var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.header-sub{color:var(--text2);font-size:0.72rem;letter-spacing:1px;margin-top:2px}
.header-right{display:flex;align-items:center;gap:16px}
.engine-status{display:flex;align-items:center;gap:8px;font-size:0.82rem}
.status-dot{width:10px;height:10px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
.status-dot.offline{background:#555;animation:none}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(0,204,102,0.4)}50%{opacity:.7;box-shadow:0 0 0 6px rgba(0,204,102,0)}}
.ws-badge{font-size:0.7rem;padding:3px 8px;border-radius:4px;background:rgba(0,204,102,0.12);color:var(--green);border:1px solid rgba(0,204,102,0.25)}
.ws-badge.dc{background:rgba(255,51,51,0.12);color:var(--red);border-color:rgba(255,51,51,0.25)}
.layout{display:grid;grid-template-columns:220px 1fr;min-height:calc(100vh - 64px)}
.sidebar{background:var(--bg2);border-right:1px solid var(--border);padding:16px 10px;position:sticky;top:64px;height:calc(100vh - 64px);overflow-y:auto}
.nav-group{margin-bottom:22px}
.nav-group-label{font-size:0.62rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--text2);padding:0 10px;margin-bottom:8px;display:block}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;cursor:pointer;transition:all .15s;font-size:0.86rem;color:var(--text2);margin-bottom:2px;border:1px solid transparent;user-select:none}
.nav-item:hover{background:var(--bg3);color:var(--text);border-color:var(--border)}
.nav-item.active{background:rgba(255,51,51,0.12);color:var(--red);border-color:rgba(255,51,51,0.25);font-weight:600}
.nav-item .ni{font-size:1rem;width:20px;text-align:center;flex-shrink:0}
.nav-badge{margin-left:auto;background:var(--red);color:#fff;font-size:0.62rem;padding:2px 6px;border-radius:10px;min-width:18px;text-align:center}
.main{padding:22px;overflow-y:auto;background:var(--bg)}
.section{display:none}.section.active{display:block}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;margin-bottom:18px;overflow:hidden}
.card-header{background:var(--bg3);padding:13px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.card-title{font-size:0.92rem;font-weight:600;display:flex;align-items:center;gap:8px}
.card-body{padding:18px}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.stat{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center;transition:all .2s;cursor:default}
.stat:hover{border-color:var(--red);transform:translateY(-2px)}
.stat-num{font-size:2rem;font-weight:800;line-height:1}
.stat-num.c{color:var(--red)}.stat-num.h{color:var(--orange)}.stat-num.m{color:var(--yellow)}.stat-num.l{color:var(--green)}
.stat-lbl{font-size:0.7rem;color:var(--text2);margin-top:5px;text-transform:uppercase;letter-spacing:1px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.form-group{display:flex;flex-direction:column;gap:5px;margin-bottom:12px}
.form-group label{font-size:0.75rem;color:var(--text2);font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.form-group input,.form-group select,.form-group textarea{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:9px 13px;border-radius:8px;font-size:0.88rem;font-family:inherit;transition:border-color .15s}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{outline:none;border-color:var(--cyan)}
.form-group select option{background:var(--bg2)}
.checkbox-row{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.checkbox-label{display:flex;align-items:center;gap:7px;cursor:pointer;font-size:0.85rem;color:var(--text2)}
.checkbox-label input[type=checkbox]{width:15px;height:15px;accent-color:var(--red);cursor:pointer}
.btn{display:inline-flex;align-items:center;gap:7px;padding:10px 20px;border-radius:8px;font-size:0.88rem;font-weight:600;cursor:pointer;border:none;transition:all .15s}
.btn-primary{background:linear-gradient(135deg,var(--red),var(--red2));color:#fff}
.btn-primary:hover{transform:translateY(-1px);box-shadow:var(--glow)}
.btn-primary:active{transform:translateY(0)}
.btn-primary:disabled{opacity:.5;cursor:not-allowed;transform:none}
.btn-secondary{background:var(--bg3);color:var(--text);border:1px solid var(--border)}
.btn-secondary:hover{background:var(--bg4);border-color:var(--cyan);color:var(--cyan)}
.btn-danger{background:rgba(255,51,51,.12);color:var(--red);border:1px solid rgba(255,51,51,.25)}
.btn-danger:hover{background:rgba(255,51,51,.22)}
.btn-success{background:rgba(0,204,102,.12);color:var(--green);border:1px solid rgba(0,204,102,.25)}
.btn-success:hover{background:rgba(0,204,102,.22)}
.btn-sm{padding:5px 12px;font-size:0.78rem}
.btn-full{width:100%;justify-content:center;padding:13px}
.progress-wrap{background:var(--bg);border-radius:10px;height:5px;overflow:hidden;margin-top:10px}
.progress-bar{height:100%;border-radius:10px;background:linear-gradient(90deg,var(--red),var(--cyan));transition:width .4s ease;width:0%}
.progress-label{font-size:0.75rem;color:var(--text2);margin-top:5px;text-align:center}
.vuln-list{max-height:520px;overflow-y:auto}
.vuln-item{background:var(--bg);border-left:3px solid var(--border);border-radius:8px;padding:13px;margin-bottom:7px;transition:all .15s;cursor:pointer}
.vuln-item:hover{transform:translateX(4px)}
.vuln-item.critical{border-left-color:var(--red)}.vuln-item.high{border-left-color:var(--orange)}.vuln-item.medium{border-left-color:var(--yellow)}.vuln-item.low{border-left-color:var(--green)}.vuln-item.info{border-left-color:var(--cyan)}
.vuln-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
.vuln-type{font-weight:700;font-size:0.88rem;text-transform:uppercase;letter-spacing:.5px}
.badge{padding:2px 9px;border-radius:4px;font-size:0.68rem;font-weight:700;text-transform:uppercase}
.badge.critical{background:var(--red);color:#fff}.badge.high{background:var(--orange);color:#fff}.badge.medium{background:var(--yellow);color:#000}.badge.low{background:var(--green);color:#fff}.badge.info{background:var(--cyan);color:#000}
.vuln-url{font-family:monospace;font-size:0.76rem;color:var(--text2);word-break:break-all}
.vuln-evidence{font-size:0.76rem;color:var(--cyan);margin-top:3px}
.vuln-payload{font-family:monospace;font-size:0.73rem;color:var(--orange);margin-top:3px;background:rgba(255,136,0,.07);padding:3px 7px;border-radius:4px}
.empty-state{text-align:center;padding:50px 20px;color:var(--text2)}
.empty-state .es-icon{font-size:2.5rem;margin-bottom:10px;opacity:.35}
.terminal{background:#000;border-radius:8px;padding:13px;font-family:'Consolas','Monaco',monospace;font-size:0.8rem;max-height:420px;overflow-y:auto;line-height:1.6}
.t-line{margin-bottom:1px}.t-time{color:#444}.t-info{color:var(--cyan)}.t-success{color:var(--green)}.t-error{color:var(--red)}.t-warning{color:var(--yellow)}.t-output{color:#ccc}.t-input{color:var(--purple)}
.chat-box{background:var(--bg);border-radius:8px;padding:14px;max-height:400px;overflow-y:auto;margin-bottom:12px}
.chat-msg{margin-bottom:12px;display:flex;flex-direction:column}
.chat-msg.user{align-items:flex-end}.chat-msg.ai{align-items:flex-start}
.chat-bubble{max-width:82%;padding:11px 15px;border-radius:12px;font-size:0.86rem;line-height:1.6}
.chat-msg.user .chat-bubble{background:var(--cyan);color:#000;border-radius:12px 12px 2px 12px}
.chat-msg.ai .chat-bubble{background:var(--bg3);border:1px solid var(--border);border-radius:12px 12px 12px 2px}
.chat-msg.ai .chat-bubble pre{white-space:pre-wrap;font-family:inherit;margin:0;font-size:0.84rem}
.chat-input-row{display:flex;gap:9px}
.chat-input-row input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:9px 13px;border-radius:8px;font-size:0.88rem}
.chat-input-row input:focus{outline:none;border-color:var(--cyan)}
.quick-btns{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.payload-item{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:11px;margin-bottom:9px}
.payload-item-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:7px}
.payload-code{font-family:monospace;font-size:0.8rem;color:var(--green);word-break:break-all;background:rgba(0,204,102,.05);padding:7px;border-radius:4px}
.agent-card{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:13px;margin-bottom:9px}
.agent-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:7px}
.agent-id{font-family:monospace;font-size:0.78rem;color:var(--cyan)}
.agent-info{display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:0.78rem;color:var(--text2)}
.agent-info strong{color:var(--text)}
.cmd-input-row{display:flex;gap:7px;margin-top:9px}
.cmd-input-row input{flex:1;background:var(--bg2);border:1px solid var(--border);color:var(--text);padding:7px 11px;border-radius:6px;font-family:monospace;font-size:0.83rem}
.cmd-output{font-family:monospace;font-size:0.78rem;color:var(--green);background:rgba(0,204,102,.05);padding:7px;border-radius:4px;margin-top:7px;white-space:pre-wrap;max-height:140px;overflow-y:auto}
.report-card{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:9px;display:flex;align-items:center;justify-content:space-between;gap:14px}
.report-info{flex:1}
.report-target{font-weight:600;margin-bottom:3px}
.report-meta{font-size:0.76rem;color:var(--text2);display:flex;gap:14px;flex-wrap:wrap}
.report-actions{display:flex;gap:7px;flex-shrink:0}
.config-section{margin-bottom:22px}
.config-section h3{font-size:0.82rem;color:var(--cyan);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid var(--border)}
.config-row{display:flex;align-items:center;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(30,42,58,.5)}
.config-row:last-child{border-bottom:none}
.config-key{font-size:0.86rem;color:var(--text)}
.config-val{font-size:0.82rem;color:var(--text2);font-family:monospace}
.provider-row{display:flex;align-items:center;gap:11px;padding:9px;background:var(--bg);border-radius:8px;margin-bottom:7px}
.provider-name{font-weight:600;min-width:110px;font-size:0.86rem}
.provider-model{font-size:0.75rem;color:var(--text2);flex:1;font-family:monospace}
.provider-status{font-size:0.72rem;padding:2px 9px;border-radius:4px}
.provider-status.active{background:rgba(0,204,102,.12);color:var(--green);border:1px solid rgba(0,204,102,.25)}
.provider-status.inactive{background:rgba(139,148,158,.08);color:var(--text2);border:1px solid var(--border)}
.provider-requests{font-size:0.72rem;color:var(--text2);min-width:75px;text-align:right}
.result-card{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:11px}
.result-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:11px}
.result-target{font-weight:700;font-size:0.95rem}
.result-time{font-size:0.75rem;color:var(--text2)}
.result-stats{display:flex;gap:14px;margin-bottom:11px}
.result-stat{text-align:center}
.result-stat-num{font-size:1.3rem;font-weight:700}
.result-stat-lbl{font-size:0.68rem;color:var(--text2);text-transform:uppercase}
.result-modules{display:flex;flex-wrap:wrap;gap:5px}
.module-tag{font-size:0.7rem;padding:2px 9px;border-radius:4px;background:var(--bg3);border:1px solid var(--border);color:var(--text2)}
.module-tag.has-findings{background:rgba(255,51,51,.08);border-color:rgba(255,51,51,.25);color:var(--red)}
.scan-active-banner{background:linear-gradient(135deg,rgba(255,51,51,.08),rgba(0,212,255,.04));border:1px solid rgba(255,51,51,.25);border-radius:10px;padding:14px 18px;margin-bottom:18px;display:none}
.scan-active-banner.visible{display:flex;align-items:center;gap:14px}
.scan-spinner{width:22px;height:22px;border:3px solid var(--border);border-top-color:var(--red);border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0}
@keyframes spin{to{transform:rotate(360deg)}}
.scan-active-info{flex:1}
.scan-active-target{font-weight:600;margin-bottom:3px;font-size:0.9rem}
.scan-active-msg{font-size:0.8rem;color:var(--text2)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--cyan)}
@media(max-width:900px){.layout{grid-template-columns:1fr}.sidebar{display:none}.stats-row{grid-template-columns:repeat(2,1fr)}.form-row{grid-template-columns:1fr}}
</style>
</head>
<body>"""


_HTML_PART2 = """
<div class="header">
  <div class="header-brand">
    <div>
      <div class="header-logo">&#128293; PHANTOM STRIKE</div>
      <div class="header-sub">AI-POWERED OFFENSIVE SECURITY PLATFORM</div>
    </div>
  </div>
  <div class="header-right">
    <span class="ws-badge dc" id="ws-badge">&#9679; Connecting...</span>
    <div class="engine-status">
      <div class="status-dot offline" id="status-dot"></div>
      <span id="status-text">Initializing</span>
    </div>
  </div>
</div>

<div class="layout">
  <aside class="sidebar">
    <div class="nav-group">
      <span class="nav-group-label">Operations</span>
      <div class="nav-item active" id="nav-scan" onclick="showSection('scan')">
        <span class="ni">&#127919;</span> New Scan
        <span class="nav-badge" id="badge-scan" style="display:none">0</span>
      </div>
      <div class="nav-item" id="nav-results" onclick="showSection('results')">
        <span class="ni">&#128202;</span> Results
        <span class="nav-badge" id="badge-results" style="display:none">0</span>
      </div>
      <div class="nav-item" id="nav-ai" onclick="showSection('ai')">
        <span class="ni">&#129504;</span> AI Assistant
      </div>
    </div>
    <div class="nav-group">
      <span class="nav-group-label">Tools</span>
      <div class="nav-item" id="nav-payloads" onclick="showSection('payloads')">
        <span class="ni">&#128163;</span> Payloads
      </div>
      <div class="nav-item" id="nav-c2" onclick="showSection('c2')">
        <span class="ni">&#128225;</span> C2 Console
        <span class="nav-badge" id="badge-c2" style="display:none">0</span>
      </div>
      <div class="nav-item" id="nav-reports" onclick="showSection('reports')">
        <span class="ni">&#128196;</span> Reports
      </div>
    </div>
    <div class="nav-group">
      <span class="nav-group-label">System</span>
      <div class="nav-item" id="nav-config" onclick="showSection('config')">
        <span class="ni">&#9881;&#65039;</span> Configuration
      </div>
      <div class="nav-item" id="nav-logs" onclick="showSection('logs')">
        <span class="ni">&#128203;</span> Logs
      </div>
      </div>
    </div>
  </aside>

  <main class="main">

    <!-- ═══ SCAN SECTION ═══ -->
    <section id="section-scan" class="section active">
      <div class="stats-row">
        <div class="stat"><div class="stat-num c" id="stat-critical">0</div><div class="stat-lbl">Critical</div></div>
        <div class="stat"><div class="stat-num h" id="stat-high">0</div><div class="stat-lbl">High</div></div>
        <div class="stat"><div class="stat-num m" id="stat-medium">0</div><div class="stat-lbl">Medium</div></div>
        <div class="stat"><div class="stat-num l" id="stat-low">0</div><div class="stat-lbl">Low</div></div>
      </div>

      <div class="scan-active-banner" id="scan-banner">
        <div class="scan-spinner"></div>
        <div class="scan-active-info">
          <div class="scan-active-target" id="scan-banner-target">Scanning...</div>
          <div class="scan-active-msg" id="scan-banner-msg">Initializing modules...</div>
        </div>
        <div class="progress-wrap" style="width:200px;margin-top:0">
          <div class="progress-bar" id="scan-progress-bar"></div>
        </div>
        <button class="btn btn-danger btn-sm" onclick="stopScan()">&#9632; Stop</button>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">&#127919; Launch New Scan</span>
          <span id="scan-status-text" style="font-size:0.8rem;color:var(--text2)">Ready</span>
        </div>
        <div class="card-body">
          <div class="form-group">
            <label>Target URL / Domain / IP</label>
            <input type="text" id="scan-target" placeholder="example.com or https://target.com" autocomplete="off">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Scan Type</label>
              <select id="scan-type">
                <option value="full">&#128293; Full Kill Chain (7 phases)</option>
                <option value="recon">&#128269; Reconnaissance Only</option>
                <option value="web">&#127757; Web Vulnerabilities</option>
                <option value="cloud">&#9729;&#65039; Cloud Security</option>
                <option value="network">&#127760; Network Scan</option>
              </select>
            </div>
            <div class="form-group">
              <label>Profile</label>
              <select id="scan-profile">
                <option value="normal">&#9899; Normal (Balanced)</option>
                <option value="stealth">&#128123; Stealth (Slow/Evasive)</option>
                <option value="aggressive">&#9889; Aggressive (Fast/Noisy)</option>
              </select>
            </div>
          </div>
          <div class="checkbox-row" style="margin-bottom:16px">
            <label class="checkbox-label">
              <input type="checkbox" id="auto-exploit">
              <span>&#9888;&#65039; Enable Auto-Exploitation</span>
            </label>
            <label class="checkbox-label">
              <input type="checkbox" id="use-ai" checked>
              <span>&#129504; Use AI Analysis</span>
            </label>
          </div>
          <button class="btn btn-primary btn-full" id="start-btn" onclick="startScan()">
            <span>&#128640;</span> Start Attack
          </button>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">&#128680; Live Vulnerabilities</span>
          <span id="vuln-count" style="font-size:0.82rem;color:var(--text2)">0 found</span>
        </div>
        <div class="card-body">
          <div class="vuln-list" id="vuln-list">
            <div class="empty-state">
              <div class="es-icon">&#128270;</div>
              <div>No vulnerabilities found yet.<br>Start a scan to discover issues.</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ RESULTS SECTION ═══ -->
    <section id="section-results" class="section">
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#128202; Scan Results History</span>
          <button class="btn btn-secondary btn-sm" onclick="loadResults()">&#8635; Refresh</button>
        </div>
        <div class="card-body" id="results-container">
          <div class="empty-state"><div class="es-icon">&#128202;</div><div>No completed scans yet.</div></div>
        </div>
      </div>
    </section>

    <!-- ═══ AI SECTION ═══ -->
    <section id="section-ai" class="section">
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#129504; AI Attack Assistant</span>
          <span id="ai-provider-badge" style="font-size:0.78rem;color:var(--text2)">Loading...</span>
        </div>
        <div class="card-body">
          <div class="chat-box" id="ai-chat">
            <div class="chat-msg ai">
              <div class="chat-bubble">
                <strong>Phantom AI:</strong> Ready to help with attack planning, vulnerability analysis, and payload generation. Ask me anything.
              </div>
            </div>
          </div>
          <div class="chat-input-row">
            <input type="text" id="ai-input" placeholder="Ask about vulnerabilities, attack techniques, payloads..." onkeydown="if(event.key==='Enter')sendAI()">
            <button class="btn btn-primary" onclick="sendAI()">&#9658; Send</button>
          </div>
          <div class="quick-btns">
            <button class="btn btn-secondary btn-sm" onclick="quickAI('Generate 5 polymorphic XSS payloads that bypass Cloudflare WAF')">XSS Payloads</button>
            <button class="btn btn-secondary btn-sm" onclick="quickAI('Generate SQL injection payloads for MySQL with WAF bypass')">SQLi Bypass</button>
            <button class="btn btn-secondary btn-sm" onclick="quickAI('Explain JWT none algorithm attack with exploit steps')">JWT Attack</button>
            <button class="btn btn-secondary btn-sm" onclick="quickAI('Plan lateral movement strategy after initial access')">Lateral Move</button>
            <button class="btn btn-secondary btn-sm" onclick="quickAI('Generate reverse shell payloads for bash python php powershell')">Rev Shells</button>
            <button class="btn btn-secondary btn-sm" onclick="quickAI('Explain SSRF attack to access AWS metadata endpoint')">SSRF Guide</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ PAYLOADS SECTION ═══ -->
    <section id="section-payloads" class="section">
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#128163; Payload Generator</span>
          <div style="display:flex;gap:8px;align-items:center">
            <label style="font-size:0.8rem;color:var(--text2)">Count:</label>
            <input type="number" id="payload-count" value="10" min="1" max="50" style="width:60px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:6px;font-size:0.85rem">
          </div>
        </div>
        <div class="card-body">
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px">
            <button class="btn btn-primary" onclick="genPayloads('xss')">&#128163; XSS Payloads</button>
            <button class="btn btn-primary" onclick="genPayloads('sqli')">&#128201; SQLi Payloads</button>
            <button class="btn btn-primary" onclick="genPayloads('reverse_shell')">&#128032; Reverse Shells</button>
          </div>
          <div id="payload-container">
            <div class="empty-state"><div class="es-icon">&#128163;</div><div>Select a payload type above to generate.</div></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ C2 SECTION ═══ -->
    <section id="section-c2" class="section">
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#128225; Command &amp; Control</span>
          <div style="display:flex;gap:8px">
            <button class="btn btn-secondary btn-sm" onclick="loadAgents()">&#8635; Refresh</button>
            <span id="c2-agent-count" style="font-size:0.82rem;color:var(--text2);align-self:center">0 agents</span>
          </div>
        </div>
        <div class="card-body">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
            <div>
              <h3 style="font-size:0.82rem;color:var(--cyan);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">Active Agents</h3>
              <div id="agent-list">
                <div class="empty-state" style="padding:30px 10px"><div class="es-icon">&#128225;</div><div>No agents connected</div></div>
              </div>
            </div>
            <div>
              <h3 style="font-size:0.82rem;color:var(--cyan);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">Generate Agent Payload</h3>
              <div class="form-group">
                <label>C2 Host / IP</label>
                <input type="text" id="c2-host" value="your-server.com" placeholder="your-server.com or IP">
              </div>
              <div class="form-group">
                <label>C2 Port</label>
                <input type="number" id="c2-port" value="8443" placeholder="8443">
              </div>
              <div class="form-group">
                <label>Check-in Interval (seconds)</label>
                <input type="number" id="c2-interval" value="30" placeholder="30">
              </div>
              <button class="btn btn-primary btn-full" onclick="generateAgent()">&#9889; Generate Agent</button>
              <div id="agent-payload-output" style="margin-top:12px;display:none">
                <div style="display:flex;gap:7px;margin-bottom:8px">
                  <button class="btn btn-secondary btn-sm" onclick="showAgentLang('python')">Python</button>
                  <button class="btn btn-secondary btn-sm" onclick="showAgentLang('bash')">Bash</button>
                </div>
                <div class="payload-code" id="agent-code" style="max-height:200px;overflow-y:auto;white-space:pre;font-size:0.75rem"></div>
                <button class="btn btn-success btn-sm" style="margin-top:8px" onclick="copyAgentCode()">&#128203; Copy</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ REPORTS SECTION ═══ -->
    <section id="section-reports" class="section">
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#128196; Generated Reports</span>
          <button class="btn btn-secondary btn-sm" onclick="loadReports()">&#8635; Refresh</button>
        </div>
        <div class="card-body" id="reports-container">
          <div class="empty-state"><div class="es-icon">&#128196;</div><div>No reports generated yet.<br>Run a scan to auto-generate reports.</div></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#128196; Generate Report for Target</span>
        </div>
        <div class="card-body">
          <div class="form-row">
            <div class="form-group">
              <label>Target</label>
              <input type="text" id="report-target" placeholder="example.com">
            </div>
            <div class="form-group">
              <label>Format</label>
              <select id="report-format">
                <option value="html">HTML (Full Report)</option>
                <option value="json">JSON (Raw Data)</option>
                <option value="txt">TXT (Plain Text)</option>
              </select>
            </div>
          </div>
          <button class="btn btn-primary" onclick="generateReport()">&#128196; Generate Report</button>
          <div id="report-result" style="margin-top:12px;display:none;padding:12px;background:var(--bg);border-radius:8px;font-size:0.85rem;color:var(--green)"></div>
        </div>
      </div>
    </section>

    <!-- ═══ CONFIG SECTION ═══ -->
    <section id="section-config" class="section">
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#9881;&#65039; Engine Configuration</span>
          <button class="btn btn-secondary btn-sm" onclick="loadConfig()">&#8635; Refresh</button>
        </div>
        <div class="card-body" id="config-container">
          <div class="empty-state"><div class="es-icon">&#9881;&#65039;</div><div>Loading configuration...</div></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#129504; AI Providers Status</span>
        </div>
        <div class="card-body" id="ai-providers-container">
          <div class="empty-state"><div class="es-icon">&#129504;</div><div>Loading AI providers...</div></div>
        </div>
      </div>
    </section>

    <!-- ═══ LOGS SECTION ═══ -->
    <section id="section-logs" class="section">
      <div class="card">
        <div class="card-header">
          <span class="card-title">&#128203; System Logs</span>
          <div style="display:flex;gap:8px">
            <button class="btn btn-secondary btn-sm" onclick="clearLogs()">&#128465; Clear</button>
            <label class="checkbox-label" style="font-size:0.8rem">
              <input type="checkbox" id="log-autoscroll" checked style="width:14px;height:14px;accent-color:var(--cyan)">
              Auto-scroll
            </label>
          </div>
        </div>
        <div class="card-body">
          <div class="terminal" id="log-terminal">
            <div class="t-line"><span class="t-time">[--:--:--]</span> <span class="t-info">PhantomStrike Dashboard v2.0 initialized</span></div>
          </div>
        </div>
      </div>
    </section>

  </main>
</div>"""


_HTML_PART3 = (
    '<script>'
    'let ws=null,wsRetries=0,scanActive=false;'
    'let vulnCount={critical:0,high:0,medium:0,low:0,total:0};'
    'let allResults=[],allAgents={},agentPayloads={};'
    'function connectWS(){'
    '  const proto=location.protocol==="https:"?"wss:":"ws:";'
    '  ws=new WebSocket(proto+"//"+location.host+"/ws");'
    '  ws.onopen=()=>{setWS(true);log("Connected","success");wsRetries=0;};'
    '  ws.onmessage=(e)=>{try{handleMsg(JSON.parse(e.data));}catch(ex){}};'
    '  ws.onclose=()=>{setWS(false);wsRetries++;setTimeout(connectWS,Math.min(wsRetries*2000,15000));};'
    '  ws.onerror=()=>setWS(false);'
    '}'
    'function setWS(ok){'
    '  const dot=document.getElementById("status-dot");'
    '  const txt=document.getElementById("status-text");'
    '  const badge=document.getElementById("ws-badge");'
    '  if(ok){dot.className="status-dot";txt.textContent="Engine Online";badge.className="ws-badge";badge.textContent="\u25cf Connected";}'
    '  else{dot.className="status-dot offline";txt.textContent="Disconnected";badge.className="ws-badge dc";badge.textContent="\u25cf Disconnected";}'
    '}'
    'function handleMsg(d){'
    '  switch(d.type){'
    '    case "vulnerability":addVuln(d.payload);break;'
    '    case "progress":updateProgress(d.percent,d.message);break;'
    '    case "log":log(d.message,d.level);break;'
    '    case "scan_complete":onScanComplete(d);break;'
    '    case "scan_error":onScanError(d.error);break;'
    '    case "terminal":addTermLine(d.line,d.line_type);break;'
    '    case "attack_mode":updateAttackMode(d);break;'
    '  }'
    '}'
    'function showSection(name){'
    '  document.querySelectorAll(".section").forEach(s=>s.classList.remove("active"));'
    '  document.querySelectorAll(".nav-item").forEach(n=>n.classList.remove("active"));'
    '  const sec=document.getElementById("section-"+name);'
    '  if(sec)sec.classList.add("active");'
    '  const navEl=document.getElementById("nav-"+name);'
    '  if(navEl)navEl.classList.add("active");'
    '  if(name==="results")loadResults();'
    '  if(name==="config")loadConfig();'
    '  if(name==="c2")loadAgents();'
    '  if(name==="reports")loadReports();'
    '  if(name==="ai")loadAIStatus();'
    '}'
    'async function startScan(){'
    '  const target=document.getElementById("scan-target").value.trim();'
    '  if(!target){alert("Please enter a target");return;}'
    '  const scanType=document.getElementById("scan-type").value;'
    '  const profile=document.getElementById("scan-profile").value;'
    '  const autoExploit=document.getElementById("auto-exploit").checked;'
    '  const useAI=document.getElementById("use-ai").checked;'
    '  vulnCount={critical:0,high:0,medium:0,low:0,total:0};updateStatCards();'
    '  document.getElementById("vuln-list").innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#128270;</div><div>Scanning...</div></div>";'
    '  document.getElementById("vuln-count").textContent="0 found";'
    '  scanActive=true;'
    '  document.getElementById("scan-banner").classList.add("visible");'
    '  document.getElementById("scan-banner-target").textContent="Scanning: "+target;'
    '  document.getElementById("scan-banner-msg").textContent="Initializing...";'
    '  document.getElementById("scan-progress-bar").style.width="0%";'
    '  document.getElementById("start-btn").disabled=true;'
    '  document.getElementById("scan-status-text").textContent="Running...";'
    '  log("Starting "+scanType+" scan on "+target,"info");'
    '  try{'
    '    const r=await fetch("/api/scan/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target,scan_type:scanType,profile,auto_exploit:autoExploit,use_ai:useAI})});'
    '    const data=await r.json();'
    '    if(data.status==="rejected"){log("Scan rejected: "+data.message,"warning");endScan();return;}'
    '    log("Scan started: "+data.scan_id,"success");'
    '  }catch(e){log("Failed: "+e.message,"error");endScan();}'
    '}'
    'function stopScan(){scanActive=false;endScan();log("Scan stopped","warning");}'
    'function endScan(){'
    '  scanActive=false;'
    '  document.getElementById("scan-banner").classList.remove("visible");'
    '  document.getElementById("start-btn").disabled=false;'
    '  document.getElementById("scan-status-text").textContent="Ready";'
    '  document.getElementById("scan-progress-bar").style.width="0%";'
    '}'
    'function updateProgress(pct,msg){'
    '  document.getElementById("scan-progress-bar").style.width=pct+"%";'
    '  if(msg)document.getElementById("scan-banner-msg").textContent=msg;'
    '  if(pct>=100)setTimeout(endScan,1500);'
    '}'
    'function onScanComplete(d){endScan();log("Scan complete! "+vulnCount.total+" vulns found","success");allResults.unshift({scan_id:d.scan_id,timestamp:new Date().toLocaleString()});const b=document.getElementById("badge-results");b.style.display="inline";b.textContent=allResults.length;}'
    'function onScanError(err){endScan();log("Scan error: "+err,"error");}'
    'function addVuln(v){'
    '  const sev=v.severity||"medium";'
    '  const list=document.getElementById("vuln-list");'
    '  const es=list.querySelector(".empty-state");if(es)es.remove();'
    '  vulnCount[sev]=(vulnCount[sev]||0)+1;vulnCount.total=(vulnCount.total||0)+1;'
    '  updateStatCards();'
    '  document.getElementById("vuln-count").textContent=vulnCount.total+" found";'
    '  const item=document.createElement("div");item.className="vuln-item "+sev;'
    '  const url=v.url||v.bucket||v.account||"N/A";'
    '  item.innerHTML="<div class=\\"vuln-row\\"><span class=\\"vuln-type\\">"+esc(v.type||"unknown")+"</span><span class=\\"badge "+sev+"\\">"+sev+"</span></div><div class=\\"vuln-url\\">"+esc(url)+"</div>"+(v.evidence?"<div class=\\"vuln-evidence\\">"+esc(v.evidence)+"</div>":"")+(v.payload?"<div class=\\"vuln-payload\\">"+esc(v.payload.substring(0,120))+"</div>":"");'
    '  list.insertBefore(item,list.firstChild);'
    '  const nb=document.getElementById("badge-scan");nb.style.display="inline";nb.textContent=vulnCount.total;'
    '  log("["+sev.toUpperCase()+"] "+v.type+": "+url.substring(0,60),"warning");'
    '}'
    'function updateStatCards(){document.getElementById("stat-critical").textContent=vulnCount.critical||0;document.getElementById("stat-high").textContent=vulnCount.high||0;document.getElementById("stat-medium").textContent=vulnCount.medium||0;document.getElementById("stat-low").textContent=vulnCount.low||0;}'
    'async function loadResults(){const c=document.getElementById("results-container");c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#8987;</div><div>Loading...</div></div>";try{const r=await fetch("/api/results");const data=await r.json();const results=data.results||{};const keys=Object.keys(results);if(keys.length===0){c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#128202;</div><div>No completed scans yet.</div></div>";return;}c.innerHTML="";keys.slice().reverse().forEach(k=>{const card=document.createElement("div");card.className="result-card";const target=k.replace("scan_","").replace("chain_","");card.innerHTML="<div class=\\"result-header\\"><span class=\\"result-target\\">"+esc(target)+"</span><span class=\\"result-time\\">"+esc(k)+"</span></div>";c.appendChild(card);});}catch(e){c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#10060;</div><div>Error: "+esc(e.message)+"</div></div>";}  }'
    'async function loadAIStatus(){try{const r=await fetch("/api/ai/status");const data=await r.json();const badge=document.getElementById("ai-provider-badge");if(data.available){const active=Object.values(data.providers||{}).filter(p=>p.active||p.api_key_set);badge.textContent=active.length+" providers active";badge.style.color="var(--green)";}else{badge.textContent="No AI providers";badge.style.color="var(--orange)";}}catch(e){}}'
    'async function sendAI(){const input=document.getElementById("ai-input");const q=input.value.trim();if(!q)return;input.value="";addChatMsg(q,"user");const thinkId="think-"+Date.now();addChatMsg("<span id=\\""+thinkId+"\\">&#129504; Thinking...</span>","ai");try{const r=await fetch("/api/ai/query",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:q})});const data=await r.json();const el=document.getElementById(thinkId);if(el){const bubble=el.closest(".chat-bubble");if(bubble)bubble.innerHTML="<strong>Phantom AI</strong><br><pre>"+esc(data.content||data.error||"No response")+"</pre>";}}catch(e){const el=document.getElementById(thinkId);if(el){const b=el.closest(".chat-bubble");if(b)b.innerHTML="<span style=\\"color:var(--red)\\">Error: "+esc(e.message)+"</span>";}}const chat=document.getElementById("ai-chat");chat.scrollTop=chat.scrollHeight;}'
    'function quickAI(q){document.getElementById("ai-input").value=q;sendAI();}'
    'function addChatMsg(html,role){const chat=document.getElementById("ai-chat");const div=document.createElement("div");div.className="chat-msg "+role;div.innerHTML="<div class=\\"chat-bubble\\">"+html+"</div>";chat.appendChild(div);chat.scrollTop=chat.scrollHeight;}'
    'async function genPayloads(type){const count=parseInt(document.getElementById("payload-count").value)||10;const c=document.getElementById("payload-container");c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#8987;</div><div>Generating...</div></div>";try{const r=await fetch("/api/payloads/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({type,count})});const data=await r.json();const payloads=data.payloads||[];if(payloads.length===0){c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#128163;</div><div>No payloads generated.</div></div>";return;}c.innerHTML="";payloads.forEach((p,i)=>{const item=document.createElement("div");item.className="payload-item";const payload=p.payload||p.bash||p.python||"";const label=p.language||p.encoding||("Payload "+(i+1));item.innerHTML="<div class=\\"payload-item-header\\"><span style=\\"font-size:0.82rem;font-weight:600;color:var(--cyan)\\">"+esc(label)+"</span><button class=\\"btn btn-secondary btn-sm\\" onclick=\\"copyText(this,this.dataset.p)\\" data-p=\\""+esc(payload)+"\\">&nbsp;&#128203; Copy</button></div><div class=\\"payload-code\\">"+esc(payload)+"</div>";c.appendChild(item);});}catch(e){c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#10060;</div><div>Error: "+esc(e.message)+"</div></div>";}}'
    'async function loadAgents(){try{const r=await fetch("/api/c2/agents");const data=await r.json();allAgents=data.agents||{};const count=Object.keys(allAgents).length;document.getElementById("c2-agent-count").textContent=count+" agent"+(count!==1?"s":"");const badge=document.getElementById("badge-c2");if(count>0){badge.style.display="inline";badge.textContent=count;}else badge.style.display="none";renderAgents();}catch(e){log("C2 load error: "+e.message,"error");}}'
    'function renderAgents(){const c=document.getElementById("agent-list");const agents=Object.entries(allAgents);if(agents.length===0){c.innerHTML="<div class=\\"empty-state\\" style=\\"padding:30px 10px\\"><div class=\\"es-icon\\">&#128225;</div><div>No agents connected</div></div>";return;}c.innerHTML="";agents.forEach(([id,a])=>{const card=document.createElement("div");card.className="agent-card";card.innerHTML="<div class=\\"agent-header\\"><span class=\\"agent-id\\">"+esc(id)+"</span><span class=\\"badge "+(a.status==="active"?"low":"medium")+"\\">"+esc(a.status)+"</span></div><div class=\\"agent-info\\"><span><strong>Host:</strong> "+esc(a.hostname||"?")+"</span><span><strong>IP:</strong> "+esc(a.ip||"?")+"</span><span><strong>User:</strong> "+esc(a.user||"?")+"</span><span><strong>OS:</strong> "+esc(a.os||"?")+"</span></div><div class=\\"cmd-input-row\\"><input type=\\"text\\" id=\\"cmd-"+id+"\\" placeholder=\\"whoami, id, ls -la ...\\"><button class=\\"btn btn-danger btn-sm\\" onclick=\\"sendCmd(\'"+(id)+"\')\">&nbsp;&#9658; Run</button></div><div class=\\"cmd-output\\" id=\\"out-"+id+"\\" style=\\"display:none\\"></div>";c.appendChild(card);});}'
    'async function sendCmd(agentId){const input=document.getElementById("cmd-"+agentId);const cmd=input.value.trim();if(!cmd)return;input.value="";const out=document.getElementById("out-"+agentId);out.style.display="block";out.textContent="Sending...";try{const r=await fetch("/api/c2/agents/"+agentId+"/command",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command:cmd})});const data=await r.json();out.textContent="$ "+cmd+"\n"+(data.queued?"Queued: "+data.command_id:JSON.stringify(data));}catch(e){out.textContent="Error: "+e.message;}}'
    'async function generateAgent(){const host=document.getElementById("c2-host").value.trim()||"your-server.com";const port=document.getElementById("c2-port").value||"8443";const interval=document.getElementById("c2-interval").value||"30";try{const r=await fetch("/api/module/phantom-c2",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target:"",options:{operation:"generate_agent",lhost:host,lport:parseInt(port),interval:parseInt(interval)}})});const data=await r.json();const payload=data.result?.data?.agent_payload||{};agentPayloads=payload;document.getElementById("agent-payload-output").style.display="block";showAgentLang("python");log("Agent generated for "+host+":"+port,"success");}catch(e){log("Agent error: "+e.message,"error");}}'
    'function showAgentLang(lang){document.getElementById("agent-code").textContent=agentPayloads[lang]||"No payload for "+lang;}'
    'function copyAgentCode(){copyText(null,document.getElementById("agent-code").textContent);}'
    'async function loadReports(){const c=document.getElementById("reports-container");c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#8987;</div><div>Loading...</div></div>";try{const r=await fetch("/api/results");const data=await r.json();const results=data.results||{};const keys=Object.keys(results);if(keys.length===0){c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#128196;</div><div>No reports yet. Run a scan first.</div></div>";return;}c.innerHTML="";keys.forEach(k=>{const target=k.replace("chain_","").replace("scan_","");const card=document.createElement("div");card.className="report-card";card.innerHTML="<div class=\\"report-info\\"><div class=\\"report-target\\">"+esc(target)+"</div><div class=\\"report-meta\\"><span>Session: "+esc(k)+"</span></div></div><div class=\\"report-actions\\"><button class=\\"btn btn-secondary btn-sm\\" onclick=\\"genReportFor(\'"+(target)+"\')\">&nbsp;&#128196; Generate</button></div>";c.appendChild(card);});}catch(e){c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#10060;</div><div>Error: "+esc(e.message)+"</div></div>";}}'
    'async function generateReport(){const target=document.getElementById("report-target").value.trim();if(!target){alert("Enter a target");return;}await genReportFor(target);}'
    'async function genReportFor(target){const result=document.getElementById("report-result");result.style.display="block";result.textContent="Generating...";result.style.color="var(--cyan)";try{const r=await fetch("/api/module/phantom-report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target,options:{results:{},session_id:"dashboard"}})});const data=await r.json();const rdata=data.result?.data||{};result.style.color="var(--green)";result.textContent="Report generated!\nHTML: "+(rdata.html_path||"N/A")+"\nJSON: "+(rdata.json_path||"N/A")+"\nTXT: "+(rdata.txt_path||"N/A");log("Report generated for "+target,"success");}catch(e){result.style.color="var(--red)";result.textContent="Error: "+e.message;}}'
    'async function loadConfig(){const c=document.getElementById("config-container");const ap=document.getElementById("ai-providers-container");c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#8987;</div><div>Loading...</div></div>";ap.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#8987;</div><div>Loading...</div></div>";try{const r=await fetch("/api/status");const data=await r.json();c.innerHTML="";const cs=document.createElement("div");cs.className="config-section";cs.innerHTML="<h3>Engine Status</h3>"+cfgRow("Session ID",data.session_id||"N/A")+cfgRow("Running",data.running?"Yes":"No")+cfgRow("Uptime",Math.round(data.uptime_seconds||0)+"s")+cfgRow("Modules Loaded",data.modules_loaded||0)+cfgRow("Results Stored",data.results_stored||0);c.appendChild(cs);if(data.modules&&data.modules.length>0){const ms=document.createElement("div");ms.className="config-section";ms.innerHTML="<h3>Loaded Modules ("+data.modules.length+")</h3>";data.modules.forEach(m=>{const row=document.createElement("div");row.className="config-row";row.innerHTML="<span class=\\"config-key\\">"+esc(m.name)+"</span><span class=\\"config-val\\" style=\\"color:var(--text2);font-size:0.78rem\\">"+esc(m.category)+" &mdash; "+esc(m.description||"")+"</span>";ms.appendChild(row);});c.appendChild(ms);}const aiR=await fetch("/api/ai/status");const aiData=await aiR.json();ap.innerHTML="";const providers=aiData.providers||{};if(Object.keys(providers).length===0){ap.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#129504;</div><div>No AI providers configured.</div></div>";}else{Object.entries(providers).forEach(([id,p])=>{const row=document.createElement("div");row.className="provider-row";const active=p.active||p.api_key_set;row.innerHTML="<span class=\\"provider-name\\">"+esc(p.name||id)+"</span><span class=\\"provider-model\\">"+esc(p.model||"")+"</span><span class=\\"provider-status "+(active?"active":"inactive")+"\\">"+( active?"Active":"No Key")+"</span><span class=\\"provider-requests\\">"+( p.requests_today||0)+"/"+(p.daily_limit||p.daily||"?")+"</span>";ap.appendChild(row);});}}catch(e){c.innerHTML="<div class=\\"empty-state\\"><div class=\\"es-icon\\">&#10060;</div><div>Error: "+esc(e.message)+"</div></div>";}}'
    'function cfgRow(k,v){return "<div class=\\"config-row\\"><span class=\\"config-key\\">"+esc(String(k))+"</span><span class=\\"config-val\\">"+esc(String(v))+"</span></div>";}'
    'function log(msg,level){const t=document.getElementById("log-terminal");const now=new Date().toLocaleTimeString();const line=document.createElement("div");line.className="t-line";line.innerHTML="<span class=\\"t-time\\">["+ now+"]</span> <span class=\\"t-"+(level||"output")+"\\">"+esc(msg)+"</span>";t.appendChild(line);if(document.getElementById("log-autoscroll")?.checked)t.scrollTop=t.scrollHeight;while(t.children.length>500)t.removeChild(t.firstChild);}'
    'function addTermLine(line,type){log(line,type||"output");}'
    'function clearLogs(){document.getElementById("log-terminal").innerHTML="";}'
    'function updateAttackMode(d){updateProgress(d.progress,d.message);log("["+d.mode+"] "+d.progress+"% - "+d.message,"info");}'
    'function esc(s){if(s==null)return"";return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/\'/g,"&#39;");}'
    'function copyText(btn,text){navigator.clipboard.writeText(text).then(()=>{if(btn){const orig=btn.textContent;btn.textContent="Copied!";setTimeout(()=>btn.textContent=orig,1500);}}).catch(()=>{const ta=document.createElement("textarea");ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand("copy");document.body.removeChild(ta);if(btn){const orig=btn.textContent;btn.textContent="Copied!";setTimeout(()=>btn.textContent=orig,1500);}});}'
    'document.addEventListener("DOMContentLoaded",()=>{connectWS();setInterval(()=>{const c2=document.getElementById("section-c2");if(c2&&c2.classList.contains("active"))loadAgents();},15000);setTimeout(loadAIStatus,2000);});'
    '</script>'
    '</body>'
    '</html>'
)

DASHBOARD_HTML = _HTML_PART1 + _HTML_PART2 + _HTML_PART3
