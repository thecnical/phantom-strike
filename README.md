<p align="center">
  <img src="https://img.shields.io/badge/🔥_PHANTOM_STRIKE-v2.0-FF4444?style=for-the-badge&logo=ghost&logoColor=white" alt="PhantomStrike" width="420">
</p>

<h1 align="center">PhantomStrike — AI-Powered Offensive Security Framework</h1>

<p align="center">
  <b>Open-source penetration testing framework with autonomous AI attack planning,<br>
  real vulnerability detection, and a full-stack web dashboard.</b>
</p>

<p align="center">
  <a href="https://github.com/thecnical/phantom-strike/stargazers">
    <img src="https://img.shields.io/github/stars/thecnical/phantom-strike?style=for-the-badge&color=FFD700&logo=github" alt="Stars">
  </a>
  <a href="https://github.com/thecnical/phantom-strike/network/members">
    <img src="https://img.shields.io/github/forks/thecnical/phantom-strike?style=for-the-badge&color=00CED1&logo=github" alt="Forks">
  </a>
  <a href="https://github.com/thecnical/phantom-strike/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-22D3EE?style=for-the-badge" alt="MIT License">
  </a>
  <a href="https://github.com/thecnical/phantom-strike/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/thecnical/phantom-strike/ci.yml?style=for-the-badge&label=CI" alt="CI">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Playwright-✓-2EAD33?style=flat-square&logo=microsoft-edge" alt="Playwright">
  <img src="https://img.shields.io/badge/Groq_AI-500+_tok/s-F55000?style=flat-square" alt="Groq">
  <img src="https://img.shields.io/badge/Async-aiohttp-blue?style=flat-square" alt="Async">
  <img src="https://img.shields.io/badge/Tests-28_passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/Live_Backend-Render-46E3B7?style=flat-square&logo=render" alt="Render">
</p>

---

## What is PhantomStrike?

**PhantomStrike** is a fully open-source, AI-powered penetration testing framework written in Python. It automates the complete offensive security lifecycle — from OSINT and network reconnaissance through vulnerability discovery, exploitation, post-exploitation, and professional report generation.

Every module makes real network requests, performs real vulnerability tests, and produces real findings. No simulations, no stubs.

**Key features:**
- **Zero API key setup** — AI works out of the box via deployed Render backend
- Multi-provider AI engine (Groq → OpenRouter → Cerebras) with automatic failover
- Blind time-based SQL injection detection
- Real S3/Azure/GCP bucket enumeration
- Playwright browser engine for JS-rendered XSS verification
- Full-stack web dashboard with WebSocket live updates
- 28 passing tests, zero stubs in critical paths

---

## Feature Comparison

| Capability | Metasploit | Burp Suite Pro | Nuclei | **PhantomStrike** |
|:-----------|:----------:|:--------------:|:------:|:-----------------:|
| AI Attack Planning | ❌ | ❌ | ❌ | ✅ Groq + OpenRouter |
| Zero Config AI | ❌ | ❌ | ❌ | ✅ Backend pre-configured |
| Blind SQLi (time-based) | ❌ | ✅ | ❌ | ✅ Real detection |
| Cloud Storage Audit | ❌ | ❌ | ❌ | ✅ S3/Azure/GCP |
| Browser XSS Verification | ❌ | ✅ | ❌ | ✅ Playwright |
| Real-Time Dashboard | ❌ | ✅ $449/yr | ❌ | ✅ WebSocket |
| C2 Framework | ✅ | ❌ | ❌ | ✅ Agent management |
| MITRE ATT&CK Mapping | ❌ | ❌ | ❌ | ✅ Auto-mapped |
| Cost | Free | **$449/yr** | Free | **100% Free** |

---

## Modules (11 total)

