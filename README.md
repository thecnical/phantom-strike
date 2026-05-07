<p align="center">
  <img src="https://img.shields.io/badge/🔥_PHANTOM_STRIKE-v3.0-FF4444?style=for-the-badge&logo=ghost&logoColor=white" alt="PhantomStrike" width="420">
</p>

<h1 align="center">PhantomStrike — AI-Powered Offensive Security Framework</h1>

<p align="center">
  <b>Fully autonomous, multi-agent penetration testing framework with AI attack planning,<br>
  Knowledge Graph, 13 specialist agents, and a complete offensive toolkit.</b>
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
  <img src="https://img.shields.io/badge/Version-3.0.0--alpha-FF4444?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Tests-411_passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/Agents-13_specialist-blueviolet?style=flat-square" alt="Agents">
  <img src="https://img.shields.io/badge/AI-Unrestricted-FF4444?style=flat-square" alt="AI">
</p>

---

## What's New in v3.0

PhantomStrike v3.0 is a complete upgrade from v2.0 — same familiar CLI, massively expanded capabilities:

| Feature | v2.0 | v3.0 |
|:--------|:----:|:----:|
| Modules | 11 | **15** (+ AD, Sliver C2, ExploitDB, Reverser) |
| Agents | ❌ | **13 specialist agents** |
| Autonomous attack | ❌ | ✅ `autonomous <target>` |
| Knowledge Graph | ❌ | ✅ SQLite-backed attack graph |
| OPPLAN system | ❌ | ✅ Dependency-aware objective planning |
| Rules of Engagement | ❌ | ✅ CIDR/glob/time-window enforcement |
| Docker sandbox | ❌ | ✅ Kali Linux container for tool execution |
| Skill library | ❌ | ✅ 16 YAML technique files |
| Active Directory | ❌ | ✅ Kerberoast, AS-REP, LDAP enum |
| Sliver C2 | ❌ | ✅ gRPC implant generation |
| Binary analysis | ❌ | ✅ ROP gadgets, disassembly, strings |
| Tests | 28 | **411** (property-based + integration) |

---

## What is PhantomStrike?

**PhantomStrike** is a fully open-source, AI-powered penetration testing framework. v3.0 adds a **multi-agent autonomous attack engine** — 13 specialist agents coordinated by an AI orchestrator, all sharing a live Knowledge Graph of findings.

**Core capabilities:**
- **Autonomous attack** — one command launches a full AI-planned engagement
- **13 specialist agents** — Recon, Scanner, WebExploit, Cloud, Cred, AD, Exploit, PostExploit, C2, Stealth, Reverser, Analyst, Report
- **Knowledge Graph** — SQLite graph tracks hosts, vulns, creds, attack paths across the engagement
- **Rules of Engagement** — CIDR/glob target filtering, MITRE technique allow/deny lists, rate limiting, engagement windows
- **OPPLAN system** — dependency-aware objective graph with cycle detection and YAML serialization
- **Docker sandbox** — run nmap, sqlmap, hydra, hashcat, metasploit, impacket in an isolated Kali container
- **Unrestricted AI** — no topic filters, persistent chat, adaptive memory, web search
- **411 tests** — property-based (Hypothesis) + unit + integration

---

## Installation

### Fresh install (recommended)

```bash
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike
bash install.sh
```

Works on: **Kali Linux, Ubuntu 20.04+, Debian 11+, Parrot OS, Arch, Fedora, macOS**

After install, run from **anywhere**:
```bash
phantom          # interactive CLI
phantom serve    # web dashboard → http://localhost:10000
```

### Install with optional v3.0 components

```bash
# Full v3.0 stack (Docker sandbox, AD attacks, binary analysis)
bash install.sh --v3

# Development install (includes pytest, ruff, mypy)
bash install.sh --dev

# Skip Playwright browser download
bash install.sh --no-browser
```

### Updating from v2.0

```bash
cd /path/to/phantom-strike
git pull
bash install.sh --update
```

The update preserves your `.env` API keys and `~/.phantom-strike/` data directory.

**What changes from v2.0 → v3.0:**
- All 11 v2.0 modules still work unchanged
- 4 new modules added (phantom-ad, phantom-sliver, phantom-exploitdb, phantom-reverser)
- New CLI commands: `autonomous`, `opplan`, `graph`, `agents`, `sandbox`, `roe`, `skills`
- Engine now initializes KnowledgeGraph, RoEMiddleware, SkillLibrary, DockerSandbox on startup

