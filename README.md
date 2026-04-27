<p align="center">
  <h1 align="center">🔥 PhantomStrike</h1>
  <p align="center"><b>"See Everything. Strike Anywhere. Leave Nothing."</b></p>
  <p align="center">The World's Most Powerful Open-Source AI-Powered Offensive Security Framework</p>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white"></a>
  <a href="https://github.com/thecnical/phantom-strike/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"></a>
  <a href="https://console.groq.com"><img src="https://img.shields.io/badge/AI-9_FREE_Providers-red?style=for-the-badge&logo=openai&logoColor=white"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"></a>
  <a href="https://render.com"><img src="https://img.shields.io/badge/Deploy-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white"></a>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#%EF%B8%8F-architecture">Architecture</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-usage">Usage</a> •
  <a href="#-api-server">API</a> •
  <a href="#-ai-engine">AI Engine</a> •
  <a href="#-deployment">Deployment</a>
</p>

---

## 🎯 What is PhantomStrike?

PhantomStrike is the **first fully AI-powered, end-to-end offensive security framework** that automates the entire penetration testing lifecycle — from OSINT to exploitation to reporting — using **9 free AI providers** with intelligent failover. No other tool does this.

### Why PhantomStrike?

| Feature | Metasploit | Nmap | Nuclei | Burp Suite | **PhantomStrike** |
|---------|:---------:|:----:|:------:|:----------:|:-----------------:|
| AI Attack Planning | ❌ | ❌ | ❌ | ❌ | ✅ |
| Full Kill Chain Automation | ❌ | ❌ | ❌ | ❌ | ✅ |
| Cloud Security (AWS/Azure/GCP) | ❌ | ❌ | Limited | ❌ | ✅ |
| Identity Attacks (JWT/OAuth) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Polymorphic Payload Generation | ❌ | ❌ | ❌ | ❌ | ✅ |
| C2 Framework | ❌ | ❌ | ❌ | ❌ | ✅ |
| REST API (30+ endpoints) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Multi-Provider AI Failover | ❌ | ❌ | ❌ | ❌ | ✅ |
| Browser Automation (Playwright) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Cost | Free | Free | Free | **$449/yr** | **100% FREE** |

---

## 📔 Table of Contents

