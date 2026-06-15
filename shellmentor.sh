#!/usr/bin/env bash
# ================================================================
#  ShellMentor v2.0.0  —  Professional Linux Learning Platform
#  Author: Kunal Kumar
#  LinkedIn: https://linkedin.com/in/kunal-kumar
#  GitHub: https://github.com/shellmentor/shellmentor
#  Usage: ./shellmentor.sh [--dev] [--install-only] [--help]
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="${PYTHON:-python3}"
SHELLMENTOR_CMD="$SCRIPT_DIR/shellmentor.sh"

# Version information
VERSION="2.0.0"
AUTHOR="Kunal Saraswat"
AUTHOR_EMAIL="kunalsaraswat30@gmail.com"
LINKEDIN_URL="https://www.linkedin.com/in/kunalsaraswat/"
GITHUB_URL="https://github.com/shellmentor/shellmentor"

# ── Terminal colours ──────────────────────────────────────────
R='\033[0;31m'   # red
G='\033[0;32m'   # green
Y='\033[1;33m'   # yellow
C='\033[0;36m'   # cyan
B='\033[0;34m'   # blue
W='\033[1;37m'   # bold white
D='\033[2m'      # dim
NC='\033[0m'     # reset
BOLD='\033[1m'

# ── Banner ────────────────────────────────────────────────────
banner() {
  clear
  echo -e "${C}${BOLD}"
  echo "   ███████╗██╗  ██╗███████╗██╗     ██╗     ███╗   ███╗███████╗███╗   ██╗████████╗ ██████╗ ██████╗ "
  echo "   ██╔════╝██║  ██║██╔════╝██║     ██║     ████╗ ████║██╔════╝████╗  ██║╚══██╔══╝██╔═══██╗██╔══██╗"
  echo "   ███████╗███████║█████╗  ██║     ██║     ██╔████╔██║█████╗  ██╔██╗ ██║   ██║   ██║   ██║██████╔╝"
  echo "   ╚════██║██╔══██║██╔══╝  ██║     ██║     ██║╚██╔╝██║██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██╔══██╗"
  echo "   ███████║██║  ██║███████╗███████╗███████╗██║ ╚═╝ ██║███████╗██║ ╚████║   ██║   ╚██████╔╝██║  ██║"
  echo "   ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝"
  echo -e "${NC}"
  echo -e "   ${D}Professional Linux Command-Line Learning Platform${NC}"
  echo -e "   ${D}Version: ${VERSION}${NC}"
  echo -e "   ${D}────────────────────────────────────────────────${NC}"
  echo ""
  echo -e "   ${W}Author:${NC}  ${C}${AUTHOR}${NC}"
  echo -e "   ${W}LinkedIn:${NC} ${C}${LINKEDIN_URL}${NC}"
  echo -e "   ${W}GitHub:${NC}  ${C}${GITHUB_URL}${NC}"
  echo ""
  echo -e "   ${D}Type './shellmentor.sh --help' for usage options${NC}"
  echo ""
}

# ── Logging helpers ───────────────────────────────────────────
step()    { echo -e "  ${C}▶${NC}  $*"; }
ok()      { echo -e "  ${G}✔${NC}  $*"; }
warn()    { echo -e "  ${Y}⚠${NC}  $*"; }
error()   { echo -e "  ${R}✘${NC}  $*"; }
fail()    { echo -e "  ${R}✘${NC}  $*"; exit 1; }
info()    { echo -e "  ${B}ℹ${NC}  $*"; }
section() { echo -e "\n  ${C}${BOLD}━━━ $* ━━━${NC}"; }

# ── System checks ─────────────────────────────────────────────
check_linux() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    warn "Non-Linux system detected — some features may behave differently."
    return 1
  else
    ok "Linux kernel: $(uname -r)"
    return 0
  fi
}

