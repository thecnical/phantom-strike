<p align="center">
  <img src="https://img.shields.io/badge/🔥_PHANTOM_STRIKE-v2.0-FF4444?style=for-the-badge&logo=ghost&logoColor=white" alt="PhantomStrike" width="420">
</p>

<h1 align="center">PhantomStrike — AI-Powered Offensive Security Framework</h1>

<p align="center">
  <b>The open-source penetration testing framework with autonomous AI attack planning,<br>
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
</p>

---

## What is PhantomStrike?

**PhantomStrike** is a fully open-source, AI-powered penetration testing framework written in Python. It automates the complete offensive security lifecycle — from OSINT and network reconnaissance through vulnerability discovery, exploitation, post-exploitation, and professional report generation.

Unlike tools that simulate results, every module in PhantomStrike makes real network requests, performs real vulnerability tests, and produces real findings.

**Key differentiators:**
- Multi-provider AI engine (Groq, OpenRouter, Gemini, Cerebras) with automatic failover
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
| Blind SQLi (time-based) | ❌ | ✅ | ❌ | ✅ Real detection |
| Cloud Storage Audit | ❌ | ❌ | ❌ | ✅ S3/Azure/GCP |
| Browser XSS Verification | ❌ | ✅ | ❌ | ✅ Playwright |
| Real-Time Dashboard | ❌ | ✅ $449/yr | ❌ | ✅ WebSocket |
| C2 Framework | ✅ | ❌ | ❌ | ✅ Agent management |
| MITRE ATT&CK Mapping | ❌ | ❌ | ❌ | ✅ Auto-mapped |
| Cost | Free | **$449/yr** | Free | **100% Free** |

---

## Modules

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

## Quick Start

### Install

```bash
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike
pip install -e ".[api,dev]"
playwright install chromium   # optional — for browser-based XSS
```

### Configure AI (optional but recommended)

```bash
# Get free key at https://console.groq.com
export GROQ_API_KEY=gsk_xxxxxxxxxxxx

# Fallback providers (all free tiers)
export OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
export GEMINI_API_KEY=AIxxxxxxxxxxxx
```

### Run CLI

```bash
phantom
phantom> scan example.com
phantom> attack example.com
phantom> ai ask "explain JWT none algorithm attack"
phantom> stealth xss 20
phantom> report example.com
```

### Run Web Dashboard

```bash
phantom serve
# Open http://localhost:10000
```

---

## Attack Modes

```bash
# Full autonomous kill chain (7 phases)
phantom> attack target.com

# Stealth — slow, evasive, jitter delays
phantom> module phantom-web target.com {"mode":"stealth"}

# Aggressive — max threads, parallel
phantom> scan target.com
```

**Kill chain phases:**
1. OSINT + Network Reconnaissance
2. Web Vulnerability Discovery
3. Cloud Security Assessment
4. AI Attack Path Planning
5. Payload Generation (polymorphic)
6. Exploitation (if enabled)
7. Post-Exploitation + Report

---

## AI Integration

PhantomStrike uses a multi-provider AI engine with automatic failover:

```
Priority 1: Groq (Llama 3.3 70B)     — 500+ tokens/sec, 14K req/day free
Priority 2: OpenRouter (Gemini 2.5)   — 100+ models, free tier
Priority 3: Google Gemini Flash        — 60 req/min free
Priority 4: Cerebras (Llama 3.3 70B)  — fast inference, free tier
Fallback:   Rule-based templates       — always works, no API key needed
```

AI capabilities:
- Attack chain planning from recon data
- Vulnerability analysis with MITRE ATT&CK mapping
- Polymorphic payload generation (WAF-aware)
- Evasion technique suggestions

---

## API Reference

Start the server: `phantom serve`

| Endpoint | Method | Description |
|:---------|:------:|:------------|
| `/` | GET | Web Dashboard |
| `/health` | GET | Health check |
| `/ws` | WS | WebSocket live feed |
| `/api/scan/start` | POST | Start background scan |
| `/api/scan/quick` | POST | Synchronous scan |
| `/api/ai/query` | POST | AI query |
| `/api/ai/status` | GET | AI provider status |
| `/api/payloads/generate` | POST | Generate payloads |
| `/api/modules` | GET | List modules |
| `/api/c2/agents` | GET | C2 agents |
| `/api/attack/start` | POST | Start attack mode |
| `/docs` | GET | Swagger UI |

**Example:**
```bash
curl -X POST http://localhost:10000/api/scan/start \
  -H "Content-Type: application/json" \
  -d '{"target": "scanme.nmap.org", "scan_type": "full"}'
```

---

## Testing

```bash
# Run all 28 tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=phantom --cov-report=html
```

All 28 tests pass. Test coverage includes:
- Config loading and AI provider setup
- EventBus pub/sub and stats
- Module loader (all 11 modules)
- Stealth payload generation (XSS, SQLi, reverse shells)
- Credential hash cracking
- Post-exploitation enumeration
- C2 agent registration and payload generation
- Database CRUD (scans, vulns, creds)
- Attack mode configuration (stealth, aggressive, recon)
- Exploit engine URL injection correctness
- Backend opt-in default
- Playwright config presence

---

## Deploy to Render

```yaml
# render.yaml
services:
  - type: web
    name: phantom-strike
    runtime: docker
    plan: standard
    envVars:
      - key: GROQ_API_KEY
        sync: false
      - key: OPENROUTER_API_KEY
        sync: false
```

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/thecnical/phantom-strike)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  CLI (Rich TUI)  │  Web Dashboard  │  REST API (FastAPI) │
├─────────────────────────────────────────────────────────┤
│              EnhancedPhantomEngine                       │
│   EventBus │ ModuleLoader │ AI Engine │ TaskQueue        │
├─────────────────────────────────────────────────────────┤
│  OSINT │ Network │ Web │ Cloud │ Identity │ Cred         │
│  Stealth │ Exploit │ C2 │ Post │ Report                  │
├─────────────────────────────────────────────────────────┤
│  AI: Groq → OpenRouter → Gemini → Cerebras → Fallback   │
├─────────────────────────────────────────────────────────┤
│  SQLite (aiosqlite) │ Playwright Browser │ aiohttp       │
└─────────────────────────────────────────────────────────┘
```

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
