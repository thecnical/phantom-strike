#!/bin/bash
# ═══════════════════════════════════════════════════════════
# PhantomStrike — One-Command Installer for Linux
# Usage: curl -sSL https://raw.githubusercontent.com/phantom-strike/phantom-strike/main/install.sh | bash
# ═══════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}"
echo "  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗"
echo "  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║"
echo "  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║"
echo "  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║"
echo "  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║"
echo "  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝"
echo -e "${CYAN}                    S T R I K E${NC}"
echo -e "${YELLOW}         Installing the world's most powerful offensive framework...${NC}"
echo ""

# Check Python version
echo -e "${CYAN}[1/6] Checking Python version...${NC}"
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
REQUIRED="3.12"

if [ "$(printf '%s\n' "$REQUIRED" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED" ]; then
    echo -e "${RED}[!] Python 3.12+ required. Found: ${PYTHON_VERSION}${NC}"
    echo -e "${YELLOW}    Install: sudo apt install python3.12 python3.12-venv${NC}"
    exit 1
fi
echo -e "${GREEN}[✓] Python ${PYTHON_VERSION} detected${NC}"

# Create virtual environment
echo -e "${CYAN}[2/6] Creating virtual environment...${NC}"
python3 -m venv ~/.phantom-strike/venv
source ~/.phantom-strike/venv/bin/activate
echo -e "${GREEN}[✓] Virtual environment created${NC}"

# Install PhantomStrike
echo -e "${CYAN}[3/6] Installing PhantomStrike...${NC}"
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -e . > /dev/null 2>&1
echo -e "${GREEN}[✓] PhantomStrike installed${NC}"

# Install Playwright browsers
echo -e "${CYAN}[4/6] Installing Playwright browsers...${NC}"
playwright install chromium > /dev/null 2>&1
playwright install-deps > /dev/null 2>&1 || true
echo -e "${GREEN}[✓] Playwright ready${NC}"

# Create config directory
echo -e "${CYAN}[5/6] Setting up configuration...${NC}"
mkdir -p ~/.phantom-strike/{reports,evidence,logs,wordlists}
if [ ! -f ~/.phantom-strike/.env ]; then
    cp .env.example ~/.phantom-strike/.env 2>/dev/null || true
fi
echo -e "${GREEN}[✓] Configuration ready${NC}"

# Create symlink
echo -e "${CYAN}[6/6] Creating command alias...${NC}"
VENV_BIN="$HOME/.phantom-strike/venv/bin"
if [ -d "$HOME/.local/bin" ]; then
    ln -sf "$VENV_BIN/phantom" "$HOME/.local/bin/phantom" 2>/dev/null || true
    ln -sf "$VENV_BIN/phantom-strike" "$HOME/.local/bin/phantom-strike" 2>/dev/null || true
fi
echo -e "${GREEN}[✓] Commands ready${NC}"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  PhantomStrike installed successfully! 🎉${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}  Next steps:${NC}"
echo -e "    1. Add API keys: ${YELLOW}nano ~/.phantom-strike/.env${NC}"
echo -e "    2. Run PhantomStrike: ${YELLOW}phantom-strike${NC}"
echo ""
echo -e "${RED}  ⚠ ONLY use on authorized targets!${NC}"
echo ""