| Module | Category | What it does |
|:-------|:---------|:-------------|
| `phantom-osint` | Reconnaissance | Subdomain enumeration (DNS brute + crt.sh), email harvest, tech detection |
| `phantom-network` | Reconnaissance | Async port scan (65535 ports), banner grabbing, OS fingerprinting |
| `phantom-web` | Vulnerability | SQLi (error/blind/union), XSS (reflected/stored), XXE, CSRF, LFI, SSRF, IDOR, JWT |
| `phantom-cloud` | Vulnerability | S3/Azure Blob/GCP bucket enumeration, metadata SSRF, IAM misconfiguration |
| `phantom-identity` | Vulnerability | JWT none-algorithm attack, weak secret brute force, auth bypass |
| `phantom-cred` | Credential | Password spraying, brute force, hash cracking (MD5/SHA1/SHA256/SHA512) |
| `phantom-stealth` | Evasion | Polymorphic XSS/SQLi payloads, WAF bypass, reverse shells (6 languages) |
| `phantom-exploit` | Exploitation | Union-based SQLi extraction, LFI file read, SSRF internal access, RCE |
| `phantom-c2` | C2 | Agent registration, command queuing, Python/Bash agent generation |
| `phantom-post` | Post-Exploitation | Privesc checks, lateral movement discovery, persistence techniques |
| `phantom-report` | Reporting | HTML + JSON + TXT reports with MITRE ATT&CK mapping |

---

## Installation

### One-command install (recommended — works on all Linux distros)

```bash
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike
bash install.sh
```

This handles everything automatically:
- Detects OS (Kali, Ubuntu, Debian, Arch, Fedora, macOS)
- Installs Python 3.10+ if missing
- Creates virtual environment at `~/.phantom-strike/venv`
- Installs all dependencies
- Installs `phantom` command to `/usr/local/bin` (works from anywhere, survives restarts)
- Installs Playwright Chromium browser

After install, run from **any directory**:
```bash
phantom          # interactive CLI
phantom serve    # web dashboard at http://localhost:10000
```

### Update existing installation

```bash
cd /path/to/phantom-strike
git pull
bash install.sh --update
```

### Manual install (if you prefer)

```bash
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike                          # MUST be inside this folder

sudo apt install -y python3-venv python3-pip   # Kali/Debian only
python3 -m venv ~/.phantom-strike/venv
source ~/.phantom-strike/venv/bin/activate

pip install -e ".[api,dev]"
playwright install chromium                # optional

phantom
```

> **Kali Linux note:** Never run `pip install` without activating the venv first — Kali uses externally-managed Python (PEP 668). Always `source ~/.phantom-strike/venv/bin/activate` first, or just use `bash install.sh`.

---

## Usage

### Interactive CLI

```bash
phantom
```

```
phantom> scan example.com              # vulnerability scan
phantom> attack example.com           # full 7-phase kill chain
phantom> recon example.com            # OSINT + network recon only
phantom> ai ask "explain XSS"         # ask AI anything (with memory)
phantom> ai chat                      # persistent AI chat (type 'bye' to exit)
phantom> ai plan example.com          # AI generates plan + auto-executes it
phantom> ai status                    # show AI provider status
phantom> ai memory                    # show conversation memory
phantom> stealth xss 20               # generate 20 XSS payloads
phantom> stealth sqli 10              # generate 10 SQLi payloads
phantom> stealth reverse_shell 10.0.0.1 4444
phantom> c2 generate 10.0.0.1 4444    # generate C2 agent
phantom> c2 agents                    # list active agents
phantom> report example.com           # generate pentest report
phantom> modules                      # list all 11 modules
phantom> status                       # engine status
phantom> exit                         # exit (also: quit, q, Ctrl+C)
```

### Web Dashboard

```bash
phantom serve
# Open: http://localhost:10000
```

Dashboard features:
- Launch scans with real-time vulnerability feed
- AI chat assistant (ask attack questions)
- Payload generator (XSS, SQLi, reverse shells)
- C2 agent management
- Report generation
- System logs

---

## AI Integration

PhantomStrike AI works **without any local API keys** — it routes through a pre-configured backend deployed on Render.

```
User CLI / Dashboard
      ↓
Render Backend (phantom-strike.onrender.com)
      ↓ has all keys pre-configured
  Priority 1: Groq (Llama 3.3 70B)    — 500+ tokens/sec
  Priority 2: OpenRouter               — 100+ models
  Priority 3: Cerebras (Llama 3.3 70B) — fast inference
  Fallback:   Rule-based templates     — always works
```

**To use your own API keys instead** (optional):
```bash
# Add to ~/.phantom-strike/.env
PHANTOM_BACKEND_ENABLED=false
GROQ_API_KEY=gsk_xxxxxxxxxxxx
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
CEREBRAS_API_KEY=csk_xxxxxxxxxxxx
```

Get free keys:
- Groq: https://console.groq.com (14K req/day free)
- OpenRouter: https://openrouter.ai (free tier)
- Cerebras: https://cloud.cerebras.ai (1M tokens/day free)

