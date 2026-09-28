"""
ShellMentor - playground.py
Interactive command lab: answer recording, history, sessions, autocomplete, diff viewer.
"""

from __future__ import annotations

import difflib
import json
import logging
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from utils import PracticeResult, WORKSPACE_DIR, SUPPORTED_COMMANDS, split_pipeline
from data_manager import DataManager

logger = logging.getLogger("shellmentor")

# ── Autocomplete hints ────────────────────────────────────────

COMMAND_COMPLETIONS: dict[str, list[str]] = {
    "grep": [
        "grep -n 'PATTERN' FILE",
        "grep -i 'PATTERN' FILE",
        "grep -r 'PATTERN' DIR",
        "grep -c 'PATTERN' FILE",
        "grep -v 'PATTERN' FILE",
        "grep -E 'PAT1|PAT2' FILE",
        "grep -o 'PATTERN' FILE",
        "grep -A 3 'PATTERN' FILE",
        "grep -B 3 'PATTERN' FILE",
        "grep -C 3 'PATTERN' FILE",
        "grep --color=auto 'PATTERN' FILE",
    ],
    "sed": [
        "sed 's/OLD/NEW/g' FILE",
        "sed -n '/PATTERN/p' FILE",
        "sed '/PATTERN/d' FILE",
        "sed -n '5,10p' FILE",
        "sed 's/^/PREFIX/' FILE",
        "sed 's/$/SUFFIX/' FILE",
        "sed '/^$/d' FILE",
    ],
    "awk": [
        "awk '{print $1}' FILE",
        "awk -F',' '{print $2}' FILE",
        "awk '/PATTERN/ {print}' FILE",
        "awk 'NR>1 {print $0}' FILE",
        "awk '{sum+=$1} END{print sum}' FILE",
        "awk 'BEGIN{OFS=\",\"} {print $1,$3}' FILE",
        "awk '{print NR, $0}' FILE",
        "awk 'NR>=5 && NR<=10' FILE",
    ],
    "cut": [
        "cut -d',' -f1 FILE",
        "cut -d',' -f1,3 FILE",
        "cut -d':' -f1 FILE",
        "cut -c1-10 FILE",
    ],
    "sort": [
        "sort FILE",
        "sort -r FILE",
        "sort -n FILE",
        "sort -rn FILE",
        "sort -t',' -k2 FILE",
        "sort -t',' -k2 -n FILE",
        "sort -u FILE",
    ],
    "uniq": [
        "sort FILE | uniq",
        "sort FILE | uniq -c",
        "sort FILE | uniq -d",
        "sort FILE | uniq -u",
        "sort FILE | uniq -c | sort -rn",
    ],
    "find": [
        "find . -name '*.log'",
        "find . -name '*.csv'",
        "find . -type f",
        "find . -mtime -1",
    ],
    "wc": [
        "wc -l FILE",
        "wc -w FILE",
        "wc -c FILE",
    ],
}

DATASET_FILES = [
    # Mirrors the files shipped in workspace/ — keep in sync.
    "apache.log",
    "article.txt",
    "constraints.sdc",
    "employees.csv",
    "liberty.lib",
    "names.txt",
    "nginx.log",
    "sales.csv",
    "server.log",
    "synthesis.log",
    "syslog.log",
    "timing.rpt",
]

