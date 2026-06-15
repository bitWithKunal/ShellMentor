"""
ShellMentor - utils.py
System utilities: Linux detection, environment scanning, sandbox engine,
dependency management, and general helpers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shellmentor")

# ─────────────────────────── Constants ───────────────────────────

APP_NAME = "ShellMentor"
APP_VERSION = "2.0.0"
APP_TAGLINE = "Professional Linux Command-Line Learning Platform"

WORKSPACE_DIR = Path(__file__).parent / "workspace"
DATA_DIR      = Path(__file__).parent / "data"
THEMES_DIR    = Path(__file__).parent / "themes"

BLOCKED_COMMANDS = frozenset([
    "rm", "rmdir", "dd", "mkfs", "fdisk", "mkswap", "shutdown",
    "reboot", "halt", "poweroff", "init", "telinit",
    "passwd", "chpasswd", "useradd", "userdel", "usermod",
    "chmod", "chown", "chgrp", "sudo", "su", "doas",
    "systemctl", "service", "systemd", "journalctl",
    "iptables", "ip6tables", "nftables", "ufw",
    "mount", "umount", "fsck", "parted", "lvm",
    "wget", "curl", "nc", "netcat", "ncat", "ssh", "scp",
    "python", "python3", "perl", "ruby", "node", "bash",
    "sh", "zsh", "fish", "dash", "csh", "tcsh",
    "eval", "exec", "source",
    "crontab", "at", "batch",
    "kill", "killall", "pkill",
    "export", "env", "printenv",
])

BLOCKED_PATTERNS = [
    r"rm\s+-[^\s]*r",       # rm -r, rm -rf, etc.
    r">\s*/dev/",            # writing to /dev
    r">\s*/etc/",            # overwriting /etc
    r">\s*/sys/",            # kernel sysfs
    r">\s*/proc/",           # proc fs
    r";.*rm\s",              # command chaining with rm
    r"\|\s*sh\b",            # pipe to shell
    r"\|\s*bash\b",          # pipe to bash
    r"mkfs",                 # format filesystem
    r"\.\.\./",              # path traversal
    r"~/",                   # home directory access
    r"/home/",               # home directory
    r"/root/",               # root home
    r"/etc/",                # system config
    r"/usr/",                # system binaries
    r"/var/",                # system var
    r"/sys/",                # sysfs
    r"/proc/",               # procfs
    r"/dev/",                # devices
    r"\$\(",                 # command substitution
    r"`",                    # backtick substitution
]

SAFE_COMMANDS = frozenset([
    "grep", "egrep", "fgrep",
    "sed", "awk", "gawk",
    "cut", "sort", "uniq", "tr", "wc", "head", "tail", "tee",
    "paste", "join", "comm",
    "find", "xargs",
    "cat", "less", "more", "column", "nl", "split",
    "echo", "printf",
    "ls", "pwd", "date", "id",
    "ripgrep", "rg", "fd", "bat", "jq",
    "diff", "cmp",
    "base64", "od", "xxd",
    "iconv", "strings",
])

DEPENDENCY_TOOLS = [
    ("git",       "git"),
    ("grep",      "grep"),
    ("sed",       "sed"),
    ("awk",       "awk"),
    ("gawk",      "gawk"),
    ("rg",        "ripgrep"),
    ("fd",        "fd-find"),
    ("fzf",       "fzf"),
    ("bat",       "bat"),
    ("sqlite3",   "sqlite3"),
    ("tar",       "tar"),
    ("gzip",      "gzip"),
    ("find",      "findutils"),
    ("ls",        "coreutils"),
]

PKG_MANAGERS = {
    "apt":    "sudo apt install -y",
    "apt-get":"sudo apt-get install -y",
    "dnf":    "sudo dnf install -y",
    "yum":    "sudo yum install -y",
    "pacman": "sudo pacman -S --noconfirm",
    "zypper": "sudo zypper install -y",
    "emerge": "sudo emerge",
    "xbps-install": "sudo xbps-install -y",
}

# Package name overrides per distro family
PKG_NAME_MAP = {
    "apt":    {"fd-find": "fd-find", "bat": "bat", "ripgrep": "ripgrep"},
    "dnf":    {"fd-find": "fd",      "bat": "bat", "ripgrep": "ripgrep"},
    "pacman": {"fd-find": "fd",      "bat": "bat", "ripgrep": "ripgrep"},
    "zypper": {"fd-find": "fd",      "bat": "bat", "ripgrep": "ripgrep"},
}


# ─────────────────────────── Data Classes ───────────────────────────

@dataclass
class SystemInfo:
    distro_name:    str = "Unknown"
    distro_version: str = "Unknown"
    distro_id:      str = "unknown"
    kernel:         str = "Unknown"
    desktop_env:    str = "Unknown"
    terminal:       str = "Unknown"
    shell:          str = "Unknown"
    python_version: str = "Unknown"
    pkg_manager:    str = "None"
    tools:          dict[str, bool] = field(default_factory=dict)
    missing_tools:  list[str]       = field(default_factory=list)
    is_linux:       bool = False


@dataclass
class SandboxResult:
    command:    str
    stdout:     str
    stderr:     str
    exit_code:  int
    duration_ms: float
    blocked:    bool = False
    block_reason: str = ""
    timestamp:  str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.blocked

    @property
    def output(self) -> str:
        return self.stdout if self.stdout else self.stderr


# ─────────────────────────── System Detection ───────────────────────────

def detect_system() -> SystemInfo:
    """Perform a full Linux environment scan."""
    info = SystemInfo()

    info.is_linux = platform.system() == "Linux"
    info.python_version = platform.python_version()
    info.kernel = platform.release()
    info.shell = os.environ.get("SHELL", "unknown").split("/")[-1]
    info.terminal = _detect_terminal()
    info.desktop_env = os.environ.get("XDG_CURRENT_DESKTOP",
                        os.environ.get("DESKTOP_SESSION", "Unknown"))

    # Distro detection
    try:
        with open("/etc/os-release") as f:
            os_release = {}
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    os_release[k] = v.strip('"')
        info.distro_name    = os_release.get("NAME", "Unknown Linux")
        info.distro_version = os_release.get("VERSION_ID", "Unknown")
        info.distro_id      = os_release.get("ID", "unknown").lower()
    except FileNotFoundError:
        info.distro_name = "Linux (unknown distro)"

    # Package manager detection
    for mgr in PKG_MANAGERS:
        if shutil.which(mgr):
            info.pkg_manager = mgr
            break

    # Tool availability check
    for binary, _pkg in DEPENDENCY_TOOLS:
        found = shutil.which(binary) is not None
        info.tools[binary] = found
        if not found:
            info.missing_tools.append(binary)

    return info


def _detect_terminal() -> str:
    """Attempt to detect the terminal emulator."""
    for var in ("TERM_PROGRAM", "VTE_VERSION", "TERMINAL", "COLORTERM"):
        val = os.environ.get(var)
        if val:
            return val
    term = os.environ.get("TERM", "unknown")
    if "xterm" in term:
        return "xterm-compatible"
    return term


def get_install_command(system_info: SystemInfo, packages: list[str]) -> str:
    """Generate distro-appropriate install command for missing packages."""
    mgr = system_info.pkg_manager
    if not mgr:
        return "# No supported package manager detected"

    base_cmd = PKG_MANAGERS.get(mgr, f"sudo {mgr} install")
    name_map = PKG_NAME_MAP.get(mgr, {})
    pkg_names = [name_map.get(p, p) for p in packages]

    return f"{base_cmd} {' '.join(pkg_names)}"


# ─────────────────────────── Sandbox Engine ───────────────────────────

class SandboxEngine:
    """Isolated command execution environment."""

    def __init__(self, workspace: Path = WORKSPACE_DIR):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.history: list[SandboxResult] = []

    def validate(self, command: str) -> tuple[bool, str]:
        """Validate a command before execution. Returns (safe, reason)."""
        stripped = command.strip()
        if not stripped:
            return False, "Empty command"

        # Extract the base command
        try:
            tokens = shlex.split(stripped)
        except ValueError as e:
            return False, f"Parse error: {e}"

        base = tokens[0].lower() if tokens else ""
        base = os.path.basename(base)

        if base in BLOCKED_COMMANDS:
            return False, f"'{base}' is blocked for safety. Use safe alternatives."

        # Check blocked patterns
        for pat in BLOCKED_PATTERNS:
            if re.search(pat, stripped, re.IGNORECASE):
                return False, f"Blocked pattern detected: path traversal or dangerous redirection."

        # Check for output redirection to non-workspace paths
        if ">" in stripped:
            redirect_match = re.search(r">\s*([^\s>|]+)", stripped)
            if redirect_match:
                redir_path = redirect_match.group(1)
                if not redir_path.startswith(("./", "/tmp/")) and "/" in redir_path:
                    return False, "Output redirection outside workspace is blocked."

        return True, ""

    def run(self, command: str, timeout: int = 10) -> SandboxResult:
        """Execute a command in the sandbox workspace."""
        safe, reason = self.validate(command)
        if not safe:
            result = SandboxResult(
                command=command, stdout="", stderr=reason,
                exit_code=1, duration_ms=0, blocked=True, block_reason=reason
            )
            self.history.append(result)
            return result

        start = time.monotonic()
        proc = None
        try:
            # start_new_session=True creates a new process group so that on
            # timeout we can kill the whole group (shell + children), preventing
            # zombie processes and terminal hangs.
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "HOME": str(self.workspace)},
                start_new_session=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Kill the entire process group cleanly
                import signal as _sig
                try:
                    os.killpg(os.getpgid(proc.pid), _sig.SIGKILL)
                except (ProcessLookupError, OSError):
                    proc.kill()
                proc.wait()
                duration = timeout * 1000
                result = SandboxResult(
                    command=command, stdout="",
                    stderr=f"Command timed out after {timeout}s — killed.",
                    exit_code=124, duration_ms=duration,
                    blocked=True, block_reason="timeout",
                )
                self.history.append(result)
                return result

            duration = (time.monotonic() - start) * 1000
            # Truncate very large outputs to avoid UI freeze
            if len(stdout) > 50_000:
                stdout = stdout[:50_000] + "\n[... output truncated at 50 KB ...]"
            result = SandboxResult(
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode,
                duration_ms=duration,
            )
        except Exception as e:
            if proc is not None:
                try:
                    proc.kill()
                    proc.wait()
                except Exception:
                    pass
            duration = (time.monotonic() - start) * 1000
            result = SandboxResult(
                command=command, stdout="",
                stderr=str(e), exit_code=1, duration_ms=duration,
            )

        self.history.append(result)
        return result

    def clear_history(self) -> None:
        self.history.clear()

    def get_history_commands(self) -> list[str]:
        return [r.command for r in self.history]


# ─────────────────────────── File Utilities ───────────────────────────

def load_json(path: Path) -> Any:
    """Load JSON file with error handling."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"JSON file not found: {path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {path}: {e}")
        return {}


def save_json(path: Path, data: Any) -> bool:
    """Save data to JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON {path}: {e}")
        return False


def load_yaml(path: Path) -> Any:
    """Load YAML file."""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"YAML load error {path}: {e}")
        return {}


# ─────────────────────────── Text Utilities ───────────────────────────

def truncate(text: str, max_len: int = 60, suffix: str = "…") -> str:
    """Truncate text to max_len characters."""
    return text if len(text) <= max_len else text[:max_len - len(suffix)] + suffix


def format_xp(xp: int) -> str:
    """Format XP with thousands separator."""
    return f"{xp:,} XP"


def format_duration(seconds: float) -> str:
    """Format duration for display."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def difficulty_color(difficulty: str) -> str:
    """Return markup color string for difficulty level."""
    colors = {
        "beginner":     "green",
        "intermediate": "yellow",
        "advanced":     "orange1",
        "expert":       "red",
        "master":       "magenta",
    }
    return colors.get(difficulty.lower(), "white")


def difficulty_icon(difficulty: str) -> str:
    icons = {
        "beginner":     "🟢",
        "intermediate": "🟡",
        "advanced":     "🟠",
        "expert":       "🔴",
        "master":       "💀",
    }
    return icons.get(difficulty.lower(), "⚪")


def rarity_color(rarity: str) -> str:
    colors = {
        "common":    "grey70",
        "uncommon":  "green",
        "rare":      "dodger_blue1",
        "epic":      "medium_purple1",
        "legendary": "gold1",
    }
    return colors.get(rarity.lower(), "white")


def generate_portfolio_markdown(user_data: dict, achievements: list, progress: dict) -> str:
    """Generate a full markdown portfolio report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    name = user_data.get("username", "ShellMentor User")
    rank = user_data.get("rank_title", "Terminal Novice")
    xp   = user_data.get("xp", 0)
    level = user_data.get("level", 1)
    streak = user_data.get("streak", 0)
    lessons = progress.get("lessons_completed", 0)
    challenges = progress.get("challenges_solved", 0)
    missions = progress.get("missions_completed", 0)
    accuracy = progress.get("accuracy", 0)

    ach_lines = "\n".join(
        f"- **{a['icon']} {a['title']}** — {a['description']} *(+{a['xp_reward']} XP)*"
        for a in achievements
    )

    tracks_completed = progress.get("tracks_completed", [])
    track_lines = "\n".join(f"- ✅ {t}" for t in tracks_completed) if tracks_completed else "- No tracks completed yet"

    return f"""# 🐧 ShellMentor Portfolio — {name}

> *{APP_TAGLINE}*

Generated: `{now}`

---

## 📊 Learning Stats

| Metric | Value |
|--------|-------|
| **Rank** | {rank} |
| **Level** | {level} |
| **Total XP** | {xp:,} XP |
| **Learning Streak** | {streak} days |
| **Lessons Completed** | {lessons} |
| **Challenges Solved** | {challenges} |
| **Missions Completed** | {missions} |
| **Quiz Accuracy** | {accuracy:.1f}% |

---

## 🏆 Achievements ({len(achievements)} earned)

{ach_lines if ach_lines else "No achievements yet — keep learning!"}

---

## 🎯 Tracks Completed

{track_lines}

---

## 🛠️ Skills Demonstrated

This portfolio was generated by [ShellMentor v{APP_VERSION}](https://github.com/shellmentor).

Mastery demonstrated across:
- `grep` / `egrep` — Pattern matching and log filtering
- `sed` — Stream editing and text transformation  
- `awk` — Data extraction and report generation
- `cut`, `sort`, `uniq` — Data pipeline fundamentals
- `tr`, `wc`, `head`, `tail` — Text processing toolkit
- `find`, `xargs` — Filesystem querying
- Shell pipelines — Command composition and data flow
- Regular expressions — Pattern construction and analysis
- Log analysis — Apache, Nginx, syslog investigation
- VLSI text processing — EDA report parsing and analysis

---

*Generated by ShellMentor {APP_VERSION} — The Professional Linux Learning Platform*
"""


def hash_command(command: str) -> str:
    """Generate a short hash for a command string."""
    return hashlib.md5(command.encode()).hexdigest()[:8]


def validate_challenge_output(user_output: str, expected_pattern: str,
                               validation_type: str, expected_lines: int = 0) -> tuple[bool, str]:
    """Validate challenge output against expected criteria."""
    output = user_output.strip()
    if not output:
        return False, "No output produced. Make sure your command runs successfully."

    if validation_type == "line_count":
        actual = len(output.splitlines())
        if actual == expected_lines:
            return True, f"✓ Correct! Got exactly {expected_lines} lines."
        else:
            return False, f"Expected {expected_lines} lines, got {actual}."

    if validation_type == "pattern_match":
        lines = output.splitlines()
        if len(lines) > 0 and all(line.strip() for line in lines):
            return True, "✓ Output looks correct!"
        return False, "Output doesn't match expected format."

    if validation_type == "format_check":
        return True, "✓ Output accepted!"

    return True, "✓ Output accepted!"