---

## Usage

### Interactive CLI

```bash
phantom
```

**v2.0 commands (unchanged):**
```
phantom> scan example.com              # vulnerability scan
phantom> attack example.com           # full 7-phase kill chain
phantom> recon example.com            # OSINT + network recon
phantom> ai ask "explain XSS"         # ask AI anything
phantom> ai chat                      # persistent AI chat (type 'bye' to exit)
phantom> ai plan example.com          # AI generates + executes attack plan
phantom> stealth xss 20               # polymorphic XSS payloads
phantom> c2 generate 10.0.0.1 4444    # generate C2 agent
phantom> module phantom-web target.com
phantom> report example.com
phantom> results
phantom> exit
```

**New v3.0 commands:**
```
phantom> autonomous example.com       # fully autonomous AI-driven attack 🤖
phantom> opplan list                  # show all OPPLAN objectives
phantom> opplan load /path/plan.yaml  # load saved OPPLAN
phantom> graph                        # ASCII knowledge graph visualization
phantom> agents                       # show all 13 specialist agents + status
phantom> sandbox status               # Docker sandbox availability
phantom> roe violations               # show Rules of Engagement violation log
phantom> skills list                  # list all 16 offensive skills
```

### Autonomous Attack

```bash
phantom> autonomous 192.168.1.0/24
```

1. AI generates a full OPPLAN (Recon → Scan → Exploit → Post → Report)
2. Displays the plan for operator approval
3. Dispatches objectives to specialist agents in dependency order
4. Agents update the Knowledge Graph with findings in real time
5. AI decides next objectives based on KG state
6. ReportAgent generates final report from full KG

### Knowledge Graph

```bash
phantom> graph
```

```
[HOST] 192.168.1.1
  └─ [VULN] SQL Injection@1:http://192.168.1.1/login
  └─ [VULN] Outdated Apache@1
  └─ [CRED] admin
[HOST] 192.168.1.50
  └─ [VULN] Kerberoastable SPN@2
  └─ [SERVICE] smb/445@192.168.1.50
```

### Rules of Engagement

```bash
phantom> roe violations
```

Shows every blocked action with timestamp, target, technique, and reason.

---

## Modules (15 total)

### v2.0 Modules (unchanged)

| Module | Category | What it does |
|:-------|:---------|:-------------|
| `phantom-osint` | Recon | Subdomain enum, email harvest, tech detection |
| `phantom-network` | Recon | Async port scan, banner grabbing, OS fingerprint |
| `phantom-web` | Vuln | SQLi, XSS, XXE, CSRF, LFI, SSRF, IDOR, JWT |
| `phantom-cloud` | Vuln | S3/Azure/GCP bucket enum, metadata SSRF, IAM |
| `phantom-identity` | Vuln | JWT none-algorithm, weak secret brute force |
| `phantom-cred` | Cred | Password spraying, brute force, hash cracking |
| `phantom-stealth` | Evasion | Polymorphic payloads, WAF bypass, reverse shells |
| `phantom-exploit` | Exploit | SQLi extraction, LFI read, SSRF, RCE |
| `phantom-c2` | C2 | Agent registration, command queuing, payload gen |
| `phantom-post` | Post | Privesc, lateral movement, persistence, LSASS dump |
| `phantom-report` | Report | HTML + JSON + TXT reports with MITRE mapping |

### v3.0 New Modules

| Module | Category | What it does |
|:-------|:---------|:-------------|
| `phantom-ad` | Active Directory | Kerberoasting, AS-REP roasting, BloodHound, LDAP enum |
| `phantom-sliver` | C2 | Sliver gRPC implant generation (fallback to phantom-c2) |
| `phantom-exploitdb` | Exploit | CVE/keyword search via searchsploit or exploit-db.com API |
| `phantom-reverser` | Reverse Eng | Binary analysis, ROP gadgets, r2pipe/objdump disassembly |

All v3.0 modules **degrade gracefully** — if impacket, Sliver, searchsploit, or radare2 are not installed, the module returns a clean error and the rest of the framework continues normally.

---

## 13 Specialist Agents