COMMAND_HELP: dict[str, dict] = {
    "grep": {
        "description": "Search for patterns in text",
        "common_flags": [
            ("-n", "Show line numbers"),
            ("-i", "Case-insensitive"),
            ("-r", "Recursive"),
            ("-c", "Count matches"),
            ("-v", "Invert match"),
            ("-E", "Extended regex"),
            ("-o", "Only matching part"),
            ("-A N", "N lines after match"),
            ("-B N", "N lines before match"),
            ("-C N", "N lines context"),
        ],
    },
    "sed": {
        "description": "Stream editor for text transformation",
        "common_flags": [
            ("s/OLD/NEW/g", "Global substitution"),
            ("-n '/PAT/p'", "Print matching lines"),
            ("'/PAT/d'", "Delete matching lines"),
            ("-n '5,10p'", "Print line range"),
            ("-i", "Edit file in-place"),
            ("-E", "Extended regex"),
        ],
    },
    "awk": {
        "description": "Pattern-action text processor",
        "common_flags": [
            ("-F','", "Set field separator"),
            ("'{print $1}'", "Print first field"),
            ("'NR>1'", "Skip first line"),
            ("'/PAT/{action}'", "Pattern matching"),
            ("'BEGIN{}'", "Run before input"),
            ("'END{}'", "Run after input"),
        ],
    },
    "sort": {
        "description": "Sort lines of text",
        "common_flags": [
            ("-n", "Numeric sort"),
            ("-r", "Reverse sort"),
            ("-u", "Unique (remove dups)"),
            ("-t','", "Field separator"),
            ("-k2", "Sort by field 2"),
        ],
    },
    "uniq": {
        "description": "Report or filter repeated lines",
        "common_flags": [
            ("-c", "Count occurrences"),
            ("-d", "Only duplicates"),
            ("-u", "Only unique"),
            ("-i", "Case-insensitive"),
        ],
    },
    "cut": {
        "description": "Extract sections from each line",
        "common_flags": [
            ("-d','", "Field delimiter"),
            ("-f2", "Select field 2"),
            ("-c1-5", "Select character range"),
        ],
    },
    "tr": {
        "description": "Translate or delete characters",
        "common_flags": [
            ("-d", "Delete characters"),
            ("-s", "Squeeze repeats"),
            ("'[:upper:]' '[:lower:]'", "Lowercase text"),
        ],
    },
    "wc": {
        "description": "Count lines, words and bytes",
        "common_flags": [
            ("-l", "Count lines"),
            ("-w", "Count words"),
            ("-c", "Count bytes"),
        ],
    },
    "head": {
        "description": "Print the first lines of input",
        "common_flags": [("-n N", "First N lines")],
    },
    "tail": {
        "description": "Print the last lines of input",
        "common_flags": [("-n N", "Last N lines"), ("-f", "Follow appended data")],
    },
    "cat": {
        "description": "Concatenate and print file contents",
        "common_flags": [("-n", "Number output lines")],
    },
    "tac": {
        "description": "Print a file's lines in reverse order",
        "common_flags": [],
    },
    "find": {
        "description": "Search a directory tree for files",
        "common_flags": [
            ("-name PAT", "Match by filename"),
            ("-type f", "Files only"),
            ("-mtime -N", "Modified in last N days"),
        ],
    },
    "xargs": {
        "description": "Build and run commands from standard input",
        "common_flags": [("-n N", "N arguments per command"), ("-I{}", "Placeholder substitution")],
    },
    "join": {
        "description": "Join lines of two sorted files on a common field",
        "common_flags": [("-t','", "Field delimiter"), ("-1 N", "Join field of file 1")],
    },
    "paste": {
        "description": "Merge lines of files side by side",
        "common_flags": [("-d','", "Output delimiter")],
    },
    "comm": {
        "description": "Compare two sorted files line by line",
        "common_flags": [("-12", "Suppress unique lines from both")],
    },
    "column": {
        "description": "Format input into aligned columns",
        "common_flags": [("-t", "Create a table")],
    },
    "ls": {
        "description": "List directory contents",
        "common_flags": [("-la", "Long listing, including hidden files")],
    },
    "ps": {
        "description": "Report a snapshot of running processes",
        "common_flags": [("aux", "All processes, full detail")],
    },
    "du": {
        "description": "Estimate file and directory space usage",
        "common_flags": [("-sh", "Human-readable total for a directory")],
    },
    "df": {
        "description": "Report filesystem disk space usage",
        "common_flags": [("-h", "Human-readable sizes")],
    },
    "echo": {
        "description": "Print text to standard output",
        "common_flags": [("-e", "Interpret backslash escapes")],
    },
    "printf": {
        "description": "Format and print text",
        "common_flags": [],
    },
    "curl": {
        "description": "Transfer data from or to a server",
        "common_flags": [("-s", "Silent mode"), ("-I", "Headers only")],
    },
    "dig": {
        "description": "Query DNS name servers",
        "common_flags": [("+short", "Terse output")],
    },
    "ping": {
        "description": "Test network reachability of a host",
        "common_flags": [("-c N", "Send N packets and stop")],
    },
    "ss": {
        "description": "Investigate network sockets",
        "common_flags": [("-tuln", "Listening TCP/UDP sockets")],
    },
    "crontab": {
        "description": "Maintain scheduled (cron) jobs for a user",
        "common_flags": [("-l", "List the current crontab")],
    },
    "uname": {
        "description": "Print system information",
        "common_flags": [("-a", "All available information")],
    },
    "chmod": {
        "description": "Change file access permissions",
        "common_flags": [("+x", "Make executable")],
    },
    "diff": {
        "description": "Compare two files line by line",
        "common_flags": [("-u", "Unified diff format")],
    },
}