---

## Kill Chain (7 phases)

```bash
phantom> attack target.com
```

```
Phase 1: OSINT + Network Reconnaissance
Phase 2: Web Vulnerability Discovery
Phase 3: Cloud Security Assessment
Phase 4: AI Attack Path Planning
Phase 5: Polymorphic Payload Generation
Phase 6: Exploitation (requires auto_exploit=true)
Phase 7: Post-Exploitation + Report Generation
```

---

## API Reference

Start server: `phantom serve`

| Endpoint | Method | Description |
|:---------|:------:|:------------|
| `/` | GET | Web Dashboard UI |
| `/health` | GET | Health check |
| `/ws` | WS | WebSocket live feed |
| `/api/scan/start` | POST | Start background scan |
| `/api/scan/quick` | POST | Synchronous scan |
| `/api/ai/query` | POST | AI query |
| `/api/ai/status` | GET | AI provider status |
| `/api/payloads/generate` | POST | Generate payloads |
| `/api/modules` | GET | List all modules |
| `/api/c2/agents` | GET | List C2 agents |
| `/api/c2/agents/{id}/command` | POST | Send command to agent |
| `/api/attack/start` | POST | Start attack mode |
| `/api/results` | GET | All scan results |
| `/docs` | GET | Swagger UI |

**Example:**
```bash
curl -X POST https://phantom-strike.onrender.com/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "explain SQL injection in 3 lines"}'
```

---

## Live Backend

The backend is deployed at: **https://phantom-strike.onrender.com**

```bash
# Health check
curl https://phantom-strike.onrender.com/health

# AI query (no API key needed)
curl -X POST https://phantom-strike.onrender.com/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "what is XSS?"}'

# Web dashboard
open https://phantom-strike.onrender.com
```

> **Note:** Render free tier sleeps after 15 minutes of inactivity. First request may take 30-60 seconds to wake up.

---

## Deploy Your Own Backend

```bash
# 1. Fork this repo
# 2. Connect to Render: https://render.com/deploy?repo=https://github.com/thecnical/phantom-strike
# 3. Set environment variables in Render Dashboard:
#    PHANTOM_BACKEND_ENABLED = false
#    GROQ_API_KEY = your_key
#    OPENROUTER_API_KEY = your_key
#    CEREBRAS_API_KEY = your_key
```

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/thecnical/phantom-strike)

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  CLI (Rich TUI)  │  Web Dashboard  │  REST API (FastAPI)  │
├──────────────────────────────────────────────────────────┤
│               EnhancedPhantomEngine                       │
│    EventBus │ ModuleLoader │ AI Engine │ TaskQueue         │
├──────────────────────────────────────────────────────────┤
│  OSINT │ Network │ Web │ Cloud │ Identity │ Cred           │
│  Stealth │ Exploit │ C2 │ Post │ Report                    │
├──────────────────────────────────────────────────────────┤
│  AI: Groq → OpenRouter → Cerebras → Rule-based Fallback   │
├──────────────────────────────────────────────────────────┤
│  SQLite (aiosqlite) │ Playwright Browser │ aiohttp         │
└──────────────────────────────────────────────────────────┘
```

---

## Testing

```bash
# Run all 28 tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=phantom --cov-report=html
```

28 tests cover: config, EventBus, module loader, stealth payloads, hash cracking, post-exploitation, C2, database CRUD, attack modes, exploit engine, AI backend config, Playwright config.

---

## Legal Disclaimer

PhantomStrike is designed exclusively for **authorized penetration testing**, security research, and educational purposes.

- Only scan systems you own or have **written authorization** to test
- Follow responsible disclosure for any vulnerabilities found
- Comply with all applicable laws

The developers assume no liability for misuse.

---

## License

MIT License — see [LICENSE](LICENSE)

Copyright (c) 2024 Chandan Pandey

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome.

---

<p align="center">
  <b>⭐ Star this repo if it helped you</b><br>
  <a href="https://github.com/thecnical/phantom-strike/stargazers">Star</a> •
  <a href="https://github.com/thecnical/phantom-strike/fork">Fork</a> •
  <a href="https://github.com/thecnical/phantom-strike/issues">Issues</a>
</p>

<p align="center">
  <i>Built by Chandan Pandey — chandanabhay4456@gmail.com</i>
</p>
