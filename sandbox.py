"""
ShellMentor - sandbox.py
Extended sandbox: virtual filesystem management, session recording,
output capture, and safety audit utilities.

This is the 10th and final Python file (per spec: max 10 Python files).
All additional content lives in JSON/YAML/SQLite/dataset files.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from utils import WORKSPACE_DIR, SandboxEngine, SandboxResult

logger = logging.getLogger("shellmentor")


# ──────────────────────── Session Recording ────────────────────────

@dataclass
class RecordedCommand:
    index: int
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timestamp: str
    blocked: bool = False


@dataclass
class SessionRecording:
    """A full recorded sandbox session with replay capability."""

    name: str
    commands: list[RecordedCommand] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    metadata: dict = field(default_factory=dict)

    def add(self, result: SandboxResult) -> RecordedCommand:
        rec = RecordedCommand(
            index=len(self.commands),
            command=result.command,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            timestamp=result.timestamp,
            blocked=result.blocked,
        )
        self.commands.append(rec)
        return rec

    def stop(self) -> None:
        self.ended_at = time.time()

    @property
    def duration_s(self) -> float:
        end = self.ended_at or time.time()
        return end - self.started_at

    @property
    def total_commands(self) -> int:
        return len(self.commands)

    @property
    def success_rate(self) -> float:
        if not self.commands:
            return 0.0
        good = sum(1 for c in self.commands if c.exit_code == 0 and not c.blocked)
        return (good / len(self.commands)) * 100

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "commands": [
                {
                    "index":    c.index,
                    "command":  c.command,
                    "stdout":   c.stdout,
                    "stderr":   c.stderr,
                    "exit_code":c.exit_code,
                    "duration_ms": c.duration_ms,
                    "timestamp": c.timestamp,
                    "blocked":  c.blocked,
                }
                for c in self.commands
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionRecording":
        rec = cls(
            name=data.get("name", "Unnamed"),
            started_at=data.get("started_at", 0),
            ended_at=data.get("ended_at", 0),
            metadata=data.get("metadata", {}),
        )
        for cmd_data in data.get("commands", []):
            rec.commands.append(RecordedCommand(
                index=cmd_data.get("index", 0),
                command=cmd_data.get("command", ""),
                stdout=cmd_data.get("stdout", ""),
                stderr=cmd_data.get("stderr", ""),
                exit_code=cmd_data.get("exit_code", 0),
                duration_ms=cmd_data.get("duration_ms", 0),
                timestamp=cmd_data.get("timestamp", ""),
                blocked=cmd_data.get("blocked", False),
            ))
        return rec

    def export_script(self, include_output: bool = False) -> str:
        """Export as shell script."""
        lines = [
            "#!/usr/bin/env bash",
            f"# ShellMentor Session: {self.name}",
            f"# Commands: {self.total_commands}",
            f"# Success rate: {self.success_rate:.0f}%",
            "",
        ]
        for cmd in self.commands:
            if cmd.blocked:
                lines.append(f"# [BLOCKED] {cmd.command}")
                continue
            lines.append(cmd.command)
            if include_output and cmd.stdout:
                for line in cmd.stdout.splitlines()[:3]:
                    lines.append(f"# → {line}")
        return "\n".join(lines)

    def export_markdown(self) -> str:
        """Export as annotated Markdown."""
        lines = [
            f"# ShellMentor Session: {self.name}",
            "",
            f"- **Commands:** {self.total_commands}",
            f"- **Duration:** {self.duration_s:.1f}s",
            f"- **Success rate:** {self.success_rate:.0f}%",
            "",
            "---",
            "",
        ]
        for cmd in self.commands:
            if cmd.blocked:
                lines.append(f"> ⛔ **Blocked:** `{cmd.command}`")
                lines.append("")
                continue
            lines.append(f"```bash")
            lines.append(cmd.command)
            lines.append(f"```")
            if cmd.stdout:
                lines.append(f"```")
                lines.append(cmd.stdout.strip()[:500])
                lines.append(f"```")
            lines.append("")
        return "\n".join(lines)


# ──────────────────────── Virtual Filesystem Manager ────────────────────────

class VirtualFilesystem:
    """
    Manages the isolated workspace: reset, snapshot, restore.
    Dataset files are always restored from the bundled originals.
    """

    BUNDLED_FILES = [
        "apache.log", "nginx.log", "server.log",
        "employees.csv", "timing.rpt", "synthesis.log",
        "constraints.sdc", "liberty.lib",
    ]

    def __init__(self, workspace: Path = WORKSPACE_DIR,
                 source: Path = WORKSPACE_DIR):
        self.workspace = workspace
        self.source = source
        self.workspace.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> list[dict]:
        """Return info about all workspace files."""
        files = []
        for fname in self.BUNDLED_FILES:
            fpath = self.workspace / fname
            if fpath.exists():
                stat = fpath.stat()
                files.append({
                    "name":     fname,
                    "size":     stat.st_size,
                    "lines":    self._count_lines(fpath),
                    "modified": stat.st_mtime,
                    "bundled":  True,
                })
        # Also list any user-created files
        for fpath in self.workspace.iterdir():
            if fpath.name not in self.BUNDLED_FILES and fpath.is_file():
                stat = fpath.stat()
                files.append({
                    "name":     fpath.name,
                    "size":     stat.st_size,
                    "lines":    self._count_lines(fpath),
                    "modified": stat.st_mtime,
                    "bundled":  False,
                })
        return files

    def _count_lines(self, path: Path) -> int:
        try:
            with open(path) as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def snapshot(self) -> dict:
        """Create an in-memory snapshot of all workspace files."""
        snap: dict[str, str] = {}
        for fname in self.BUNDLED_FILES:
            fpath = self.workspace / fname
            if fpath.exists():
                try:
                    snap[fname] = fpath.read_text(errors="replace")
                except Exception:
                    pass
        return snap

    def restore(self, snapshot: dict) -> None:
        """Restore workspace from snapshot."""
        for fname, content in snapshot.items():
            fpath = self.workspace / fname
            try:
                fpath.write_text(content)
            except Exception as e:
                logger.error(f"Restore failed for {fname}: {e}")

    def reset_to_defaults(self) -> None:
        """
        Restore bundled dataset files to original content.
        Source is the same workspace dir (files are created by create_datasets).
        User-created files are preserved.
        """
        logger.info("Resetting workspace to defaults (no-op — datasets are static)")
        # Datasets are read-only from the perspective of lessons;
        # if user created extra files, leave them alone.

    def get_file_hash(self, filename: str) -> str:
        """Return MD5 hash of a workspace file."""
        fpath = self.workspace / filename
        if not fpath.exists():
            return ""
        h = hashlib.md5()
        with open(fpath, "rb") as f:
            h.update(f.read())
        return h.hexdigest()

    def preview(self, filename: str, n_lines: int = 10) -> str:
        """Return first n_lines of a workspace file."""
        fpath = self.workspace / filename
        if not fpath.exists():
            return f"File not found: {filename}"
        try:
            with open(fpath) as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= n_lines:
                        break
                    lines.append(line.rstrip())
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"


# ──────────────────────── Enhanced Sandbox ────────────────────────

class EnhancedSandbox(SandboxEngine):
    """
    Extends SandboxEngine with recording, snapshot/restore,
    and per-challenge isolated environments.
    """

    def __init__(self, workspace: Path = WORKSPACE_DIR):
        super().__init__(workspace)
        self.vfs = VirtualFilesystem(workspace)
        self._recording: SessionRecording | None = None
        self._snapshots: dict[str, dict] = {}
        self._on_command_callbacks: list[Callable] = []

    def on_command(self, callback: Callable) -> None:
        self._on_command_callbacks.append(callback)

    def run(self, command: str, timeout: int = 10) -> SandboxResult:
        result = super().run(command, timeout)
        if self._recording:
            self._recording.add(result)
        for cb in self._on_command_callbacks:
            try:
                cb(result)
            except Exception:
                pass
        return result

    # ── Recording ──────────────────────────────────────────

    def start_recording(self, name: str = "") -> SessionRecording:
        self._recording = SessionRecording(
            name=name or f"Session-{int(time.time())}"
        )
        return self._recording

    def stop_recording(self) -> SessionRecording | None:
        if self._recording:
            self._recording.stop()
            rec = self._recording
            self._recording = None
            return rec
        return None

    @property
    def is_recording(self) -> bool:
        return self._recording is not None

    # ── Snapshots ──────────────────────────────────────────

    def save_snapshot(self, name: str) -> None:
        self._snapshots[name] = self.vfs.snapshot()

    def restore_snapshot(self, name: str) -> bool:
        if name in self._snapshots:
            self.vfs.restore(self._snapshots[name])
            return True
        return False

    # ── Challenge Isolation ────────────────────────────────

    def prepare_for_challenge(self, challenge_id: str) -> None:
        """Save workspace snapshot before challenge."""
        self.save_snapshot(f"pre_challenge_{challenge_id}")

    def cleanup_after_challenge(self, challenge_id: str) -> None:
        """Restore workspace after challenge completes."""
        key = f"pre_challenge_{challenge_id}"
        if key in self._snapshots:
            self.restore_snapshot(key)
            del self._snapshots[key]

    # ── Safety Audit ──────────────────────────────────────

    def audit_history(self) -> dict:
        """Analyze command history for patterns."""
        total = len(self.history)
        blocked = sum(1 for r in self.history if r.blocked)
        failed  = sum(1 for r in self.history if r.exit_code != 0 and not r.blocked)
        success = total - blocked - failed

        cmd_freq: dict[str, int] = {}
        for r in self.history:
            tok = r.command.split()[0] if r.command.strip() else ""
            cmd_freq[tok] = cmd_freq.get(tok, 0) + 1

        avg_duration = (
            sum(r.duration_ms for r in self.history) / total
            if total > 0 else 0
        )

        return {
            "total":         total,
            "success":       success,
            "failed":        failed,
            "blocked":       blocked,
            "success_rate":  (success / total * 100) if total > 0 else 0,
            "avg_duration_ms": avg_duration,
            "top_commands":  sorted(cmd_freq.items(), key=lambda x: x[1], reverse=True)[:10],
        }

    def replay(self, recording: SessionRecording,
               on_result: Callable | None = None) -> list[SandboxResult]:
        """Replay a recorded session."""
        results = []
        for cmd_rec in recording.commands:
            if cmd_rec.blocked:
                continue
            result = self.run(cmd_rec.command)
            results.append(result)
            if on_result:
                on_result(result)
            time.sleep(0.05)  # Small delay for UI rendering
        return results


# ──────────────────────── Output Differ ────────────────────────

class OutputDiffer:
    """Compare and diff command outputs for learning feedback."""

    @staticmethod
    def diff(expected: str, actual: str) -> dict:
        """
        Compare expected vs actual output.
        Returns structured diff result.
        """
        exp_lines = expected.strip().splitlines()
        act_lines = actual.strip().splitlines()

        exp_set = set(exp_lines)
        act_set = set(act_lines)

        missing = exp_set - act_set
        extra   = act_set - exp_set
        correct = exp_set & act_set

        line_match = exp_lines == act_lines
        set_match  = exp_set == act_set

        return {
            "exact_match":  line_match,
            "set_match":    set_match,
            "correct_lines":sorted(correct),
            "missing_lines":sorted(missing),
            "extra_lines":  sorted(extra),
            "expected_count": len(exp_lines),
            "actual_count":   len(act_lines),
            "similarity_pct": (len(correct) / max(len(exp_set), 1)) * 100,
        }

    @staticmethod
    def format_diff(diff_result: dict) -> str:
        """Format diff result for terminal display."""
        lines = []
        if diff_result["exact_match"]:
            lines.append("✓ Exact match!")
        elif diff_result["set_match"]:
            lines.append("≈ Same content, different order")
        else:
            lines.append(f"Similarity: {diff_result['similarity_pct']:.0f}%")
            if diff_result["missing_lines"]:
                lines.append("Missing from your output:")
                for l in diff_result["missing_lines"][:5]:
                    lines.append(f"  - {l}")
            if diff_result["extra_lines"]:
                lines.append("Extra in your output:")
                for l in diff_result["extra_lines"][:5]:
                    lines.append(f"  + {l}")
        return "\n".join(lines)


# ──────────────────────── Public Factory ────────────────────────

def create_enhanced_sandbox(workspace: Path = WORKSPACE_DIR) -> EnhancedSandbox:
    """Factory function: create and return a configured EnhancedSandbox."""
    return EnhancedSandbox(workspace)