PIPELINE_TEMPLATES = [
    {
        "name": "Top 10 Error Frequency",
        "command": "grep 'ERROR' server.log | awk '{print $NF}' | sort | uniq -c | sort -rn | head -10",
        "description": "Count and rank error types in server.log"
    },
    {
        "name": "Top IPs from Apache Log",
        "command": "awk '{print $1}' apache.log | sort | uniq -c | sort -rn | head -10",
        "description": "Most frequent source IPs in Apache access log"
    },
    {
        "name": "HTTP Status Distribution",
        "command": "awk '{print $9}' apache.log | sort | uniq -c | sort -rn",
        "description": "Distribution of HTTP status codes"
    },
    {
        "name": "High Salary Employees",
        "command": "awk -F',' 'NR>1 && $4>100000 {print $2, $3, $4}' employees.csv | sort -t' ' -k3 -rn",
        "description": "Employees earning over $100k sorted by salary"
    },
    {
        "name": "Timing Violations",
        "command": "grep 'VIOLATED' timing.rpt | grep -oE '-[0-9]+\\.[0-9]+' | sort -n",
        "description": "All negative slack values sorted worst-first"
    },
    {
        "name": "Clock Domains",
        "command": "grep 'create_clock' constraints.sdc | grep -oE '\\-name [^ ]+' | awk '{print $2}'",
        "description": "All clock domain names from SDC constraints"
    },
    {
        "name": "Word Frequency Analysis",
        "command": "cat server.log | tr -s '[:space:]' '\\n' | sort | uniq -c | sort -rn | head -20",
        "description": "Top 20 most frequent words in server log"
    },
    {
        "name": "Liberty Cell Count",
        "command": "grep -c '^\\s*cell\\s*(' liberty.lib",
        "description": "Count total cell definitions in Liberty library"
    },
]


@dataclass
class PlaygroundSession:
    """A recorded playground session."""
    session_id: int
    name: str
    commands: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def add(self, command: str, output: str) -> None:
        self.commands.append(command)
        self.outputs.append(output)

    def export_script(self) -> str:
        """Export session as a shell script."""
        lines = ["#!/usr/bin/env bash", f"# ShellMentor Session: {self.name}", ""]
        for cmd in self.commands:
            lines.append(cmd)
        return "\n".join(lines)

    def export_markdown(self) -> str:
        """Export session as annotated markdown."""
        lines = [f"# ShellMentor Session: {self.name}", ""]
        for cmd, out in zip(self.commands, self.outputs):
            lines.append(f"```bash\n{cmd}\n```")
            if out.strip():
                lines.append(f"```\n{out.strip()}\n```")
            lines.append("")
        return "\n".join(lines)

    def diff_outputs(self, idx1: int, idx2: int) -> str:
        """Show diff between two command outputs."""
        if idx1 >= len(self.outputs) or idx2 >= len(self.outputs):
            return "Invalid indices"
        a = self.outputs[idx1].splitlines(keepends=True)
        b = self.outputs[idx2].splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            a, b,
            fromfile=f"cmd[{idx1}]",
            tofile=f"cmd[{idx2}]",
            lineterm=""
        ))
        return "".join(diff) if diff else "No differences"


