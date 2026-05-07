#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  PhantomStrike — One-Command Installer v3.0
#  Supports: Ubuntu 20.04+, Debian 11+, Kali Linux, Parrot OS, Arch, Fedora, macOS
#
#  Usage (fresh install):
#    git clone https://github.com/thecnical/phantom-strike.git
#    cd phantom-strike && bash install.sh
#
#  Usage (curl one-liner):
#    curl -sSL https://raw.githubusercontent.com/thecnical/phantom-strike/main/install.sh | bash
#
#  Options:
#    --dev        Install dev/test dependencies (pytest, ruff, mypy, hypothesis)
#    --v3         Install optional v3.0 extras (ldap3, docker, r2pipe, networkx)
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
INSTALL_V3=false
SKIP_BROWSER=false
NO_VENV=false
UPDATE_MODE=false

for arg in "$@"; do
    case $arg in
        --dev)        INSTALL_DEV=true ;;
        --v3)         INSTALL_V3=true ;;
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
VERSION="3.0.0-alpha"

# ── Banner ────────────────────────────────────────────────────────────────
echo -e "${RED}"
echo "  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗"
echo "  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║"
echo "  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║"
echo "  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║"
echo "  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║"
echo "  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝"
echo -e "${CYAN}                    S T R I K E  v${VERSION}${NC}"
echo -e "${YELLOW}         AI-Powered Autonomous Offensive Security Framework${NC}"
echo -e "${YELLOW}         \"See Everything. Strike Anywhere. Leave Nothing.\"${NC}"
echo ""

if [ "$UPDATE_MODE" = true ]; then
    echo -e "${CYAN}  Mode: UPDATE existing installation${NC}"
elif [ "$INSTALL_V3" = true ]; then
    echo -e "${CYAN}  Mode: FRESH install + v3.0 optional components${NC}"
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
    step "1/9 — Python version check"

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
    step "2/9 — System dependencies"

    case "$OS" in
        debian)
            info "Installing system packages (apt)..."
            sudo apt-get update -qq 2>/dev/null || true
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

            if [ -n "${PYTHON_BIN:-}" ]; then
                local pyver
                pyver=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "3")
                sudo apt-get install -y "python${pyver}-venv" 2>/dev/null || true
            fi

            # v3.0: optional system tools
            if [ "$INSTALL_V3" = true ]; then
                info "Installing v3.0 optional system tools..."
                sudo apt-get install -y \
                    exploitdb \
                    radare2 \
                    binutils \
                    2>/dev/null || warn "Some v3.0 system tools unavailable — modules will degrade gracefully"
            fi
            ;;
        arch)
            info "Installing system packages (pacman)..."
            sudo pacman -Sy --noconfirm \
                git curl wget base-devel openssl libffi \
                nmap libpcap 2>/dev/null || warn "Some packages failed — continuing"
            if [ "$INSTALL_V3" = true ]; then
                sudo pacman -Sy --noconfirm radare2 binutils 2>/dev/null || true
            fi
            ;;
        fedora)
            info "Installing system packages (dnf)..."
            sudo dnf install -y \
                git curl wget gcc openssl-devel libffi-devel \
                nmap libpcap-devel 2>/dev/null || warn "Some packages failed — continuing"
            if [ "$INSTALL_V3" = true ]; then
                sudo dnf install -y radare2 binutils 2>/dev/null || true
            fi
            ;;
        macos)
            if command -v brew &>/dev/null; then
                info "Installing system packages (brew)..."
                brew install git curl nmap libpcap 2>/dev/null || warn "Some brew packages failed"
                if [ "$INSTALL_V3" = true ]; then
                    brew install radare2 binutils 2>/dev/null || true
                fi
            fi
            ;;
    esac
    success "System dependencies ready"
}

