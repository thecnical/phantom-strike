# 🔥 PhantomStrike

> **"See Everything. Strike Anywhere. Leave Nothing."**

The World's Most Powerful Open-Source AI-Powered Offensive Security Framework.

[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![AI](https://img.shields.io/badge/AI-Groq%20LPU-red?logo=ai)](https://console.groq.com)
[![API](https://img.shields.io/badge/API-FastAPI-teal?logo=fastapi)](https://fastapi.tiangolo.com)

---

## ⚡ What Makes PhantomStrike Different?

| Feature | Metasploit | Nmap | Nuclei | Burp Suite | **PhantomStrike** |
|---------|-----------|------|--------|-----------|-------------------|
| AI Attack Planning | ❌ | ❌ | ❌ | ❌ | ✅ 9 FREE AI providers |
| Full Kill Chain | ❌ | ❌ | ❌ | ❌ | ✅ 7-phase auto chain |
| Cloud Security | ❌ | ❌ | Limited | ❌ | ✅ AWS/Azure/GCP |
| Identity Attacks | ❌ | ❌ | ❌ | ❌ | ✅ JWT/OAuth/AuthBypass |
| Polymorphic Payloads | ❌ | ❌ | ❌ | ❌ | ✅ Never same twice |
| C2 Framework | ❌ | ❌ | ❌ | ❌ | ✅ Multi-protocol |
| REST API | ❌ | ❌ | ❌ | ❌ | ✅ 30+ endpoints |
| Cost | Free | Free | Free | **$449/yr** | ✅ **100% FREE** |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **Linux** (Kali, Parrot, Ubuntu, Debian) — recommended
- **Groq API Key** (free) — [Get it here](https://console.groq.com)

### Installation

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/phantom-strike.git
cd phantom-strike

# Install
pip install -e ".[api]"

# Install browser engine (optional but recommended)
playwright install chromium

# Setup API keys
cp .env.example .env
# Edit .env and add your GROQ_API_KEY (free from console.groq.com)
```

### Run CLI Mode

```bash
# Interactive CLI
python -m phantom

# Or use the command
phantom-strike
```

### Run API Server (for Render/Cloud deployment)

```bash
# Start API server
python -m phantom serve

# Or with custom port
python -m phantom serve 8000

# Or with uvicorn directly
uvicorn phantom.api.server:app --host 0.0.0.0 --port 10000
```

---

## 🧠 AI Providers (9 FREE — Zero Cost)

PhantomStrike uses **9 free AI providers** with smart failover. If one hits rate limit, it automatically switches to the next.

| Priority | Provider | Speed | Free Tier |
|----------|----------|-------|-----------|
| 🥇 #0 | **Groq** | 500+ tps (LPU) | 1000 req/day |
| 🥈 #1 | OpenRouter | varies | 200 req/day |
| 🥉 #2 | Google Gemini | fast | 1500 req/day |
| #3 | Cerebras | ultra-fast | 1M tokens/day |
| #4 | Mistral | fast | 1B tokens/month |
| #5 | Together AI | fast | Free tier |
| #6 | HuggingFace | varies | Free inference |
| #7 | NVIDIA NIM | fast | Free credits |
| #8 | SambaNova | fast | $5 credits |

### Setup API Keys

```bash
# .env file — add as many as you want (minimum 1)
GROQ_API_KEY=gsk_xxxx          # Get from console.groq.com (RECOMMENDED)
OPENROUTER_API_KEY=sk-or-xxxx  # Get from openrouter.ai
GEMINI_API_KEY=xxxx            # Get from aistudio.google.com
```

---

## 📦 12 Offensive Modules

| # | Module | Description |
|---|--------|-------------|
| 1 | 🔍 **phantom-osint** | Subdomains, emails, DNS, tech detection |
| 2 | 🌐 **phantom-network** | 200-thread port scan, banner grabbing |
| 3 | 🕷️ **phantom-web** | SQLi, XSS, LFI, SSRF, RCE scanning |
| 4 | ☁️ **phantom-cloud** | AWS S3, Azure Blobs, GCP, metadata SSRF |
| 5 | 🔐 **phantom-cred** | Password spray, brute force, hash cracking |
| 6 | 🛡️ **phantom-identity** | JWT forgery, OAuth, auth bypass |
| 7 | 👻 **phantom-stealth** | Polymorphic payloads, WAF bypass, reverse shells |
| 8 | ⚡ **phantom-exploit** | Auto-exploit SQLi, XSS, LFI, RCE |
| 9 | 📡 **phantom-c2** | Agent management, encrypted channels |
| 10 | 🎯 **phantom-post** | Privesc, lateral movement, persistence |
| 11 | 📊 **phantom-report** | HTML reports with MITRE ATT&CK mapping |
| 12 | 📦 **base** | Module architecture framework |

---

## 🖥️ CLI Commands

```
phantom> help                          # Show all commands
phantom> scan example.com              # Quick vulnerability scan
phantom> recon example.com             # Full OSINT + network recon
phantom> attack example.com            # Full 7-phase kill chain 🔥
phantom> module phantom-web target.com # Run specific module
phantom> ai status                     # AI provider status
phantom> ai ask "explain JWT forgery"  # Ask AI anything
phantom> ai plan example.com           # AI attack planning
phantom> c2 status                     # C2 server status
phantom> c2 agents                     # List active agents
phantom> c2 generate 10.0.0.1 4444     # Generate C2 agent payload
phantom> stealth xss 20                # Generate 20 polymorphic XSS payloads
phantom> stealth reverse_shell 10.0.0.1 4444  # Generate reverse shells
phantom> report example.com            # Generate pentest report
phantom> results                       # Show stored results
phantom> modules                       # List loaded modules
phantom> status                        # Engine status
phantom> config                        # Show configuration
```

---

## 🌐 REST API (30+ Endpoints)

When running as API server (`python -m phantom serve`):

### Core
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Welcome page |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger API docs |
| GET | `/api/status` | Engine status |
| GET | `/api/modules` | List modules |

### Scanning
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scan` | Run scan with modules |
| POST | `/api/scan/full` | Full kill chain |
| POST | `/api/module/{name}` | Run specific module |

### AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/query` | Query AI |
| GET | `/api/ai/status` | Provider status |
| POST | `/api/ai/plan` | Attack planning |

### C2
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/c2/checkin` | Agent check-in |
| GET | `/api/c2/agents` | List agents |
| POST | `/api/c2/command/{id}` | Send command |
| POST | `/api/c2/generate` | Generate payload |

### API Example (cURL)

```bash
# Scan a target
curl -X POST https://YOUR_APP.onrender.com/api/scan \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "modules": ["phantom-web"]}'

# Ask AI
curl -X POST https://YOUR_APP.onrender.com/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "How to detect JWT vulnerabilities?"}'

# Generate polymorphic payloads
curl -X POST https://YOUR_APP.onrender.com/api/module/phantom-stealth \
  -H "Content-Type: application/json" \
  -d '{"target": "test.com", "options": {"type": "xss"}}'
```

---

## 🚀 Deploy on Render (FREE)

### Method 1: One-Click (render.yaml)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repository
4. Render auto-reads `render.yaml` and `Dockerfile`
5. Add environment variables (GROQ_API_KEY, etc.)
6. Deploy!

### Method 2: Manual

1. **Create New Web Service** on Render
2. **Environment**: Docker
3. **Build Command**: (auto from Dockerfile)
4. **Start Command**: `uvicorn phantom.api.server:app --host 0.0.0.0 --port 10000`
5. **Add Environment Variables**:
   - `GROQ_API_KEY` = your key
   - `PORT` = 10000

Your API will be live at: `https://phantom-strike-api.onrender.com`

---

## ⚙️ Configuration

### Attack Profiles

```bash
# Default (balanced)
phantom --config configs/default.yaml

# Stealth (slow, evasive)
phantom --config configs/stealth.yaml

# Aggressive (fast, loud)
phantom --config configs/aggressive.yaml
```

### Custom Config

Create `phantom.yaml` in project root:

```yaml
log_level: INFO
attack:
  profile: balanced
  safe_mode: true
  auto_exploit: false
threading:
  max_scan_threads: 100
  max_workers: 20
```

---

## 🧪 Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=phantom
```

---

## 📁 Project Structure

```
phantom-strike/
├── phantom/
│   ├── __main__.py              # Entry point (CLI + API)
│   ├── api/
│   │   └── server.py            # FastAPI backend (30+ endpoints)
│   ├── ai/
│   │   ├── engine.py            # 9-provider AI engine
│   │   └── attack_planner.py    # AI attack chain planner
│   ├── cli/
│   │   └── app.py               # Interactive Rich CLI
│   ├── core/
│   │   ├── config.py            # Configuration + AI providers
│   │   ├── engine.py            # Master orchestration engine
│   │   ├── events.py            # Async event bus
│   │   ├── loader.py            # Dynamic module loader
│   │   ├── browser.py           # Playwright browser engine
│   │   └── task_queue.py        # Multi-threaded task queue
│   ├── db/
│   │   └── store.py             # SQLite database layer
│   └── modules/
│       ├── base.py              # Base module interface
│       ├── osint/engine.py      # OSINT reconnaissance
│       ├── network/engine.py    # Network port scanning
│       ├── web/engine.py        # Web vulnerability scanning
│       ├── cloud/engine.py      # Cloud security (AWS/Azure/GCP)
│       ├── cred/engine.py       # Credential attacks
│       ├── identity/engine.py   # JWT/OAuth/Auth attacks
│       ├── stealth/engine.py    # Polymorphic payload generation
│       ├── exploit/engine.py    # Multi-vector exploitation
│       ├── c2/engine.py         # Command & Control
│       ├── post/engine.py       # Post-exploitation
│       └── report/engine.py     # Report generation
├── configs/
│   ├── default.yaml
│   ├── stealth.yaml
│   └── aggressive.yaml
├── tests/
│   └── test_core.py             # 22 test cases
├── Dockerfile                   # Docker build
├── render.yaml                  # Render deployment
├── pyproject.toml               # Python project config
├── .env.example                 # API key template
├── install.sh                   # One-command installer
└── DISCLAIMER.md                # Legal disclaimer
```

---

## ⚠️ Legal Disclaimer

> **PhantomStrike is designed EXCLUSIVELY for authorized penetration testing, security research, and educational purposes.**
>
> - Always obtain **written authorization** before testing any system
> - Never use against systems you don't own or have explicit permission to test
> - The developers are **not responsible** for any misuse
> - Comply with all applicable laws

---

## 📄 License

MIT License — 100% Free, Open Source.

---

**Built with 🔥 by PhantomStrike Team**