- [🎯 What is PhantomStrike?](#-what-is-phantomstrike)
- [✨ Features](#-features)
  - [Reconnaissance](#-reconnaissance)
  - [Vulnerability Discovery](#-vulnerability-discovery)
  - [Exploitation & Post-Exploitation](#-exploitation--post-exploitation)
  - [AI & Evasion](#-ai--evasion)
  - [C2 & Reporting](#-c2--reporting)
- [🏗️ Architecture](#%EF%B8%8F-architecture)
  - [System Workflow](#system-workflow)
  - [Kill Chain Pipeline](#kill-chain-pipeline)
  - [AI Failover System](#ai-failover-system)
- [💿 Installation](#-installation)
  - [Local Installation](#local-installation)
  - [Docker](#docker)
  - [One-Command Install](#one-command-install)
- [⚙️ Configuration](#%EF%B8%8F-configuration)
- [🚀 Usage](#-usage)
  - [CLI Mode](#cli-mode)
  - [API Server Mode](#api-server-mode)
  - [Example Usage](#example-usage)
- [🌐 API Server](#-api-server)
- [🧠 AI Engine](#-ai-engine)
- [☁️ Deployment](#-deployment)
- [🧪 Testing](#-testing)
- [⚠️ Disclaimer](#%EF%B8%8F-disclaimer)
- [📜 License](#-license)

---

## ✨ Features

PhantomStrike packs **12 offensive modules** covering every phase of the MITRE ATT&CK framework.

### 🔍 Reconnaissance

| Capability | Description | Module |
|-----------|-------------|--------|
| **Subdomain Enumeration** | Certificate Transparency (crt.sh) + DNS brute force | `phantom-osint` |
| **Email Harvesting** | Discovers email addresses from target domain | `phantom-osint` |
| **DNS Intelligence** | A, MX, NS, TXT record analysis | `phantom-osint` |
| **Technology Detection** | Server, framework, CMS identification | `phantom-osint` |
| **Port Scanning** | 200-thread async scanner with banner grabbing | `phantom-network` |
| **Service Detection** | Version fingerprinting from banners | `phantom-network` |
| **Browser Crawling** | Playwright-powered JS rendering & endpoint discovery | `core/browser` |

### 💉 Vulnerability Discovery

| Capability | Description | Module |
|-----------|-------------|--------|
| **SQL Injection** | Union, Boolean, Time-based, Error-based detection | `phantom-web` |
| **Cross-Site Scripting** | Reflected & Stored XSS with polymorphic payloads | `phantom-web` |
| **Local File Inclusion** | Path traversal with encoding bypass | `phantom-web` |
| **Server-Side Request Forgery** | Internal network access detection | `phantom-web` |
| **Remote Code Execution** | Command injection detection | `phantom-web` |
| **Security Headers** | Missing CSP, HSTS, X-Frame-Options analysis | `phantom-web` |
| **Cloud Misconfig** | S3 buckets, Azure Blobs, GCP Storage exposure | `phantom-cloud` |
| **Cloud Metadata SSRF** | 169.254.169.254 access detection | `phantom-cloud` |
| **JWT Vulnerabilities** | None algorithm, weak secret, expired token attacks | `phantom-identity` |
| **OAuth/Auth Bypass** | Path traversal, header injection bypass | `phantom-identity` |
| **Credential Testing** | Password spraying with anti-lockout | `phantom-cred` |
| **Hash Cracking** | MD5, SHA1, SHA256, SHA512 dictionary attack | `phantom-cred` |

### ⚡ Exploitation & Post-Exploitation

| Capability | Description | Module |
|-----------|-------------|--------|
| **Auto-Exploit SQLi** | UNION-based data extraction (tables, users, version) | `phantom-exploit` |
| **Auto-Exploit XSS** | Cookie stealing payload injection | `phantom-exploit` |
| **Auto-Exploit LFI** | /etc/passwd, SSH keys, log extraction | `phantom-exploit` |
| **Auto-Exploit RCE** | Command execution (id, whoami, uname) | `phantom-exploit` |
| **Linux PrivEsc** | 14 checks: SUID, sudo, cron, docker, capabilities | `phantom-post` |
| **Lateral Movement** | 8 checks: ARP, SSH, Docker, Kubernetes discovery | `phantom-post` |
| **Persistence** | Cron, SSH key, bashrc, systemd techniques | `phantom-post` |
| **Enumeration Scripts** | Auto-generated bash scripts for target | `phantom-post` |

### 🧠 AI & Evasion

| Capability | Description | Module |
|-----------|-------------|--------|
| **AI Attack Planning** | MITRE ATT&CK-mapped attack chains via Groq LPU | `ai/attack_planner` |
| **AI Vuln Analysis** | Severity assessment & exploit strategy | `ai/engine` |
| **AI Payload Generation** | Context-aware evasive payloads | `ai/attack_planner` |
| **Polymorphic XSS** | 9 tags × 6 events × 5 handlers × 7 encodings | `phantom-stealth` |
| **Polymorphic SQLi** | Random comments, encoding, case mutation | `phantom-stealth` |
| **WAF Bypass** | URL, double-URL, Unicode, hex, base64, HTML entity | `phantom-stealth` |
| **Reverse Shells** | 6 languages: Bash, Python, Perl, PHP, NC, PowerShell | `phantom-stealth` |

### 📡 C2 & Reporting

| Capability | Description | Module |
|-----------|-------------|--------|
| **Agent Management** | Register, track, command remote agents | `phantom-c2` |
| **Agent Payloads** | Python & Bash agent generation | `phantom-c2` |
| **Encrypted Channels** | AES-256-GCM design (HTTPS/WebSocket/DNS) | `phantom-c2` |
| **HTML Reports** | Stunning dark-theme with risk scoring | `phantom-report` |
| **MITRE ATT&CK Mapping** | Automatic technique mapping for findings | `phantom-report` |
| **JSON Export** | Machine-readable results export | `phantom-report` |

---

## 🏗️ Architecture

### System Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│   ┌───────────────┐  ┌──────────────────┐  ┌───────────────────┐   │
│   │   CLI (Rich)  │  │  FastAPI (30+ep) │  │  Future Frontend  │   │
│   └───────┬───────┘  └────────┬─────────┘  └─────────┬─────────┘   │
└───────────┼────────────────────┼──────────────────────┼─────────────┘
            │                    │                      │
            ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       MASTER ENGINE                                 │
│   ┌─────────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│   │  Module Loader   │  │  Event Bus   │  │  Task Queue          │  │
│   │  (Auto-Discover) │  │  (Async PubSub│  │  (Multi-Thread)     │  │
│   └────────┬────────┘  └──────┬───────┘  └──────────────────────┘  │
└────────────┼───────────────────┼────────────────────────────────────┘
             │                   │
┌────────────┼───────────────────┼────────────────────────────────────┐
│            ▼                   ▼           AI LAYER                  │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │              AI ENGINE (9 FREE Providers)                  │    │
│   │  ┌──────┐ ┌──────────┐ ┌──────┐ ┌────────┐ ┌──────────┐  │    │
│   │  │ Groq │→│OpenRouter│→│Gemini│→│Cerebras│→│ 5 More...│  │    │
│   │  │ #0   │ │   #1     │ │  #2  │ │   #3   │ │  #4-#8   │  │    │
│   │  └──────┘ └──────────┘ └──────┘ └────────┘ └──────────┘  │    │
│   └──────────────────────┬─────────────────────────────────────┘    │
│                          ▼                                          │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │  Attack Planner │ Vuln Analyzer │ Payload Generator      │     │
│   └──────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     12 OFFENSIVE MODULES                            │
│  ┌──────┐ ┌───────┐ ┌─────┐ ┌───────┐ ┌──────┐ ┌────────┐        │
│  │OSINT │ │Network│ │ Web │ │ Cloud │ │ Cred │ │Identity│        │
│  └──────┘ └───────┘ └─────┘ └───────┘ └──────┘ └────────┘        │
│  ┌───────┐ ┌───────┐ ┌────┐ ┌──────┐ ┌──────┐                    │
│  │Stealth│ │Exploit│ │ C2 │ │ Post │ │Report│                    │
│  └───────┘ └───────┘ └────┘ └──────┘ └──────┘                    │
└─────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                                │
│   ┌──────────────┐  ┌────────────────┐  ┌────────────────────┐     │
│   │ SQLite (7 DB)│  │ Evidence Store │  │ HTML/JSON Reports  │     │
│   └──────────────┘  └────────────────┘  └────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### Kill Chain Pipeline

PhantomStrike automates the **complete 7-phase kill chain** with a single command:

```
phantom> attack example.com

  Phase 1          Phase 2          Phase 3           Phase 4
┌──────────┐    ┌───────────┐    ┌────────────┐    ┌────────────┐
│  RECON   │───▶│   VULN    │───▶│  AI PLAN   │───▶│  PAYLOAD   │
│  OSINT + │    │  Web+Cloud│    │  Attack    │    │  Polymorphic│
│  Network │    │  +Identity│    │  Chains    │    │  Generation │
└──────────┘    └───────────┘    └────────────┘    └────────────┘
                                                         │
  Phase 7          Phase 6          Phase 5               │
┌──────────┐    ┌───────────┐    ┌────────────┐          │
│  REPORT  │◀───│POST-EXPL  │◀───│  EXPLOIT   │◀─────────┘
│  HTML +  │    │  PrivEsc  │    │  Auto-Run  │
│  MITRE   │    │  Lateral  │    │  Chains    │
└──────────┘    └───────────┘    └────────────┘
```

### AI Failover System

```
Request ──▶ Groq (500+ tps, Priority #0)
             │ rate limited?
             ▼
           OpenRouter (Priority #1)
             │ rate limited?
             ▼
           Gemini (1500 req/day, Priority #2)
             │ rate limited?
             ▼
           Cerebras → Mistral → Together → HuggingFace → NVIDIA → SambaNova
             │
             ▼
           ✅ Response (always succeeds with 9 providers!)

Combined: ~5,000+ free requests/day | ~400 RPM | ₹0 cost
```

---

## 💿 Installation

### Prerequisites

- **Python 3.12+**
- **Linux recommended** (Kali, Parrot, Ubuntu, Debian) — also works on Windows/macOS
- **At least 1 AI API key** (free) — [Groq recommended](https://console.groq.com)

### Local Installation

```bash
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike
pip install -e ".[api]"

# Optional: Browser automation
playwright install chromium

# Setup API keys
cp .env.example .env
# Edit .env — add your GROQ_API_KEY (free from console.groq.com)
```

### Docker

```bash
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike
docker build -t phantom-strike .
docker run -p 10000:10000 --env-file .env phantom-strike
```

### One-Command Install

```bash
bash <(curl -sL https://raw.githubusercontent.com/thecnical/phantom-strike/main/install.sh)
```

---

## ⚙️ Configuration

PhantomStrike uses **3 attack profiles**:

| Profile | Threads | Delay | Auto-Exploit | Use Case |
|---------|---------|-------|:------------:|----------|
| `default.yaml` | 100 | 100ms | ❌ | Balanced scanning |
| `stealth.yaml` | 20 | 2000ms | ❌ | Evade IDS/IPS detection |
| `aggressive.yaml` | 200 | 0ms | ✅ | Maximum speed & coverage |

```bash
# Use specific profile
phantom --config configs/stealth.yaml
```

### AI Provider Setup (`.env`)

```bash
# Priority #0 — FASTEST (500+ tokens/sec)
GROQ_API_KEY=gsk_xxxx              # console.groq.com

# Priority #1-8 — FAILOVER (add as many as you want)
OPENROUTER_API_KEY=sk-or-xxxx      # openrouter.ai
GEMINI_API_KEY=xxxx                # aistudio.google.com
CEREBRAS_API_KEY=xxxx              # cloud.cerebras.ai
MISTRAL_API_KEY=xxxx               # console.mistral.ai
TOGETHER_API_KEY=xxxx              # api.together.ai
HUGGINGFACE_API_KEY=xxxx           # huggingface.co
NVIDIA_API_KEY=xxxx                # build.nvidia.com
SAMBANOVA_API_KEY=xxxx             # cloud.sambanova.ai
```

> 💡 More providers = more resilience. With all 9: **~5,000+ free requests/day, near-zero downtime.**

---

## 🚀 Usage

### CLI Mode

```bash
python -m phantom          # Interactive CLI
phantom-strike             # Or use the command
```

### API Server Mode

```bash
python -m phantom serve              # Default port 10000
python -m phantom serve 8080         # Custom port
uvicorn phantom.api.server:app       # Direct uvicorn
```

### Example Usage

```bash
# ── Reconnaissance ──────────────────────────────
phantom> recon example.com                 # Full OSINT + network recon
phantom> module phantom-osint example.com  # OSINT only

# ── Scanning ────────────────────────────────────
phantom> scan example.com                  # Quick vulnerability scan
phantom> scan example.com phantom-web      # Web-only scan

# ── Full Kill Chain ─────────────────────────────
phantom> attack example.com                # 7-phase automated attack

# ── AI ──────────────────────────────────────────
phantom> ai status                         # Provider status
phantom> ai ask "explain JWT none attack"  # Ask AI anything
phantom> ai plan example.com              # AI attack planning

# ── Stealth Payloads ───────────────────────────
phantom> stealth xss 20                    # 20 polymorphic XSS payloads
phantom> stealth sqli 10                   # 10 polymorphic SQLi payloads
phantom> stealth reverse_shell 10.0.0.1 4444  # 6 reverse shells

# ── C2 (Command & Control) ─────────────────────
phantom> c2 status                         # C2 status
phantom> c2 agents                         # List agents
phantom> c2 generate 10.0.0.1 4444         # Generate agent payload
phantom> c2 cmd agent_abc whoami           # Send command

# ── Reporting ───────────────────────────────────
phantom> report example.com                # Generate HTML report

# ── System ──────────────────────────────────────
phantom> modules                           # List loaded modules
phantom> status                            # Engine status
phantom> help scan                         # Detailed help
```

---

## 🌐 API Server

30+ REST endpoints available at `/docs` (Swagger UI):

| Category | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| **Core** | `GET` | `/health` | Health check |
| | `GET` | `/api/status` | Engine status |
| | `GET` | `/api/modules` | List modules |
| **Scan** | `POST` | `/api/scan` | Run scan |
| | `POST` | `/api/scan/full` | Full kill chain |
| **Module** | `POST` | `/api/module/{name}` | Run any module |
| | `POST` | `/api/osint` | OSINT scan |
| | `POST` | `/api/network` | Port scan |
| | `POST` | `/api/web` | Web vuln scan |
| | `POST` | `/api/cloud` | Cloud scan |
| | `POST` | `/api/identity` | JWT/Auth scan |
| | `POST` | `/api/cred` | Credential attacks |
| | `POST` | `/api/stealth` | Payload generation |
| **AI** | `POST` | `/api/ai/query` | Query AI |
| | `GET` | `/api/ai/status` | Provider status |
| | `POST` | `/api/ai/plan` | Attack planning |
| **C2** | `POST` | `/api/c2/checkin` | Agent check-in |
| | `GET` | `/api/c2/agents` | List agents |
| | `POST` | `/api/c2/command/{id}` | Send command |
| | `POST` | `/api/c2/generate` | Generate agent |
| **Results** | `GET` | `/api/results` | All results |

### API Examples (cURL)

```bash
# Quick scan
curl -X POST https://your-app.onrender.com/api/scan \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com"}'

# AI query
curl -X POST https://your-app.onrender.com/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "How to detect JWT vulnerabilities?"}'

# Generate XSS payloads
curl -X POST https://your-app.onrender.com/api/module/phantom-stealth \
  -H "Content-Type: application/json" \
  -d '{"target": "x", "options": {"type": "xss"}}'
```

---

## 🧠 AI Engine

| # | Provider | Speed | Free Tier | Priority |
|---|----------|-------|-----------|:--------:|
| 🥇 | **Groq** (LPU) | **500+ tps** | 1000 req/day | `#0` |
| 🥈 | OpenRouter | varies | 200 req/day | `#1` |
| 🥉 | Google Gemini | fast | 1500 req/day | `#2` |
| 4 | Cerebras | ultra-fast | 1M tokens/day | `#3` |
| 5 | Mistral | fast | 1B tokens/month | `#4` |
| 6 | Together AI | fast | Free tier | `#5` |
| 7 | HuggingFace | varies | Free inference | `#6` |
| 8 | NVIDIA NIM | fast | Free credits | `#7` |
| 9 | SambaNova | fast | $5 credits | `#8` |

**Combined capacity: ~5,000+ requests/day | ~400 RPM | ₹0**

---

## ☁️ Deployment

### Render (Free Tier)

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New Web Service** → Connect repo
3. Render auto-reads `render.yaml` + `Dockerfile`
4. Add environment variables (API keys)
5. Deploy → Your API is live!

### Docker (VPS)

```bash
docker build -t phantom-strike .
docker run -d -p 10000:10000 \
  -e GROQ_API_KEY=gsk_xxxx \
  phantom-strike
```

---

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v                    # 22 test cases
pytest tests/ -v --cov=phantom      # With coverage
```

---

## 📁 Project Structure

```
phantom-strike/
├── phantom/
│   ├── __main__.py              # Entry point (CLI + API)
│   ├── api/server.py            # FastAPI backend (30+ endpoints)
│   ├── ai/
│   │   ├── engine.py            # 9-provider AI with failover
│   │   └── attack_planner.py    # MITRE ATT&CK attack planner
│   ├── cli/app.py               # Interactive Rich CLI (20 commands)
│   ├── core/
│   │   ├── config.py            # Config + 9 AI providers
│   │   ├── engine.py            # Master orchestration (7-phase)
│   │   ├── events.py            # Async event bus
│   │   ├── loader.py            # Dynamic module loader
│   │   ├── browser.py           # Playwright stealth engine
│   │   └── task_queue.py        # Multi-threaded queue
│   ├── db/store.py              # SQLite (7 tables)
│   └── modules/
│       ├── base.py              # Base module interface
│       ├── osint/engine.py      # OSINT reconnaissance
│       ├── network/engine.py    # Port scanning
│       ├── web/engine.py        # Web vulnerability scanning
│       ├── cloud/engine.py      # Cloud security
│       ├── cred/engine.py       # Credential attacks
│       ├── identity/engine.py   # JWT/OAuth attacks
│       ├── stealth/engine.py    # Polymorphic payloads
│       ├── exploit/engine.py    # Auto-exploitation
│       ├── c2/engine.py         # Command & Control
│       ├── post/engine.py       # Post-exploitation
│       └── report/engine.py     # Report generation
├── configs/                     # Attack profiles
├── tests/test_core.py           # 22 test cases
├── Dockerfile                   # Container build
├── render.yaml                  # Render deployment
└── pyproject.toml               # Python project config
```

---

## ⚠️ Disclaimer

> **PhantomStrike is designed EXCLUSIVELY for authorized penetration testing, security research, and educational purposes.**
>
> - Always obtain **written authorization** before testing any system
> - Never use against systems you don't own or have explicit permission to test
> - The developers are **not responsible** for any misuse of this tool
> - Comply with all applicable local, national, and international laws
> - Usage for attacking targets without prior consent is **illegal**

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  <b>Built with 🔥 for the security community</b><br>
  <sub>56 files | 5,736 lines | 12 modules | 9 AI providers | 30+ API endpoints | ₹0 cost</sub>
</p>