| Agent | Phase | What it does |
|:------|:------|:-------------|
| `ReconAgent` | Recon | OSINT + network discovery → adds hosts to KG |
| `ScannerAgent` | Scan | Port/service scanning → adds services + vulns to KG |
| `WebExploitAgent` | Exploit | Web vuln discovery → adds web vulns to KG |
| `CloudAgent` | Exploit | Cloud misconfiguration → adds findings to KG |
| `CredAgent` | Cred | Credential harvesting → adds creds to KG |
| `ADAgent` | AD | Kerberoast/AS-REP/LDAP → adds AD findings to KG |
| `ExploitAgent` | Exploit | CVE exploitation → marks vulns as exploited in KG |
| `PostExploitAgent` | Post | Persistence, lateral move, LSASS dump → updates KG |
| `C2Agent` | C2 | Sliver/phantom-c2 implant generation → adds to KG |
| `StealthAgent` | Evasion | AV/EDR bypass payloads, log clearing |
| `ReverserAgent` | Reverser | Binary analysis → adds findings to KG |
| `AnalystAgent` | Analysis | Synthesizes KG → suggests next objectives |
| `ReportAgent` | Report | Full KG → professional engagement report |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLI (Rich TUI)   │  Web Dashboard   │  REST API (FastAPI)          │
├─────────────────────────────────────────────────────────────────────┤
│                    EnhancedPhantomEngine v3.0                        │
│  EventBus │ ModuleLoader │ AI Engine │ KnowledgeGraph │ RoEMiddleware│
│  SkillLibrary │ DockerSandbox │ PhantomOrchestrator                  │
├─────────────────────────────────────────────────────────────────────┤
│  PhantomOrchestrator                                                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  OPPLAN (dependency graph) → asyncio.gather() dispatch      │    │
│  │  ai_decide_next() → dynamic objective expansion             │    │
│  └─────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│  13 Specialist Agents (BaseAgent → RoE check → KG update)           │
├─────────────────────────────────────────────────────────────────────┤
│  15 Modules │ KnowledgeGraph (SQLite) │ SkillLibrary (YAML)         │
│  DockerSandbox (kalilinux/kali-rolling) │ ConversationSummarizer     │
├─────────────────────────────────────────────────────────────────────┤
│  AI Engine (multi-provider, adaptive memory, web search)            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Optional v3.0 Dependencies

These are **optional** — the framework works without them, modules just degrade gracefully:

| Dependency | What it enables | Install |
|:-----------|:----------------|:--------|
| `impacket` | Kerberoasting, AS-REP roasting | `pip install impacket` |
| `ldap3` | LDAP enumeration | `pip install ldap3` |
| `docker` (Python SDK) | Docker sandbox | `pip install docker` |
| `r2pipe` | Radare2 disassembly | `pip install r2pipe` |
| `sliver-client` (binary) | Sliver C2 implants | [sliver.sh/install](https://sliver.sh/install) |
| `searchsploit` (binary) | Local ExploitDB search | `apt install exploitdb` |
| `bloodhound-python` | BloodHound collection | `pip install bloodhound` |
| `ROPgadget` | ROP gadget finding | `pip install ROPgadget` |
| `pypykatz` | LSASS hash extraction | `pip install pypykatz` |

Install all at once:
```bash
pip install "phantom-strike[v3]"
# or
bash install.sh --v3
```

---

## Testing

```bash
# Run all 411 tests
pytest tests/ -v

# Run only original 28 v2.0 tests
pytest tests/test_core.py -v

# Run v3.0 tests by category
pytest tests/test_v3_roe.py -v          # RoE middleware
pytest tests/test_v3_knowledge_graph.py -v  # Knowledge Graph
pytest tests/test_v3_opplan.py -v       # OPPLAN system
pytest tests/test_v3_agents.py -v       # BaseAgent
pytest tests/test_v3_integration.py -v  # End-to-end pipeline

# With coverage
pytest tests/ --cov=phantom --cov-report=html
```

**Test breakdown:**
- 28 original v2.0 tests (all still pass)
- 383 new v3.0 tests: property-based (Hypothesis), unit, integration
- 10 property-based tests covering: RoE forbidden precedence, KG deduplication, OPPLAN serialization, dependency soundness, cycle rejection, summarizer verbatim preservation, agent context isolation, graceful degradation, rate limit enforcement, existing test preservation

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
| `/api/attack/start` | POST | Start attack mode |
| `/api/results` | GET | All scan results |
| `/docs` | GET | Swagger UI |

---

## Legal Disclaimer

PhantomStrike is designed for **authorized penetration testing**, security research, and educational purposes only.

- Only scan systems you own or have **written authorization** to test
- Follow responsible disclosure for any vulnerabilities found
- Comply with all applicable laws in your jurisdiction

The developers assume no liability for misuse. See [DISCLAIMER.md](DISCLAIMER.md).

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
