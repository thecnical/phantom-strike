<p align="center">
  <img src="https://img.shields.io/badge/🔥_PHANTOM_STRIKE-v2.0-FF4444?style=for-the-badge&logo=ghost&logoColor=white" alt="PhantomStrike" width="420">
</p>

<h1 align="center">PhantomStrike — AI-Powered Offensive Security Framework</h1>

<p align="center">
  <b>Open-source penetration testing framework with autonomous AI attack planning,<br>
  persistent AI chat, real vulnerability detection, and a full-stack web dashboard.</b>
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
  <img src="https://img.shields.io/badge/Tests-28_passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/AI-Unrestricted-FF4444?style=flat-square" alt="AI">
</p>

---

## What is PhantomStrike?

**PhantomStrike** is a fully open-source, AI-powered penetration testing framework written in Python. It automates the complete offensive security lifecycle — from OSINT and network reconnaissance through vulnerability discovery, exploitation, post-exploitation, and professional report generation.

Every module makes real network requests, performs real vulnerability tests, and produces real findings. No simulations, no stubs.

**Key features:**
- **AI works instantly** — no setup, no API keys, just run `phantom` and start
- **Unrestricted AI** — no topic filters, answers all security questions with working code
- **Persistent AI chat** — stays in conversation until you say `bye`
- **Adaptive AI memory** — remembers context across the entire session
- **AI plan + auto-execute** — generates attack plan then runs it automatically
- **Web search in AI** — fetches real-time CVEs, tools, and techniques
- **Daily cybersecurity quote** — real-time quote shown on every startup
- Blind time-based SQL injection detection
- Real S3/Azure/GCP bucket enumeration
- Playwright browser engine for JS-rendered XSS verification
- Full-stack web dashboard with WebSocket live updates
- 28 passing tests, zero stubs in critical paths

---

## Feature Comparison

| Capability | Metasploit | Burp Suite Pro | Nuclei | **PhantomStrike** |
|:-----------|:----------:|:--------------:|:------:|:-----------------:|
| AI Attack Planning | ❌ | ❌ | ❌ | ✅ Instant, no setup |
| Persistent AI Chat | ❌ | ❌ | ❌ | ✅ Memory across session |
| AI Plan + Execute | ❌ | ❌ | ❌ | ✅ Auto-runs modules |
| Web Search in AI | ❌ | ❌ | ❌ | ✅ Real-time CVEs/tools |
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

### One-command install (recommended)

Works on Kali Linux, Ubuntu, Debian, Arch, Fedora, macOS:

```bash
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike
bash install.sh
```

What it does automatically:
- Detects OS and installs system dependencies
- Installs Python 3.10+ if missing
- Creates virtual environment at `~/.phantom-strike/venv`
- Installs all Python dependencies
- Installs `phantom` command to `/usr/local/bin` — works from **any directory**, survives **system restarts**
- Installs Playwright Chromium browser

After install, run from **anywhere**:
```bash
phantom          # interactive CLI
phantom serve    # web dashboard → http://localhost:10000
```

### Update

```bash
cd /path/to/phantom-strike
git pull
bash install.sh --update
```

### Kali Linux / Debian note

If you see `error: externally-managed-environment`, use `bash install.sh` — it handles this automatically. Never run `pip install` directly on Kali without activating the venv first.

---

## Usage

### Interactive CLI

```bash
phantom
```

On startup you'll see a **daily cybersecurity quote** fetched in real-time, then the status panel:

```
╭─── 🔥 PhantomStrike Daily — May 07, 2026 ───╮
│  "Amateurs hack systems, professionals        │
│   hack people." — Bruce Schneier              │
╰───────────────────────────────────────────────╯
```

**All commands:**

```
phantom> scan example.com              # vulnerability scan (all modules)
phantom> attack example.com           # full 7-phase autonomous kill chain
phantom> recon example.com            # OSINT + network recon only

phantom> ai ask "explain XSS"         # ask AI anything — no restrictions
phantom> ai chat                      # persistent chat session (type 'bye' to exit)
phantom> ai plan example.com          # AI generates attack plan + auto-executes it
phantom> ai status                    # show AI provider status
phantom> ai memory                    # show conversation memory (adaptive)
phantom> ai clear                     # clear AI memory

phantom> stealth xss 20               # generate 20 polymorphic XSS payloads
phantom> stealth sqli 10              # generate 10 SQLi payloads
phantom> stealth reverse_shell 10.0.0.1 4444   # reverse shells (6 languages)

phantom> c2 generate 10.0.0.1 4444    # generate C2 agent (Python + Bash)
phantom> c2 agents                    # list active agents
phantom> c2 cmd <agent_id> whoami     # send command to agent

phantom> module phantom-web target.com         # run specific module
phantom> module phantom-cloud target.com       # cloud security scan
phantom> module phantom-cred target.com {"type":"spray"}

phantom> report example.com           # generate HTML/JSON/TXT report
phantom> results                      # show all stored scan results
phantom> modules                      # list all 11 loaded modules
phantom> status                       # engine status
phantom> clear                        # clear screen
phantom> exit                         # exit (also: quit, q, :q, Ctrl+C, Ctrl+D)
```