# ── Clone or update repo ──────────────────────────────────────────────────
setup_repo() {
    step "3/9 — Repository"

    if [ -f "pyproject.toml" ] && grep -q "phantom-strike" pyproject.toml 2>/dev/null; then
        REPO_PATH="$(pwd)"
        success "Running from local clone: $REPO_PATH"
        return
    fi

    if [ -d "phantom-strike" ] && [ -f "phantom-strike/pyproject.toml" ]; then
        REPO_PATH="$(pwd)/phantom-strike"
        success "Found local clone at: $REPO_PATH"
        return
    fi

    REPO_PATH="$PHANTOM_DIR/src"
    if [ -d "$REPO_PATH" ] && [ -f "$REPO_PATH/pyproject.toml" ]; then
        if [ "$UPDATE_MODE" = true ]; then
            info "Pulling latest changes..."
            git -C "$REPO_PATH" pull --rebase --autostash 2>/dev/null || \
                warn "Git pull failed — using existing code"
            success "Repository updated to $(git -C "$REPO_PATH" describe --tags --always 2>/dev/null || echo 'latest')"
        else
            success "Using existing clone at: $REPO_PATH"
        fi
        return
    fi

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
    step "4/9 — Virtual environment"

    if [ "$NO_VENV" = true ]; then
        warn "--no-venv flag set. Installing into current Python environment."
        VENV_BIN="$(dirname $(command -v $PYTHON_BIN))"
        return
    fi

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

    # shellcheck disable=SC1090
    source "$VENV_BIN/activate"
    success "Virtual environment activated (Python $(python --version 2>&1 | cut -d' ' -f2))"
}