check_python() {
  if ! command -v "$PYTHON" &>/dev/null; then
    error "Python 3 not found"
    echo -e "  ${D}Install it with: sudo apt install python3 python3-venv${NC}"
    fail "Python 3 is required to run ShellMentor"
  fi
  
  local ver major minor
  ver=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  major=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
  minor=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
  
  if [[ "$major" -lt 3 ]] || [[ "$major" -eq 3 && "$minor" -lt 10 ]]; then
    error "Python $ver detected"
    fail "Python 3.10 or higher is required. Found: $ver"
  fi
  ok "Python $ver (OK)"
}

# ── Dependency gate ───────────────────────────────────────────
check_python_deps() {
  local pip="$VENV_DIR/bin/pip"
  local need_install=0

  if [[ ! -f "$VENV_DIR/bin/python" ]]; then
    need_install=1
  else
    if ! "$VENV_DIR/bin/python" -c "import textual, rich, yaml, platformdirs" &>/dev/null 2>&1; then
      need_install=1
    fi
  fi

  if [[ "$need_install" -eq 1 ]]; then
    section "Installing Python Dependencies"
    step "Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR" || fail "Failed to create virtual environment"
    ok "Virtual environment created"

    step "Upgrading pip..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q 2>/dev/null || true
    ok "pip upgraded"

    step "Installing required packages..."
    if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
      "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
    else
      "$VENV_DIR/bin/pip" install textual rich pyyaml platformdirs -q
    fi
    
    if [[ $? -eq 0 ]]; then
      ok "All packages installed successfully"
    else
      fail "Failed to install required packages. Check your internet connection."
    fi
  fi
}