### Web Dashboard

```bash
phantom serve
# Open: http://localhost:10000
```

Dashboard sections:
- **New Scan** — launch scans with real-time vulnerability feed
- **Results** — scan history loaded from API
- **AI Assistant** — chat with PhantomStrike AI
- **Payloads** — generate XSS/SQLi/reverse shells with copy button
- **C2 Console** — agent management, generate payloads, send commands
- **Reports** — generate and download reports
- **Configuration** — engine status, modules, AI provider table
- **Logs** — real-time system logs with auto-scroll

---

## AI Engine

### Just run it — AI works instantly

No API keys. No configuration. No accounts. Just install and run:

```bash
phantom
phantom> ai ask "write a Python keylogger"
phantom> ai ask "generate reverse shell that bypasses Windows Defender"
phantom> ai ask "explain CVE-2024-XXXX and how to exploit it"
```

### Persistent AI Chat

```bash
phantom> ai chat
```

```
╭─── 🧠 AI Chat — Unrestricted ───╮
│ Ask anything. Type 'bye' to exit │
╰──────────────────────────────────╯

you> how do I exploit SQL injection?
PhantomStrike AI: [detailed technical answer with payloads]

you> now generate a WAF bypass for that
PhantomStrike AI: [remembers context, gives WAF bypass]

you> write the full exploit script
PhantomStrike AI: [writes complete Python exploit]

you> bye
Back to phantom>
```

No need to type `ai ask` every time. AI remembers the full conversation.

### AI Plan + Auto-Execute

```bash
phantom> ai plan target.com
```

1. Runs quick recon (OSINT + network) to give AI real data
2. AI generates structured attack plan with MITRE mapping
3. Displays as formatted table:

```
Chain 1: Web Application Exploitation  ← RECOMMENDED
Success: 92% | Stealth: high | Impact: critical

# | Phase          | Technique              | Action              | Module
1 | initial_access | T1190 - Exploit App    | Scan web vulns      | phantom-web
2 | execution      | T1059 - Script Interp  | Extract via SQLi    | phantom-exploit
3 | collection     | T1530 - Cloud Storage  | Enumerate S3        | phantom-cloud
```

4. Asks confirmation, then executes each step
5. AI analyzes findings after each phase
6. Saves TXT report to `~/.phantom-strike/reports/`

### Adaptive Memory

AI remembers everything within a session:

```bash
phantom> ai ask "I'm testing example.com, found SQLi on /login"
phantom> ai ask "what should I do next?"   # AI remembers the context
phantom> ai memory                          # see conversation history
phantom> ai clear                           # reset for new target
```

### Web Search in AI

AI automatically searches the web when you ask about CVEs, exploits, tools, or latest techniques — giving you current, real-time information.

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
Phase 6: Exploitation (if auto_exploit=true)
Phase 7: Post-Exploitation + Report Generation
```

Each phase auto-generates a TXT report saved to `~/.phantom-strike/reports/`.

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

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  CLI (Rich TUI)   │  Web Dashboard   │  REST API (FastAPI)   │
│  Daily Quote      │  WebSocket Feed  │  /api/ai/query        │
├──────────────────────────────────────────────────────────────┤
│                  EnhancedPhantomEngine                        │
│   EventBus │ ModuleLoader │ AI Engine │ TaskQueue             │
├──────────────────────────────────────────────────────────────┤
│  OSINT │ Network │ Web │ Cloud │ Identity │ Cred              │
│  Stealth │ Exploit │ C2 │ Post │ Report                       │
├──────────────────────────────────────────────────────────────┤
│  AI Engine (multi-provider, adaptive memory, web search)     │
├──────────────────────────────────────────────────────────────┤
│  SQLite (aiosqlite) │ Playwright Browser │ aiohttp            │
└──────────────────────────────────────────────────────────────┘
```

---

## Testing

```bash
# Run all 28 tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=phantom --cov-report=html
```

28 tests cover: config, EventBus, module loader, stealth payload uniqueness, hash cracking, post-exploitation, C2, database CRUD, attack modes, exploit URL injection, AI backend config, Playwright config.

---

## Legal Disclaimer

PhantomStrike is designed for **authorized penetration testing**, security research, and educational purposes only.

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

---

<p align="center">
  <a href="https://buymeacoffee.com/chandanpandit">
    <img src="https://img.shields.io/badge/☕_Buy_Me_a_Coffee-Support_the_Dev-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee" width="320">
  </a>
</p>

<p align="center">
  <b>If PhantomStrike helped you in a pentest, CTF, or research — consider buying me a coffee!</b><br>
  <a href="https://buymeacoffee.com/chandanpandit"><b>buymeacoffee.com/chandanpandit</b></a>
</p>

<p align="center">
  <i>Built by Chandan Pandey — chandanabhay4456@gmail.com</i>
</p>
