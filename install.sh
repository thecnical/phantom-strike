#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  PhantomStrike — One-Command Installer v2.0
#  Supports: Ubuntu 20.04+, Debian 11+, Kali Linux, Parrot OS, Arch, macOS
#
#  Usage (fresh install):
#    curl -sSL https://raw.githubusercontent.com/thecnical/phantom-strike/main/install.sh | bash
#
#  Usage (local clone):
#    chmod +x install.sh && ./install.sh
#
#  Options:
#    --dev        Install dev/test dependencies (pytest, ruff, mypy)
#    --no-browser Skip Playwright browser download
#    --no-venv    Install into current Python env (not recommended)
#    --update     Update an existing installation
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ── Flags ─────────────────────────────────────────────────────────────────
INSTALL_DEV=false
SKIP_BROWSER=false
NO_VENV=false
UPDATE_MODE=false

for arg in "$@"; do
    case $arg in
        --dev)        INSTALL_DEV=true ;;
        --no-browser) SKIP_BROWSER=true ;;
        --no-venv)    NO_VENV=true ;;
        --update)     UPDATE_MODE=true ;;
    esac
done

# ── Constants ─────────────────────────────────────────────────────────────
PHANTOM_DIR="$HOME/.phantom-strike"
VENV_DIR="$PHANTOM_DIR/venv"
VENV_BIN="$VENV_DIR/bin"
REPO_URL="https://github.com/thecnical/phantom-strike.git"
MIN_PYTHON="3.10"
VERSION="2.0.0"

# ── Banner ────────────────────────────────────────────────────────────────
echo -e "${RED}"
echo "  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗"
echo "  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║"
echo "  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║"
echo "  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║"
echo "  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║"
echo "  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝"
echo -e "${CYAN}                    S T R I K E  v${VERSION}${NC}"
echo -e "${YELLOW}         AI-Powered Offensive Security Framework${NC}"
echo -e "${YELLOW}         \"See Everything. Strike Anywhere. Leave Nothing.\"${NC}"
echo ""

if [ "$UPDATE_MODE" = true ]; then
    echo -e "${CYAN}  Mode: UPDATE existing installation${NC}"
else
    echo -e "${CYAN}  Mode: FRESH installation${NC}"
fi
echo ""

# ── Helper functions ──────────────────────────────────────────────────────
info()    { echo -e "${CYAN}[*]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step()    { echo -e "\n${BOLD}${BLUE}── Step $1 ──────────────────────────────────────────${NC}"; }

# ── Detect OS ─────────────────────────────────────────────────────────────
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &>/dev/null; then
            OS="debian"
        elif command -v pacman &>/dev/null; then
            OS="arch"
        elif command -v dnf &>/dev/null; then
            OS="fedora"
        else
            OS="linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="unknown"
    fi
    info "Detected OS: $OS ($OSTYPE)"
}

# ── Check Python ──────────────────────────────────────────────────────────
check_python() {
    step "1/8 — Python version check"

    # Try python3 first, then python
    PYTHON_BIN=""
    for bin in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$bin" &>/dev/null; then
            VER=$("$bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
            MAJOR=$(echo "$VER" | cut -d. -f1)
            MINOR=$(echo "$VER" | cut -d. -f2)
            if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
                PYTHON_BIN="$bin"
                PYTHON_VERSION="$VER"
                break
            fi
        fi
    done

    if [ -z "$PYTHON_BIN" ]; then
        warn "Python ${MIN_PYTHON}+ not found. Attempting to install..."
        install_python
    else
        success "Python ${PYTHON_VERSION} found at $(command -v $PYTHON_BIN)"
    fi
}

install_python() {
    case "$OS" in
        debian)
            info "Installing Python 3.12 via apt..."
            sudo apt-get update -qq
            sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
            PYTHON_BIN="python3.12"
            ;;
        arch)
            info "Installing Python via pacman..."
            sudo pacman -Sy --noconfirm python python-pip
            PYTHON_BIN="python3"
            ;;
        fedora)
            info "Installing Python via dnf..."
            sudo dnf install -y python3.12 python3.12-devel python3-pip
            PYTHON_BIN="python3.12"
            ;;
        macos)
            if command -v brew &>/dev/null; then
                info "Installing Python via Homebrew..."
                brew install python@3.12
                PYTHON_BIN="python3.12"
            else
                error "Homebrew not found. Install from https://brew.sh then re-run."
            fi
            ;;
        *)
            error "Cannot auto-install Python on this OS. Install Python ${MIN_PYTHON}+ manually."
            ;;
    esac
    success "Python installed"
}

