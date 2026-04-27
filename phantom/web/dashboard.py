"""
PhantomStrike Web Dashboard — Full-Stack Web UI using FastAPI + HTML/JS.
Real-time scan monitoring, results viewing, and AI interaction.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Dashboard HTML Template
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PhantomStrike Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #1a1f2e;
            --bg-tertiary: #242b3d;
            --accent-red: #ff4444;
            --accent-cyan: #00d4ff;
            --accent-green: #00cc66;
            --accent-yellow: #ffcc00;
            --text-primary: #e0e6ed;
            --text-secondary: #8b949e;
            --border-color: #30363d;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
            border-bottom: 2px solid var(--accent-red);
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 1.8rem;
            background: linear-gradient(90deg, var(--accent-red), var(--accent-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .header .tagline {
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 5px;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--accent-green);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .container {
            display: grid;
            grid-template-columns: 280px 1fr;
            min-height: calc(100vh - 80px);
        }
        
        .sidebar {
            background: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            padding: 20px;
        }
        
        .nav-section {
            margin-bottom: 25px;
        }
        
        .nav-section h3 {
            color: var(--accent-cyan);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 15px;
            margin-bottom: 5px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.95rem;
        }
        
        .nav-item:hover, .nav-item.active {
            background: var(--bg-tertiary);
            color: var(--accent-cyan);
        }
        
        .nav-item .icon {
            font-size: 1.2rem;
        }
        
        .main-content {
            padding: 30px;
            overflow-y: auto;
        }
        
        .panel {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 25px;
            overflow: hidden;
        }
        
        .panel-header {
            background: var(--bg-tertiary);
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .panel-header h2 {
            font-size: 1.1rem;
            color: var(--text-primary);
        }
        
        .panel-body {
            padding: 20px;
        }
        
        .scan-form {
            display: grid;
            gap: 20px;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .form-group label {
            font-size: 0.9rem;
            color: var(--text-secondary);
            font-weight: 500;
        }
        
        .form-group input, .form-group select {
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 1rem;
            font-family: inherit;
        }
        
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: var(--accent-cyan);
        }
        
        .btn {
            background: linear-gradient(135deg, var(--accent-red), #cc3333);
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(255, 68, 68, 0.3);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .btn-secondary {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
        }
        
        .btn-secondary:hover {
            background: var(--border-color);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .stat-value.critical { color: var(--accent-red); }
        .stat-value.high { color: var(--accent-yellow); }
        .stat-value.medium { color: var(--accent-cyan); }
        .stat-value.low { color: var(--accent-green); }
        
        .stat-label {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        .vuln-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .vuln-item {
            background: var(--bg-primary);
            border-left: 4px solid var(--border-color);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            transition: all 0.2s;
        }
        
        .vuln-item:hover {
            transform: translateX(5px);
        }
        
        .vuln-item.critical { border-left-color: var(--accent-red); }
        .vuln-item.high { border-left-color: var(--accent-yellow); }
        .vuln-item.medium { border-left-color: var(--accent-cyan); }
        .vuln-item.low { border-left-color: var(--accent-green); }
        
        .vuln-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .vuln-type {
            font-weight: 600;
            font-size: 1rem;
        }
        
        .vuln-severity {
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .vuln-severity.critical { background: var(--accent-red); color: white; }
        .vuln-severity.high { background: var(--accent-yellow); color: black; }
        .vuln-severity.medium { background: var(--accent-cyan); color: black; }
        .vuln-severity.low { background: var(--accent-green); color: white; }
        
        .vuln-url {
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-family: monospace;
            word-break: break-all;
        }
        
        .log-console {
            background: #000;
            border-radius: 8px;
            padding: 15px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .log-entry {
            margin-bottom: 5px;
            line-height: 1.5;
        }
        
        .log-time { color: #666; }
        .log-info { color: var(--accent-cyan); }
        .log-success { color: var(--accent-green); }
        .log-error { color: var(--accent-red); }
        .log-warning { color: var(--accent-yellow); }
        
        .ai-panel {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        .ai-chat {
            grid-column: span 2;
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .chat-message {
            margin-bottom: 15px;
            padding: 12px 15px;
            border-radius: 8px;
            max-width: 80%;
        }
        
        .chat-message.user {
            background: var(--accent-cyan);
            color: #000;
            margin-left: auto;
        }
        
        .chat-message.ai {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
        }
        
        .hidden { display: none !important; }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-primary); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-cyan); }
        
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid var(--border-color);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .progress-bar {
            background: var(--bg-primary);
            border-radius: 10px;
            height: 8px;
            overflow: hidden;
            margin-top: 10px;
        }
        
        .progress-fill {
            background: linear-gradient(90deg, var(--accent-red), var(--accent-cyan));
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🔥 PHANTOM STRIKE</h1>
            <div class="tagline">AI-Powered Offensive Security Platform</div>
        </div>
        <div class="status-indicator">
            <div class="status-dot"></div>
            <span>Engine Online</span>
        </div>
    </div>
    
    <div class="container">
        <aside class="sidebar">
            <div class="nav-section">
                <h3>Operations</h3>
                <div class="nav-item active" onclick="showSection('scan')">
                    <span class="icon">🎯</span> New Scan
                </div>
                <div class="nav-item" onclick="showSection('results')">
                    <span class="icon">📊</span> Results
                </div>
                <div class="nav-item" onclick="showSection('ai')">
                    <span class="icon">🧠</span> AI Assistant
                </div>
            </div>
            
            <div class="nav-section">
                <h3>Tools</h3>
                <div class="nav-item" onclick="showSection('payloads')">
                    <span class="icon">💣</span> Payloads
                </div>
                <div class="nav-item" onclick="showSection('c2')">
                    <span class="icon">📡</span> C2 Console
                </div>
                <div class="nav-item" onclick="showSection('reports')">
                    <span class="icon">📄</span> Reports
                </div>
            </div>
            
            <div class="nav-section">
                <h3>System</h3>
                <div class="nav-item" onclick="showSection('config')">
                    <span class="icon">⚙️</span> Configuration
                </div>
                <div class="nav-item" onclick="showSection('logs')">
                    <span class="icon">📋</span> Logs
                </div>
            </div>
        </aside>
        
        <main class="main-content">
            <!-- Scan Section -->
            <section id="scan-section">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value critical" id="stat-critical">0</div>
                        <div class="stat-label">Critical Vulns</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value high" id="stat-high">0</div>
                        <div class="stat-label">High Risk</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value medium" id="stat-medium">0</div>
                        <div class="stat-label">Medium Risk</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value low" id="stat-low">0</div>
                        <div class="stat-label">Low Risk</div>
                    </div>
                </div>
                
                <div class="panel">
                    <div class="panel-header">
                        <h2>🎯 Launch New Scan</h2>
                    </div>
                    <div class="panel-body">
                        <form class="scan-form" onsubmit="startScan(event)">
                            <div class="form-group">
                                <label>Target URL / Domain / IP</label>
                                <input type="text" id="scan-target" placeholder="example.com or https://target.com" required>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                <div class="form-group">
                                    <label>Scan Type</label>
                                    <select id="scan-type">
                                        <option value="full">Full Kill Chain</option>
                                        <option value="recon">Reconnaissance Only</option>
                                        <option value="web">Web Vulnerabilities</option>
                                        <option value="cloud">Cloud Security</option>
                                        <option value="network">Network Scan</option>
                                    </select>
                                </div>
                                
                                <div class="form-group">
                                    <label>Profile</label>
                                    <select id="scan-profile">
                                        <option value="normal">Normal (Balanced)</option>
                                        <option value="stealth">Stealth (Slow/Evasive)</option>
                                        <option value="aggressive">Aggressive (Fast/Noisy)</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div style="display: flex; gap: 15px; align-items: center;">
                                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                    <input type="checkbox" id="auto-exploit" style="width: auto;">
                                    <span>Enable Auto-Exploitation</span>
                                </label>
                                
                                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                    <input type="checkbox" id="use-ai" checked style="width: auto;">
                                    <span>Use AI Analysis</span>
                                </label>
                            </div>
                            
                            <button type="submit" class="btn">
                                <span>🚀</span> Start Attack
                            </button>
                            
                            <div class="progress-bar hidden" id="scan-progress">
                                <div class="progress-fill" style="width: 0%;"></div>
                            </div>
                        </form>
                    </div>
                </div>
                
                <div class="panel">
                    <div class="panel-header">
                        <h2>🚨 Live Vulnerabilities</h2>
                        <span id="vuln-count">0 found</span>
                    </div>
                    <div class="panel-body">
                        <div class="vuln-list" id="vuln-list">
                            <p style="color: var(--text-secondary); text-align: center; padding: 40px;">
                                No vulnerabilities found yet. Start a scan to discover issues.
                            </p>
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- Results Section -->
            <section id="results-section" class="hidden">
                <div class="panel">
                    <div class="panel-header">
                        <h2>📊 Scan Results History</h2>
                    </div>
                    <div class="panel-body" id="results-list">
                        <p style="color: var(--text-secondary);">No completed scans yet.</p>
                    </div>
                </div>
            </section>
            
            <!-- AI Section -->
            <section id="ai-section" class="hidden">
                <div class="panel">
                    <div class="panel-header">
                        <h2>🧠 AI Attack Assistant</h2>
                        <span id="ai-status">Ready</span>
                    </div>
                    <div class="panel-body">
                        <div class="ai-chat" id="ai-chat">
                            <div class="chat-message ai">
                                <strong>Phantom AI:</strong> I'm ready to help with attack planning, vulnerability analysis, and payload generation. What would you like to know?
                            </div>
                        </div>
                        
                        <div style="display: flex; gap: 10px; margin-top: 15px;">
                            <input type="text" id="ai-input" placeholder="Ask me about vulnerabilities, attack techniques, or payload generation..." 
                                style="flex: 1; background: var(--bg-primary); border: 1px solid var(--border-color); color: var(--text-primary); padding: 12px 15px; border-radius: 8px;">
                            <button class="btn" onclick="sendAIQuery()">Send</button>
                        </div>
                        
                        <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                            <button class="btn btn-secondary" onclick="quickAI('Generate polymorphic XSS payload')">XSS Payload</button>
                            <button class="btn btn-secondary" onclick="quickAI('Generate SQLi bypass for WAF')">SQLi Bypass</button>
                            <button class="btn btn-secondary" onclick="quickAI('Analyze JWT vulnerabilities')">JWT Analysis</button>
                            <button class="btn btn-secondary" onclick="quickAI('Plan lateral movement strategy')">Lateral Move</button>
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- Payloads Section -->
            <section id="payloads-section" class="hidden">
                <div class="panel">
                    <div class="panel-header">
                        <h2>💣 Payload Generator</h2>
                    </div>
                    <div class="panel-body">
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                            <button class="btn" onclick="generatePayloads('xss')">Generate XSS</button>
                            <button class="btn" onclick="generatePayloads('sqli')">Generate SQLi</button>
                            <button class="btn" onclick="generatePayloads('reverse_shell')">Reverse Shells</button>
                        </div>
                        <div id="payload-output" style="margin-top: 20px; background: var(--bg-primary); padding: 20px; border-radius: 8px; font-family: monospace; white-space: pre-wrap;">
                            Select a payload type to generate...
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- C2 Section -->
            <section id="c2-section" class="hidden">
                <div class="panel">
                    <div class="panel-header">
                        <h2>📡 Command & Control</h2>
                        <span id="c2-status">No active agents</span>
                    </div>
                    <div class="panel-body">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                            <div>
                                <h3 style="color: var(--accent-cyan); margin-bottom: 15px;">Active Agents</h3>
                                <div id="agent-list" style="background: var(--bg-primary); padding: 15px; border-radius: 8px; min-height: 200px;">
                                    <p style="color: var(--text-secondary);">No agents connected</p>
                                </div>
                            </div>
                            <div>
                                <h3 style="color: var(--accent-cyan); margin-bottom: 15px;">Generate Agent</h3>
                                <div class="form-group">
                                    <label>C2 Host</label>
                                    <input type="text" id="c2-host" placeholder="your-server.com" value="localhost">
                                </div>
                                <div class="form-group">
                                    <label>C2 Port</label>
                                    <input type="number" id="c2-port" placeholder="8443" value="8443">
                                </div>
                                <button class="btn" onclick="generateAgent()">Generate Payload</button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- Logs Section -->
            <section id="logs-section" class="hidden">
                <div class="panel">
                    <div class="panel-header">
                        <h2>📋 System Logs</h2>
                        <button class="btn btn-secondary" onclick="clearLogs()">Clear</button>
                    </div>
                    <div class="panel-body">
                        <div class="log-console" id="log-console">
                            <div class="log-entry">
                                <span class="log-time">[00:00:00]</span>
                                <span class="log-info">PhantomStrike Dashboard initialized</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    </div>
    
    <script>
        let ws = null;
        let scanResults = [];
        
        // WebSocket connection
        function connectWebSocket() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);
            
            ws.onopen = () => {
                log('Connected to PhantomStrike engine', 'success');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = () => {
                log('Disconnected from engine. Retrying...', 'warning');
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = (error) => {
                log('WebSocket error', 'error');
            };
        }
        
        function handleWebSocketMessage(data) {
            switch(data.type) {
                case 'vulnerability':
                    addVulnerability(data.payload);
                    break;
                case 'progress':
                    updateProgress(data.percent);
                    break;
                case 'log':
                    log(data.message, data.level);
                    break;
                case 'scan_complete':
                    onScanComplete(data.results);
                    break;
                case 'ai_response':
                    addAIResponse(data.response);
                    break;
            }
        }
        
        function showSection(section) {
            document.querySelectorAll('main > section').forEach(s => s.classList.add('hidden'));
            document.getElementById(section + '-section').classList.remove('hidden');
            
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            event.target.closest('.nav-item').classList.add('active');
        }
        
        async function startScan(e) {
            e.preventDefault();
            
            const target = document.getElementById('scan-target').value;
            const scanType = document.getElementById('scan-type').value;
            const profile = document.getElementById('scan-profile').value;
            const autoExploit = document.getElementById('auto-exploit').checked;
            const useAI = document.getElementById('use-ai').checked;
            
            log(`Starting ${scanType} scan on ${target}...`, 'info');
            
            document.getElementById('scan-progress').classList.remove('hidden');
            document.getElementById('vuln-list').innerHTML = '';
            
            // Reset stats
            updateStats({critical: 0, high: 0, medium: 0, low: 0});
            
            try {
                const response = await fetch('/api/scan/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target,
                        scan_type: scanType,
                        profile,
                        auto_exploit: autoExploit,
                        use_ai: useAI
                    })
                });
                
                const result = await response.json();
                log(`Scan initiated: ${result.scan_id}`, 'success');
                
            } catch (error) {
                log(`Failed to start scan: ${error.message}`, 'error');
            }
        }
        
        function addVulnerability(vuln) {
            const list = document.getElementById('vuln-list');
            const severity = vuln.severity || 'medium';
            
            const item = document.createElement('div');
            item.className = `vuln-item ${severity}`;
            item.innerHTML = `
                <div class="vuln-header">
                    <span class="vuln-type">${vuln.type.toUpperCase()}</span>
                    <span class="vuln-severity ${severity}">${severity}</span>
                </div>
                <div class="vuln-url">${vuln.url || vuln.bucket || vuln.account || 'N/A'}</div>
                ${vuln.payload ? `<div style="margin-top: 8px; font-size: 0.85rem; color: var(--text-secondary);">Payload: <code>${vuln.payload}</code></div>` : ''}
                ${vuln.evidence ? `<div style="margin-top: 5px; font-size: 0.8rem; color: var(--accent-cyan);">${vuln.evidence}</div>` : ''}
            `;
            
            list.insertBefore(item, list.firstChild);
            
            // Update stats
            const statId = `stat-${severity}`;
            const current = parseInt(document.getElementById(statId).textContent);
            document.getElementById(statId).textContent = current + 1;
            
            document.getElementById('vuln-count').textContent = 
                parseInt(document.getElementById('vuln-count').textContent.split(' ')[0]) + 1 + ' found';
            
            log(`Found ${severity} vulnerability: ${vuln.type}`, severity === 'critical' ? 'error' : 'warning');
        }
        
        function updateProgress(percent) {
            document.querySelector('.progress-fill').style.width = percent + '%';
        }
        
        function updateStats(stats) {
            document.getElementById('stat-critical').textContent = stats.critical;
            document.getElementById('stat-high').textContent = stats.high;
            document.getElementById('stat-medium').textContent = stats.medium;
            document.getElementById('stat-low').textContent = stats.low;
        }
        
        function onScanComplete(results) {
            document.getElementById('scan-progress').classList.add('hidden');
            log('Scan completed!', 'success');
            scanResults.push(results);
            updateResultsList();
        }
        
        function updateResultsList() {
            const container = document.getElementById('results-list');
            container.innerHTML = scanResults.map((r, i) => `
                <div style="background: var(--bg-primary); padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                    <strong>${r.target}</strong> - ${r.timestamp}
                    <div style="margin-top: 10px; display: flex; gap: 15px;">
                        <span style="color: var(--accent-red);">🔴 ${r.critical || 0}</span>
                        <span style="color: var(--accent-yellow);">🟠 ${r.high || 0}</span>
                        <span style="color: var(--accent-cyan);">🟡 ${r.medium || 0}</span>
                    </div>
                </div>
            `).join('');
        }
        
        async function sendAIQuery() {
            const input = document.getElementById('ai-input');
            const query = input.value.trim();
            if (!query) return;
            
            // Add user message
            const chat = document.getElementById('ai-chat');
            chat.innerHTML += `<div class="chat-message user">${query}</div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;
            
            document.getElementById('ai-status').innerHTML = '<div class="loading-spinner"></div> Thinking...';
            
            try {
                const response = await fetch('/api/ai/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: query })
                });
                
                const result = await response.json();
                
                if (result.error) {
                    addAIResponse('Error: ' + result.error);
                } else if (result.content) {
                    addAIResponse(result.content);
                } else {
                    addAIResponse('Error: AI service unavailable. Set API keys to enable AI features.');
                }
                
            } catch (error) {
                addAIResponse('Error: AI service unavailable. Set API keys to enable AI features.');
            }
            
            document.getElementById('ai-status').textContent = 'Ready';
        }
        
        function quickAI(query) {
            document.getElementById('ai-input').value = query;
            sendAIQuery();
        }
        
        function addAIResponse(response) {
            const chat = document.getElementById('ai-chat');
            chat.innerHTML += `<div class="chat-message ai"><strong>Phantom AI:</strong><br><pre style="white-space: pre-wrap; font-family: inherit;">${response}</pre></div>`;
            chat.scrollTop = chat.scrollHeight;
        }
        
        async function generatePayloads(type) {
            const output = document.getElementById('payload-output');
            output.textContent = 'Generating payloads...';
            
            try {
                const response = await fetch('/api/payloads/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type, count: 10 })
                });
                
                const result = await response.json();
                output.textContent = result.payloads.map((p, i) => 
                    `[${i+1}] ${p.language || p.encoding || 'raw'}\\n${p.payload}\\n`
                ).join('\\n---\\n');
                
            } catch (error) {
                output.textContent = 'Error generating payloads: ' + error.message;
            }
        }
        
        function log(message, level = 'info') {
            const console = document.getElementById('log-console');
            const time = new Date().toLocaleTimeString();
            console.innerHTML += `<div class="log-entry"><span class="log-time">[${time}]</span> <span class="log-${level}">${message}</span></div>`;
            console.scrollTop = console.scrollHeight;
        }
        
        function clearLogs() {
            document.getElementById('log-console').innerHTML = '';
        }
        
        // Initialize
        connectWebSocket();
        log('PhantomStrike Dashboard loaded', 'success');
    </script>
</body>
</html>
'''


class DashboardManager:
    """Manages the web dashboard state and WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.scan_progress: Dict[str, Dict] = {}
        self.vulnerabilities: List[Dict] = []
        self.logs: List[Dict] = []
        
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            
    async def broadcast(self, message: Dict):
        """Send message to all connected clients."""
        disconnected = []
        for client_id, ws in self.active_connections.items():
            try:
                await ws.send_json(message)
            except:
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for cid in disconnected:
            self.disconnect(cid)
            
    async def send_vulnerability(self, vuln: Dict):
        """Broadcast vulnerability to all clients."""
        self.vulnerabilities.append(vuln)
        await self.broadcast({
            "type": "vulnerability",
            "payload": vuln
        })
        
    async def send_progress(self, percent: int, message: str = ""):
        """Send scan progress update."""
        await self.broadcast({
            "type": "progress",
            "percent": percent,
            "message": message
        })
        
    async def send_log(self, message: str, level: str = "info"):
        """Send log message to dashboard."""
        self.logs.append({
            "time": datetime.now().isoformat(),
            "message": message,
            "level": level
        })
        await self.broadcast({
            "type": "log",
            "message": message,
            "level": level
        })


# Global dashboard manager instance
dashboard_manager = DashboardManager()


def get_dashboard_html() -> str:
    """Return the dashboard HTML."""
    return DASHBOARD_HTML