# ── Install Python packages ───────────────────────────────────────────────
install_packages() {
    step "5/9 — Python packages"

    if [ -z "${VIRTUAL_ENV:-}" ] && [ "$NO_VENV" = false ]; then
        warn "Not inside a virtual environment. Activating..."
        # shellcheck disable=SC1090
        source "$VENV_BIN/activate" || error "Cannot activate venv at $VENV_BIN"
    fi

    if [ -z "${REPO_PATH:-}" ] || [ ! -f "${REPO_PATH}/pyproject.toml" ]; then
        error "Cannot find pyproject.toml in '${REPO_PATH:-<unset>}'. Run install.sh from inside the phantom-strike folder."
    fi

    info "Upgrading pip, setuptools, wheel..."
    pip install --upgrade pip setuptools wheel --quiet

    # Build extras string
    INSTALL_EXTRAS="api"
    if [ "$INSTALL_DEV" = true ] && [ "$INSTALL_V3" = true ]; then
        INSTALL_EXTRAS="api,dev,v3"
        info "Installing with dev + v3.0 extras..."
    elif [ "$INSTALL_DEV" = true ]; then
        INSTALL_EXTRAS="api,dev"
        info "Installing with dev extras (pytest, ruff, mypy, hypothesis)..."
    elif [ "$INSTALL_V3" = true ]; then
        INSTALL_EXTRAS="api,v3"
        info "Installing with v3.0 extras (ldap3, docker, r2pipe, networkx)..."
    fi

    info "Installing PhantomStrike from: ${REPO_PATH}"
    info "This may take 2-5 minutes on first install..."

    (
        cd "${REPO_PATH}" || error "Cannot cd into ${REPO_PATH}"
        pip install -e ".[${INSTALL_EXTRAS}]" \
            --no-warn-script-location \
            2>&1 | grep -E "(Successfully|ERROR|error|WARNING|Collecting|Installing)" || true
    )

    # v3.0 optional Python packages (graceful — don't fail if unavailable)
    if [ "$INSTALL_V3" = true ]; then
        info "Installing v3.0 optional Python packages..."
        V3_PACKAGES=(
            "ldap3>=2.9.0"
            "docker>=7.0.0"
            "r2pipe>=1.8.0"
            "ROPgadget"
            "pypykatz"
            "bloodhound"
            "networkx>=3.0"
        )
        for pkg in "${V3_PACKAGES[@]}"; do
            pip install "$pkg" --quiet 2>/dev/null && \
                success "  Installed: $pkg" || \
                warn "  Optional package unavailable: $pkg (module will degrade gracefully)"
        done
    fi

    # Verify key packages installed
    REQUIRED_PACKAGES=(
        "rich" "fastapi" "uvicorn" "aiohttp" "httpx"
        "pydantic" "pydantic_settings" "aiosqlite"
        "beautifulsoup4" "dnspython" "playwright"
        "yaml" "hypothesis"
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
    step "6/9 — Playwright browser engine"

    if [ "$SKIP_BROWSER" = true ]; then
        warn "--no-browser flag set. Skipping Playwright browser download."
        warn "Browser-based XSS verification will be unavailable."
        warn "Install later with: playwright install chromium"
        return
    fi

    info "Installing Chromium browser for Playwright..."

    if playwright install chromium 2>/dev/null; then
        success "Chromium browser installed"
    else
        warn "Playwright browser install failed. Trying with system deps..."
        playwright install chromium --with-deps 2>/dev/null || \
            warn "Browser install failed. Run 'playwright install chromium' manually."
    fi

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        playwright install-deps chromium 2>/dev/null || true
    fi

    success "Playwright ready"
}

# ── Setup config and directories ──────────────────────────────────────────
setup_config() {
    step "7/9 — Configuration"

    info "Creating PhantomStrike directories..."
    mkdir -p "$PHANTOM_DIR"/{reports,evidence,logs,wordlists,browser_evidence,oplans,implants}

    if [ ! -f "$PHANTOM_DIR/.env" ]; then
        if [ -f "$REPO_PATH/.env.example" ]; then
            cp "$REPO_PATH/.env.example" "$PHANTOM_DIR/.env"
            success "Created $PHANTOM_DIR/.env from template"
        else
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

    if [ ! -f "$PHANTOM_DIR/config.yaml" ] && [ -f "$REPO_PATH/configs/default.yaml" ]; then
        cp "$REPO_PATH/configs/default.yaml" "$PHANTOM_DIR/config.yaml"
        success "Copied default config to $PHANTOM_DIR/config.yaml"
    fi

    success "Configuration ready"
}

# ── Create shell commands ─────────────────────────────────────────────────
setup_commands() {
    step "8/9 — Shell commands"

    LOCAL_BIN="$HOME/.local/bin"
    mkdir -p "$LOCAL_BIN"

    PHANTOM_WRAPPER="$LOCAL_BIN/phantom"
    PHANTOM_STRIKE_WRAPPER="$LOCAL_BIN/phantom-strike"

    cat > "$PHANTOM_WRAPPER" << EOF
#!/bin/bash
# PhantomStrike CLI wrapper — auto-activates venv on every run
VENV="$VENV_DIR"
if [ -f "\$VENV/bin/activate" ] && [ -z "\$VIRTUAL_ENV" ]; then
    source "\$VENV/bin/activate"
fi
exec "\$VENV/bin/python" -m phantom "\$@"
EOF

    cat > "$PHANTOM_STRIKE_WRAPPER" << EOF
#!/bin/bash
# PhantomStrike CLI wrapper — auto-activates venv on every run
VENV="$VENV_DIR"
if [ -f "\$VENV/bin/activate" ] && [ -z "\$VIRTUAL_ENV" ]; then
    source "\$VENV/bin/activate"
fi
exec "\$VENV/bin/python" -m phantom "\$@"
EOF

    chmod +x "$PHANTOM_WRAPPER" "$PHANTOM_STRIKE_WRAPPER"
    success "Created: $PHANTOM_WRAPPER"

    for SHELL_RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$SHELL_RC" ]; then
            if ! grep -q 'phantom-strike\|\.local/bin' "$SHELL_RC" 2>/dev/null; then
                {
                    echo ''
                    echo '# PhantomStrike'
                    echo 'export PATH="$HOME/.local/bin:$PATH"'
                } >> "$SHELL_RC"
                info "Added ~/.local/bin to PATH in $SHELL_RC"
            fi
        fi
    done

    if [ "$(id -u)" = "0" ]; then
        cp "$PHANTOM_WRAPPER" /usr/local/bin/phantom
        cp "$PHANTOM_STRIKE_WRAPPER" /usr/local/bin/phantom-strike
        chmod +x /usr/local/bin/phantom /usr/local/bin/phantom-strike
        success "Installed system-wide: /usr/local/bin/phantom"
    elif command -v sudo &>/dev/null; then
        sudo cp "$PHANTOM_WRAPPER" /usr/local/bin/phantom 2>/dev/null && \
        sudo cp "$PHANTOM_STRIKE_WRAPPER" /usr/local/bin/phantom-strike 2>/dev/null && \
        sudo chmod +x /usr/local/bin/phantom /usr/local/bin/phantom-strike 2>/dev/null && \
        success "Installed system-wide: /usr/local/bin/phantom" || \
        warn "Could not install to /usr/local/bin — use ~/.local/bin/phantom"
    fi

    export PATH="$LOCAL_BIN:$PATH"
    success "Commands installed — 'phantom' is ready to use"
}

# ── Run tests ─────────────────────────────────────────────────────────────
run_tests() {
    step "9/9 — Verification"

    if [ "$INSTALL_DEV" = true ]; then
        info "Running test suite to verify installation..."
        cd "$REPO_PATH"
        # Run original 28 tests first (fast, no optional deps needed)
        python -m pytest tests/test_core.py -v --tb=short -q 2>&1 | tail -5 || \
            warn "Core tests failed — check output above"
        cd - > /dev/null
    else
        info "Verifying core imports..."
        python -c "
from phantom.core.enhanced_engine import EnhancedPhantomEngine
from phantom.core.roe import RoEConfig, RoEMiddleware
from phantom.db.knowledge_graph import KnowledgeGraph
from phantom.core.opplan import OPPLAN
from phantom.agents.orchestrator import PhantomOrchestrator
from phantom.skills import SkillLibrary
print('All v3.0 core imports OK')
" 2>/dev/null && success "Core imports verified" || warn "Some imports failed — check dependencies"
    fi
}

# ── Print final summary ───────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   PhantomStrike v${VERSION} installed successfully! 🔥         ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}${GREEN}  ✓ phantom command installed at: /usr/local/bin/phantom${NC}"
    echo -e "${BOLD}${GREEN}  ✓ Works from ANY directory, after ANY restart${NC}"
    echo ""
    echo -e "${BOLD}  Run RIGHT NOW (no restart needed):${NC}"
    echo ""
    echo -e "  ${CYAN}phantom${NC}                        — Start interactive CLI"
    echo -e "  ${CYAN}phantom serve${NC}                  — Start web dashboard"
    echo ""
    echo -e "${BOLD}  v2.0 commands (unchanged):${NC}"
    echo -e "  ${CYAN}scan example.com${NC}               — Vulnerability scan"
    echo -e "  ${CYAN}attack example.com${NC}             — Full 7-phase kill chain"
    echo -e "  ${CYAN}ai ask what is XSS${NC}             — Ask AI anything"
    echo -e "  ${CYAN}ai chat${NC}                        — Persistent AI chat"
    echo ""
    echo -e "${BOLD}  New v3.0 commands:${NC}"
    echo -e "  ${CYAN}autonomous example.com${NC}         — Fully autonomous AI attack 🤖"
    echo -e "  ${CYAN}graph${NC}                          — Knowledge Graph visualization"
    echo -e "  ${CYAN}agents${NC}                         — Show 13 specialist agents"
    echo -e "  ${CYAN}opplan list${NC}                    — Show OPPLAN objectives"
    echo -e "  ${CYAN}roe violations${NC}                 — Show RoE violation log"
    echo -e "  ${CYAN}skills list${NC}                    — List offensive skills"
    echo -e "  ${CYAN}sandbox status${NC}                 — Docker sandbox status"
    echo ""
    echo -e "${BOLD}  Update anytime:${NC}"
    echo -e "  ${CYAN}cd $REPO_PATH && git pull && bash install.sh --update${NC}"
    echo ""

    if [ "$INSTALL_V3" = false ]; then
        echo -e "${YELLOW}  Tip: For full v3.0 capabilities (AD attacks, Docker sandbox, binary analysis):${NC}"
        echo -e "  ${CYAN}bash install.sh --v3${NC}"
        echo ""
    fi

    echo -e "${RED}  ⚠  LEGAL: Only use on systems you own or have written authorization to test.${NC}"
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