# ── Install system dependencies ───────────────────────────────────────────
install_system_deps() {
    step "2/8 — System dependencies"

    case "$OS" in
        debian)
            info "Installing system packages (apt)..."
            sudo apt-get update -qq 2>/dev/null || true
            # python3-venv is CRITICAL — must install before setup_venv
            sudo apt-get install -y \
                git curl wget build-essential \
                libssl-dev libffi-dev libxml2-dev libxslt1-dev \
                python3-dev python3-pip python3-venv \
                nmap libpcap-dev \
                libpango-1.0-0 libpangoft2-1.0-0 \
                libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
                libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
                libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
                2>/dev/null || warn "Some system packages failed — continuing anyway"

            # Kali/Debian: also install venv for the specific python version found
            if [ -n "${PYTHON_BIN:-}" ]; then
                local pyver
                pyver=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "3")
                sudo apt-get install -y "python${pyver}-venv" 2>/dev/null || true
            fi
            ;;
        arch)
            info "Installing system packages (pacman)..."
            sudo pacman -Sy --noconfirm \
                git curl wget base-devel openssl libffi \
                nmap libpcap 2>/dev/null || warn "Some packages failed — continuing"
            ;;
        fedora)
            info "Installing system packages (dnf)..."
            sudo dnf install -y \
                git curl wget gcc openssl-devel libffi-devel \
                nmap libpcap-devel 2>/dev/null || warn "Some packages failed — continuing"
            ;;
        macos)
            if command -v brew &>/dev/null; then
                info "Installing system packages (brew)..."
                brew install git curl nmap libpcap 2>/dev/null || warn "Some brew packages failed"
            fi
            ;;
    esac
    success "System dependencies ready"
}

# ── Clone or update repo ──────────────────────────────────────────────────
setup_repo() {
    step "3/8 — Repository"

    # Case 1: Running from inside the cloned repo already
    if [ -f "pyproject.toml" ] && grep -q "phantom-strike" pyproject.toml 2>/dev/null; then
        REPO_PATH="$(pwd)"
        success "Running from local clone: $REPO_PATH"
        return
    fi

    # Case 2: phantom-strike folder exists in current directory
    if [ -d "phantom-strike" ] && [ -f "phantom-strike/pyproject.toml" ]; then
        REPO_PATH="$(pwd)/phantom-strike"
        success "Found local clone at: $REPO_PATH"
        return
    fi

    # Case 3: Already cloned to default location
    REPO_PATH="$PHANTOM_DIR/src"
    if [ -d "$REPO_PATH" ] && [ -f "$REPO_PATH/pyproject.toml" ]; then
        if [ "$UPDATE_MODE" = true ]; then
            info "Pulling latest changes..."
            git -C "$REPO_PATH" pull --rebase --autostash 2>/dev/null || \
                warn "Git pull failed — using existing code"
            success "Repository updated"
        else
            success "Using existing clone at: $REPO_PATH"
        fi
        return
    fi

    # Case 4: Need to clone fresh
    if [ -d "$REPO_PATH" ]; then
        warn "Removing incomplete installation..."
        rm -rf "$REPO_PATH"
    fi
    info "Cloning PhantomStrike into $REPO_PATH ..."
    git clone --depth=1 "$REPO_URL" "$REPO_PATH" || \
        error "Git clone failed. Check internet connection."
    success "Repository cloned to $REPO_PATH"
}

# ── Create virtual environment ────────────────────────────────────────────
setup_venv() {
    step "4/8 — Virtual environment"

    if [ "$NO_VENV" = true ]; then
        warn "--no-venv flag set. Installing into current Python environment."
        VENV_BIN="$(dirname $(command -v $PYTHON_BIN))"
        return
    fi

    # Ensure python3-venv is available (critical for Kali/Debian externally-managed)
    if ! "$PYTHON_BIN" -m venv --help &>/dev/null 2>&1; then
        warn "python3-venv not available. Installing..."
        case "$OS" in
            debian)
                local pyver
                pyver=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "3")
                sudo apt-get install -y "python${pyver}-venv" python3-venv 2>/dev/null || \
                    error "Cannot install python3-venv. Run: sudo apt install python3-venv"
                ;;
            arch) sudo pacman -Sy --noconfirm python 2>/dev/null || true ;;
            fedora) sudo dnf install -y python3-venv 2>/dev/null || true ;;
        esac
    fi

    if [ "$UPDATE_MODE" = true ] && [ -d "$VENV_DIR" ]; then
        info "Reusing existing virtual environment at $VENV_DIR"
    else
        info "Creating virtual environment at $VENV_DIR..."
        "$PYTHON_BIN" -m venv "$VENV_DIR" || \
            error "Failed to create venv. Run: sudo apt install python3-venv python3-full"
        success "Virtual environment created"
    fi

    # Activate
    # shellcheck disable=SC1090
    source "$VENV_BIN/activate"
    success "Virtual environment activated (Python $(python --version 2>&1 | cut -d' ' -f2))"
}