class PlaygroundEngine:
    """Interactive command playground with session management."""

    def __init__(self, db: DataManager):
        self.db = db
        self._session: PlaygroundSession | None = None
        self._history_index: int = -1
        self._on_output_callbacks: list[Callable] = []

    # ── Callbacks ─────────────────────────────────────────────

    def on_output(self, callback: Callable) -> None:
        self._on_output_callbacks.append(callback)

    def _fire_output(self, result: PracticeResult) -> None:
        for cb in self._on_output_callbacks:
            try:
                cb(result)
            except Exception as e:
                logger.error(f"Output callback error: {e}")

    # ── Execution ─────────────────────────────────────────────

    def submit_command(self, command: str, context: str = "playground") -> PracticeResult:
        """Record a command answer without executing it on the host system."""
        start = time.monotonic()
        result = PracticeResult(
            command=command,
            stdout="Command recorded. ShellMentor never executes commands; run it in your own terminal when ready.",
            stderr="",
            exit_code=0,
            duration_ms=(time.monotonic() - start) * 1000,
        )

        # Record in DB
        self.db.record_command(
            command, result.output, result.exit_code,
            context, result.duration_ms
        )

        # Append to active session
        if self._session:
            self._session.add(command, result.output)
            self.db.append_session_command(
                self._session.session_id, command, result.output
            )

        self._fire_output(result)
        self._history_index = -1
        return result

    # ── Session Management ────────────────────────────────────

    def new_session(self, name: str = "") -> PlaygroundSession:
        """Start a new recording session."""
        if self._session:
            self.close_session()
        sid = self.db.start_session(name)
        self._session = PlaygroundSession(session_id=sid, name=name or f"Session {sid}")
        return self._session

    def close_session(self) -> PlaygroundSession | None:
        """Close the current session."""
        if self._session:
            self.db.close_session(self._session.session_id)
            closed = self._session
            self._session = None
            return closed
        return None

    @property
    def active_session(self) -> PlaygroundSession | None:
        return self._session

    def get_saved_sessions(self) -> list[dict]:
        return self.db.get_sessions()

    def replay_session(self, session_id: int) -> list[PracticeResult]:
        """Return recorded session commands without executing them."""
        sessions = self.db.get_sessions()
        session = next((s for s in sessions if s["id"] == session_id), None)
        if not session:
            return []

        commands = json.loads(session.get("commands", "[]"))
        results = []
        for cmd in commands:
            result = PracticeResult(cmd, "Recorded command (not executed).", "", 0, 0)
            results.append(result)
        return results

    # ── History Navigation ────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[str]:
        """Return recent command history."""
        history = self.db.get_command_history(limit=limit, context="playground")
        return [h["command"] for h in history]

    def history_up(self) -> str | None:
        """Navigate history upward."""
        history = self.get_history(50)
        if not history:
            return None
        self._history_index = min(self._history_index + 1, len(history) - 1)
        return history[self._history_index]

    def history_down(self) -> str | None:
        """Navigate history downward."""
        if self._history_index <= 0:
            self._history_index = -1
            return ""
        self._history_index -= 1
        history = self.get_history(50)
        return history[self._history_index] if self._history_index >= 0 else ""

    # ── Autocomplete ──────────────────────────────────────────

    def autocomplete(self, partial: str) -> list[str]:
        """Return autocomplete suggestions for partial command."""
        partial = partial.strip()
        if not partial:
            return []

        suggestions = []
        partial_lower = partial.lower()

        # Command-level completions
        if " " not in partial:
            # Complete command names
            for cmd in SUPPORTED_COMMANDS:
                if cmd.startswith(partial_lower):
                    suggestions.append(cmd)
            return sorted(suggestions)[:8]

        # Flag/argument completions based on command
        base_cmd = partial.split()[0].lower()
        if base_cmd in COMMAND_COMPLETIONS:
            for template in COMMAND_COMPLETIONS[base_cmd]:
                if template.lower().startswith(partial_lower):
                    suggestions.append(template)

        # File completions
        for fname in DATASET_FILES:
            if fname.startswith(partial.split()[-1]):
                # Replace last token with filename
                parts = partial.split()
                parts[-1] = fname
                suggestions.append(" ".join(parts))

        return suggestions[:8]

    def get_command_help(self, command: str) -> dict:
        """Return quick help for a command."""
        return COMMAND_HELP.get(command.lower(), {
            "description": f"Linux command: {command}",
            "common_flags": [],
        })

    def explain_pipeline(self, command: str) -> list[dict]:
        """Break a (possibly piped) command into a plain-language, stage-by-
        stage explanation — purely textual, built from COMMAND_HELP, never
        executed. Used to show *why* a reference solution works, not just
        what it is."""
        explanation = []
        for idx, stage in enumerate(split_pipeline(command), start=1):
            try:
                tokens = shlex.split(stage)
            except ValueError:
                tokens = stage.split()
            base = tokens[0] if tokens else ""
            help_info = self.get_command_help(base) if base else {"description": ""}
            explanation.append({
                "stage": idx,
                "command": stage,
                "tool": base,
                "description": help_info.get("description", ""),
            })
        return explanation

    # ── Pipeline Templates ────────────────────────────────────

    def get_pipeline_templates(self) -> list[dict]:
        return PIPELINE_TEMPLATES

    # ── Workspace Info ────────────────────────────────────────

    def list_workspace_files(self) -> list[dict]:
        """Return info about available workspace files."""
        files = []
        for fname in DATASET_FILES:
            fpath = WORKSPACE_DIR / fname
            if fpath.exists():
                stat = fpath.stat()
                files.append({
                    "name":  fname,
                    "size":  stat.st_size,
                    "lines": self._count_lines(fpath),
                })
        return files

    def _count_lines(self, path: Path) -> int:
        try:
            with open(path) as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def get_file_preview(self, filename: str, lines: int = 20) -> str:
        """Return first N lines of a workspace file."""
        fpath = WORKSPACE_DIR / filename
        if not fpath.exists():
            return f"File not found: {filename}"
        try:
            with open(fpath, encoding="utf-8", errors="replace") as f:
                preview_lines = []
                for i, line in enumerate(f):
                    if i >= lines:
                        total = sum(1 for _ in open(fpath, encoding="utf-8", errors="replace"))
                        preview_lines.append(f"... ({total - lines} more lines)")
                        break
                    preview_lines.append(line.rstrip())
            return "\n".join(preview_lines)
        except Exception as e:
            return f"Error reading file: {e}"

    # ── Diff Viewer ───────────────────────────────────────────

    def diff_outputs(self, output_a: str, output_b: str,
                     label_a: str = "A", label_b: str = "B") -> str:
        """Show unified diff between two output strings."""
        a_lines = output_a.splitlines(keepends=True)
        b_lines = output_b.splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            a_lines, b_lines,
            fromfile=label_a, tofile=label_b,
            lineterm=""
        ))
        if not diff:
            return "✓ Outputs are identical"
        return "".join(diff)

    # ── Stats ─────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return playground usage stats."""
        history = self.db.get_command_history(limit=1000, context="playground")
        total = len(history)
        success = sum(1 for h in history if h["exit_code"] == 0)
        cmds: dict[str, int] = {}
        for h in history:
            cmd = h["command"].split()[0] if h["command"].strip() else ""
            cmds[cmd] = cmds.get(cmd, 0) + 1

        top_cmds = sorted(cmds.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_commands": total,
            "success_rate":   (success / total * 100) if total > 0 else 0,
            "top_commands":   [{"cmd": c, "count": n} for c, n in top_cmds],
            "sessions":       len(self.db.get_sessions()),
        }