# ── Optional system tools check ───────────────────────────────
check_system_tools() {
  local tools=("grep" "sed" "awk" "sort" "uniq" "cut" "wc" "head" "tail" "tr" "find" "xargs")
  local optional=("rg" "fd" "fzf" "bat")
  local missing_optional=()

  section "System Tool Check"

  # Core tools
  local missing_core=()
  for t in "${tools[@]}"; do
    if ! command -v "$t" &>/dev/null; then
      missing_core+=("$t")
    fi
  done
  
  if [[ ${#missing_core[@]} -eq 0 ]]; then
    ok "All core Unix tools present"
  else
    warn "Missing core tools: ${missing_core[*]}"
  fi

  # Optional tools
  for t in "${optional[@]}"; do
    if command -v "$t" &>/dev/null; then
      ok "$t available (enhanced features)"
    else
      missing_optional+=("$t")
    fi
  done

  if [[ ${#missing_optional[@]} -gt 0 ]]; then
    echo ""
    warn "Optional tools not found: ${missing_optional[*]}"
    info "These tools unlock additional features"
    
    local install_cmd=""
    if command -v apt &>/dev/null; then
      install_cmd="sudo apt install -y ${missing_optional[*]}"
    elif command -v dnf &>/dev/null; then
      install_cmd="sudo dnf install -y ${missing_optional[*]}"
    elif command -v pacman &>/dev/null; then
      install_cmd="sudo pacman -S ${missing_optional[*]}"
    else
      install_cmd=""
    fi
    
    if [[ -n "$install_cmd" ]]; then
      echo -e "  ${D}Install command:${NC} ${C}$install_cmd${NC}"
      echo ""
      read -rp "  Install optional tools now? (y/N): " choice
      if [[ "${choice,,}" == "y" ]] || [[ "${choice,,}" == "yes" ]]; then
        section "Installing Optional Tools"
        # Run apt install without pipefail causing exit
        set +e
        eval "$install_cmd" 2>&1 | head -20
        local exit_code=$?
        set -e
        if [[ $exit_code -eq 0 ]]; then
          ok "Optional tools installed successfully"
        else
          warn "Some tools failed to install — continuing without them"
        fi
      fi
    else
      info "Please install optional tools manually using your package manager"
    fi
  fi
  echo ""
}

# ── Shell integration ─────────────────────────────────────────
install_to_shellrc() {
  local shell_rc=""
  local current_shell=$(basename "$SHELL")
  
  case "$current_shell" in
    bash)
      shell_rc="$HOME/.bashrc"
      ;;
    zsh)
      shell_rc="$HOME/.zshrc"
      ;;
    fish)
      shell_rc="$HOME/.config/fish/config.fish"
      ;;
    *)
      shell_rc="$HOME/.bashrc"
      ;;
  esac
  
  local marker="# ShellMentor - Professional Linux Learning Platform"
  local alias_line="alias shellmentor='bash \"$SHELLMENTOR_CMD\"'"
  
  if grep -q "ShellMentor" "$shell_rc" 2>/dev/null; then
    return 0
  fi

  echo "" >> "$shell_rc"
  echo "$marker" >> "$shell_rc"
  echo "$alias_line" >> "$shell_rc"
  echo "export PATH=\"\$PATH:$SCRIPT_DIR\"" >> "$shell_rc"

  ok "Added 'shellmentor' alias to $shell_rc"
  info "Run 'source $shell_rc' or open a new terminal to use it"
}

# ── Launch ────────────────────────────────────────────────────
launch() {
  section "Launching ShellMentor"
  ok "Starting ShellMentor ....Learn well"
  echo ""
  cd "$SCRIPT_DIR"
  exec "$VENV_DIR/bin/python" -u main.py "$@"
}

# ── Version info ──────────────────────────────────────────────
show_version() {
  echo -e "  ${C}ShellMentor${NC} version ${W}${VERSION}${NC}"
  echo -e "  ${D}Author:${NC}  ${AUTHOR}"
  echo -e "  ${D}LinkedIn:${NC} ${LINKEDIN_URL}"
  echo -e "  ${D}GitHub:${NC}  ${GITHUB_URL}"
  echo ""
  echo -e "  ${D}Released under MIT License${NC}"
}

# ── Help ──────────────────────────────────────────────────────
show_help() {
  echo -e "  ${W}Usage:${NC} ./shellmentor.sh [OPTIONS]"
  echo ""
  echo -e "  ${W}Options:${NC}"
  echo -e "    ${C}(none)${NC}           Full setup + launch (recommended)"
  echo -e "    ${C}--install-only${NC}   Install dependencies and setup shell integration"
  echo -e "    ${C}--update${NC}         Update Python packages to latest versions"
  echo -e "    ${C}--dev${NC}            Launch with system Python (skip virtual environment)"
  echo -e "    ${C}--version${NC}        Show version information"
  echo -e "    ${C}--help${NC}           Display this help message"
  echo ""
  echo -e "  ${W}Examples:${NC}"
  echo -e "    ${D}First time:${NC}  ${C}./shellmentor.sh${NC}"
  echo -e "    ${D}Quick:${NC}       ${C}./shellmentor.sh --dev${NC}"
  echo -e "    ${D}Update:${NC}      ${C}./shellmentor.sh --update${NC}"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────
main() {
  banner

  case "${1:-}" in
    --help|-h)
      show_help
      exit 0
      ;;
    --version|-v)
      show_version
      exit 0
      ;;
    --install-only|-i)
      section "Installation Mode"
      check_linux
      check_python
      check_python_deps
      check_system_tools
      install_to_shellrc
      echo ""
      ok "ShellMentor installed successfully"
      info "Run 'shellmentor' to start learning"
      echo ""
      exit 0
      ;;
    --update|-u)
      section "Update Mode"
      if [[ -d "$VENV_DIR" ]]; then
        step "Updating Python packages..."
        set +e
        "$VENV_DIR/bin/pip" install --upgrade textual rich pyyaml platformdirs -q
        set -e
        ok "All packages updated"
      else
        warn "Virtual environment not found. Running full installation..."
        check_python_deps
      fi
      launch "${@:2}"
      ;;
    --dev|-d)
      section "Developer Mode"
      check_linux
      check_python
      cd "$SCRIPT_DIR"
      exec "$PYTHON" -u main.py "${@:2}"
      ;;
    *)
      section "System Check"
      check_linux
      check_python
      check_python_deps
      check_system_tools
      install_to_shellrc
      launch "$@"
      ;;
  esac
}

# Trap Ctrl+C for clean exit
trap 'echo -e "\n  ${Y}⚠${NC}  Interrupted by user"; exit 130' INT

main "$@"