# ── Install Python packages ───────────────────────────────────────────────
install_packages() {
    step "5/8 — Python packages"

    # Safety check: we must be inside a venv to avoid externally-managed-environment error
    if [ -z "${VIRTUAL_ENV:-}" ] && [ "$NO_VENV" = false ]; then
        warn "Not inside a virtual environment. Activating..."
        # shellcheck disable=SC1090
        source "$VENV_BIN/activate" || error "Cannot activate venv at $VENV_BIN"
    fi

    # CRITICAL: cd into the repo so pip finds pyproject.toml
    # This is the fix for "does not appear to be a Python project" error
    if [ -z "${REPO_PATH:-}" ] || [ ! -f "${REPO_PATH}/pyproject.toml" ]; then
        error "Cannot find pyproject.toml in '${REPO_PATH:-<unset>}'. Run install.sh from inside the phantom-strike folder."
    fi

    info "Upgrading pip, setuptools, wheel..."
    pip install --upgrade pip setuptools wheel --quiet

    # Build the pip install command
    INSTALL_EXTRAS="api"
    if [ "$INSTALL_DEV" = true ]; then
        INSTALL_EXTRAS="api,dev"
        info "Installing with dev extras (pytest, ruff, mypy)..."
    fi

    info "Installing PhantomStrike from: ${REPO_PATH}"
    info "This may take 2-5 minutes on first install..."

    # cd into repo first, then install with -e .
    # This is the ONLY reliable way — avoids path quoting issues
    (
        cd "${REPO_PATH}" || error "Cannot cd into ${REPO_PATH}"
        pip install -e ".[${INSTALL_EXTRAS}]" \
            --no-warn-script-location \
            2>&1 | grep -E "(Successfully|ERROR|error|WARNING|Collecting|Installing)" || true
    )

    # Verify key packages installed
    REQUIRED_PACKAGES=(
        "rich" "fastapi" "uvicorn" "aiohttp" "httpx"
        "pydantic" "pydantic_settings" "aiosqlite"
        "beautifulsoup4" "dnspython" "playwright"
    )

    MISSING=()
    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        if ! python -c "import ${pkg//-/_}" &>/dev/null 2>&1; then
            MISSING+=("$pkg")
        fi
    done

    if [ ${#MISSING[@]} -gt 0 ]; then
        warn "Some packages failed to import: ${MISSING[*]}"
        warn "Attempting individual install..."
        for pkg in "${MISSING[@]}"; do
            pip install "$pkg" --quiet || warn "Could not install $pkg"
        done
    fi

    success "Python packages installed"
}

# ── Install Playwright browsers ───────────────────────────────────────────
install_playwright() {
    step "6/8 — Playwright browser engine"

    if [ "$SKIP_BROWSER" = true ]; then
        warn "--no-browser flag set. Skipping Playwright browser download."
        warn "Browser-based XSS verification will be unavailable."
        warn "Install later with: playwright install chromium"
        return
    fi

    info "Installing Chromium browser for Playwright..."
    info "(Required for JS-rendered XSS detection and screenshot evidence)"

    if playwright install chromium 2>/dev/null; then
        success "Chromium browser installed"
    else
        warn "Playwright browser install failed. Trying with system deps..."
        playwright install chromium --with-deps 2>/dev/null || \
            warn "Browser install failed. Run 'playwright install chromium' manually."
    fi

    # Install system deps for Playwright (Linux only)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        playwright install-deps chromium 2>/dev/null || true
    fi

    success "Playwright ready"
}

# ── Setup config and directories ──────────────────────────────────────────
setup_config() {
    step "7/8 — Configuration"

    # Create directory structure
    info "Creating PhantomStrike directories..."
    mkdir -p "$PHANTOM_DIR"/{reports,evidence,logs,wordlists,browser_evidence}

    # Copy .env.example if no .env exists
    if [ ! -f "$PHANTOM_DIR/.env" ]; then
        if [ -f "$REPO_PATH/.env.example" ]; then
            cp "$REPO_PATH/.env.example" "$PHANTOM_DIR/.env"
            success "Created $PHANTOM_DIR/.env from template"
        else
            # Create minimal .env
            cat > "$PHANTOM_DIR/.env" << 'EOF'
# PhantomStrike API Keys
# Get free keys and add them here for AI features

# Groq (fastest — 14K req/day free): https://console.groq.com
GROQ_API_KEY=

# OpenRouter (100+ models free): https://openrouter.ai
OPENROUTER_API_KEY=

# Google Gemini (1500 req/day free): https://aistudio.google.com
GEMINI_API_KEY=

# Cerebras (1M tokens/day free): https://cloud.cerebras.ai
CEREBRAS_API_KEY=

# Mistral (1B tokens/month free): https://console.mistral.ai
MISTRAL_API_KEY=

# Together AI: https://api.together.ai
TOGETHER_API_KEY=

# HuggingFace: https://huggingface.co/settings/tokens
HUGGINGFACE_API_KEY=

# NVIDIA NIM: https://build.nvidia.com
NVIDIA_API_KEY=

# SambaNova: https://cloud.sambanova.ai
SAMBANOVA_API_KEY=

# ── Optional Settings ──
# PHANTOM_LOG_LEVEL=INFO
# PHANTOM_BACKEND_ENABLED=false
EOF
            success "Created $PHANTOM_DIR/.env"
        fi
    else
        success ".env already exists — keeping your existing API keys"
    fi

    # Copy default config if not present
    if [ ! -f "$PHANTOM_DIR/config.yaml" ] && [ -f "$REPO_PATH/configs/default.yaml" ]; then
        cp "$REPO_PATH/configs/default.yaml" "$PHANTOM_DIR/config.yaml"
        success "Copied default config to $PHANTOM_DIR/config.yaml"
    fi

    success "Configuration ready"
}

# ── Create shell commands ─────────────────────────────────────────────────
setup_commands() {
    step "8/8 — Shell commands"

    # Determine install locations
    LOCAL_BIN="$HOME/.local/bin"
    mkdir -p "$LOCAL_BIN"

    # Create wrapper scripts (more reliable than symlinks for venv)
    PHANTOM_WRAPPER="$LOCAL_BIN/phantom"
    PHANTOM_STRIKE_WRAPPER="$LOCAL_BIN/phantom-strike"

    cat > "$PHANTOM_WRAPPER" << EOF
#!/bin/bash
# PhantomStrike CLI wrapper — auto-activates venv
VENV="$VENV_DIR"
if [ -f "\$VENV/bin/activate" ] && [ -z "\$VIRTUAL_ENV" ]; then
    source "\$VENV/bin/activate"
fi
exec "\$VENV/bin/python" -m phantom "\$@"
EOF

    cat > "$PHANTOM_STRIKE_WRAPPER" << EOF
#!/bin/bash
# PhantomStrike CLI wrapper — auto-activates venv
VENV="$VENV_DIR"
if [ -f "\$VENV/bin/activate" ] && [ -z "\$VIRTUAL_ENV" ]; then
    source "\$VENV/bin/activate"
fi
exec "\$VENV/bin/python" -m phantom "\$@"
EOF

    chmod +x "$PHANTOM_WRAPPER" "$PHANTOM_STRIKE_WRAPPER"
    success "Created: $PHANTOM_WRAPPER"
    success "Created: $PHANTOM_STRIKE_WRAPPER"

    # Add ~/.local/bin to PATH if not already there
    SHELL_RC=""
    if [ -n "${BASH_VERSION:-}" ]; then
        SHELL_RC="$HOME/.bashrc"
    elif [ -n "${ZSH_VERSION:-}" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -f "$HOME/.profile" ]; then
        SHELL_RC="$HOME/.profile"
    fi

    if [ -n "$SHELL_RC" ]; then
        if ! grep -q 'PATH.*\.local/bin' "$SHELL_RC" 2>/dev/null; then
            echo '' >> "$SHELL_RC"
            echo '# PhantomStrike' >> "$SHELL_RC"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
            info "Added ~/.local/bin to PATH in $SHELL_RC"
        fi
    fi

    # Also try /usr/local/bin if we have sudo
    if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
        sudo ln -sf "$PHANTOM_WRAPPER" /usr/local/bin/phantom 2>/dev/null || true
        sudo ln -sf "$PHANTOM_STRIKE_WRAPPER" /usr/local/bin/phantom-strike 2>/dev/null || true
        success "Also linked to /usr/local/bin/ (system-wide)"
    fi

    success "Commands installed"
}

# ── Run tests ─────────────────────────────────────────────────────────────
run_tests() {
    if [ "$INSTALL_DEV" = true ]; then
        echo ""
        info "Running test suite to verify installation..."
        cd "$REPO_PATH"
        python -m pytest tests/ -v --tb=short -q 2>&1 | tail -20 || warn "Some tests failed — check output above"
        cd - > /dev/null
    fi
}

# ── Print final summary ───────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   PhantomStrike v${VERSION} installed successfully! 🔥       ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}  What's installed:${NC}"
    echo -e "  ${GREEN}✓${NC} 11 offensive modules (OSINT, Network, Web, Cloud, C2...)"
    echo -e "  ${GREEN}✓${NC} Multi-provider AI engine (Groq, OpenRouter, Gemini, Cerebras)"
    echo -e "  ${GREEN}✓${NC} Playwright browser engine (JS-rendered XSS, screenshots)"
    echo -e "  ${GREEN}✓${NC} Full-stack web dashboard (FastAPI + WebSocket)"
    echo -e "  ${GREEN}✓${NC} Real exploit engine (SQLi, LFI, SSRF, RCE, file upload)"
    echo -e "  ${GREEN}✓${NC} Polymorphic payload generator (XSS, SQLi, reverse shells)"
    echo -e "  ${GREEN}✓${NC} C2 framework with agent management"
    echo -e "  ${GREEN}✓${NC} HTML/JSON/TXT report generation with MITRE ATT&CK mapping"
    echo ""
    echo -e "${BOLD}  Quick start:${NC}"
    echo ""
    echo -e "  ${YELLOW}Step 1${NC} — Add at least one AI API key (optional but recommended):"
    echo -e "          ${CYAN}nano $PHANTOM_DIR/.env${NC}"
    echo -e "          Get free Groq key: ${CYAN}https://console.groq.com${NC}"
    echo ""
    echo -e "  ${YELLOW}Step 2${NC} — Reload your shell:"
    echo -e "          ${CYAN}source ~/.bashrc${NC}  (or open a new terminal)"
    echo ""
    echo -e "  ${YELLOW}Step 3${NC} — Launch CLI:"
    echo -e "          ${CYAN}phantom${NC}"
    echo -e "          ${CYAN}phantom> scan example.com${NC}"
    echo -e "          ${CYAN}phantom> attack example.com${NC}"
    echo ""
    echo -e "  ${YELLOW}Step 4${NC} — Or launch web dashboard:"
    echo -e "          ${CYAN}phantom serve${NC}"
    echo -e "          Open: ${CYAN}http://localhost:10000${NC}"
    echo ""
    echo -e "${BOLD}  Useful commands:${NC}"
    echo -e "  ${CYAN}phantom serve${NC}                  — Start web dashboard"
    echo -e "  ${CYAN}phantom> scan <target>${NC}         — Quick vulnerability scan"
    echo -e "  ${CYAN}phantom> attack <target>${NC}       — Full 7-phase kill chain"
    echo -e "  ${CYAN}phantom> ai ask <question>${NC}     — Ask AI anything"
    echo -e "  ${CYAN}phantom> stealth xss 20${NC}        — Generate 20 XSS payloads"
    echo -e "  ${CYAN}phantom> c2 generate 10.0.0.1 4444${NC} — Generate C2 agent"
    echo -e "  ${CYAN}phantom> report <target>${NC}       — Generate pentest report"
    echo ""
    echo -e "${BOLD}  Update PhantomStrike anytime:${NC}"
    echo -e "  ${CYAN}curl -sSL https://raw.githubusercontent.com/thecnical/phantom-strike/main/install.sh | bash -- --update${NC}"
    echo ""
    echo -e "${RED}  ⚠  LEGAL: Only use on systems you own or have written authorization to test.${NC}"
    echo ""
    echo -e "  ${BLUE}GitHub:${NC} https://github.com/thecnical/phantom-strike"
    echo -e "  ${BLUE}Issues:${NC} https://github.com/thecnical/phantom-strike/issues"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────
main() {
    detect_os
    check_python
    install_system_deps
    setup_repo
    setup_venv
    install_packages
    install_playwright
    setup_config
    setup_commands
    run_tests
    print_summary
}

main "$@"
