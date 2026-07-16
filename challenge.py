"""
ShellMentor - challenge.py
Challenge engine: loading challenges, validation, mission mode, scoring.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from utils import DATA_DIR, WORKSPACE_DIR, load_json, validate_challenge_output
from data_manager import DataManager

logger = logging.getLogger("shellmentor")


@dataclass
class ActiveChallenge:
    challenge: dict
    started_at: float = field(default_factory=time.time)
    hints_revealed: int = 0
    attempts: int = 0
    command_history: list[str] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def next_hint(self) -> str | None:
        hints = self.challenge.get("hints", [])
        if self.hints_revealed < len(hints):
            hint = hints[self.hints_revealed]
            self.hints_revealed += 1
            return hint
        return None

    @property
    def all_hints_shown(self) -> bool:
        return self.hints_revealed >= len(self.challenge.get("hints", []))


@dataclass
class ActiveMission:
    mission: dict
    current_stage_idx: int = 0
    started_at: float = field(default_factory=time.time)
    stages_completed: list[int] = field(default_factory=list)
    total_xp_earned: int = 0

    @property
    def current_stage(self) -> dict | None:
        stages = self.mission.get("stages", [])
        if self.current_stage_idx < len(stages):
            return stages[self.current_stage_idx]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_stage_idx >= len(self.mission.get("stages", []))

    @property
    def progress_pct(self) -> float:
        total = len(self.mission.get("stages", []))
        if total == 0:
            return 100.0
        return (len(self.stages_completed) / total) * 100


class ChallengeEngine:
    """Manages challenges and missions."""

    def __init__(self, db: DataManager):
        self.db = db
        self._challenges_data: list[dict] = []
        self._missions_data: list[dict] = []
        self._active: ActiveChallenge | None = None
        self._active_mission: ActiveMission | None = None
        self._on_complete_callbacks: list[Callable] = []
        self._load_data()

    def _load_data(self) -> None:
        ch_data = load_json(DATA_DIR / "challenges.json")
        self._challenges_data = ch_data.get("challenges", [])
        ms_data = load_json(DATA_DIR / "missions.json")
        self._missions_data = ms_data.get("missions", [])

    def on_complete(self, callback: Callable) -> None:
        self._on_complete_callbacks.append(callback)

    # ── Challenge Access ──────────────────────────────────────

    def get_challenges(self, difficulty: str = "", track: str = "") -> list[dict]:
        challenges = self._challenges_data
        if difficulty:
            challenges = [c for c in challenges if c.get("difficulty") == difficulty]
        if track:
            challenges = [c for c in challenges if c.get("track") == track]

        solved = self.db.get_solved_challenges()
        result = []
        for ch in challenges:
            d = dict(ch)
            d["solved"] = ch["id"] in solved

            # Get attempt info
            row = self.db.conn.execute(
                "SELECT attempts, hints_used, best_time FROM challenge_history "
                "WHERE user_id=1 AND challenge_id=?", (ch["id"],)
            ).fetchone()
            if row:
                d["attempts"]   = row["attempts"]
                d["hints_used"] = row["hints_used"]
                d["best_time"]  = row["best_time"]
            else:
                d["attempts"]   = 0
                d["hints_used"] = 0
                d["best_time"]  = 0.0

            result.append(d)
        return result

    def get_challenge(self, challenge_id: str) -> dict | None:
        return next((c for c in self._challenges_data if c["id"] == challenge_id), None)

    # ── Challenge Session ─────────────────────────────────────

    def start_challenge(self, challenge_id: str) -> ActiveChallenge | None:
        ch = self.get_challenge(challenge_id)
        if not ch:
            return None
        self._active = ActiveChallenge(challenge=ch)
        return self._active

    @property
    def active_challenge(self) -> ActiveChallenge | None:
        return self._active

    def submit_challenge(self, user_output: str) -> dict:
        """Validate challenge submission. Returns result dict."""
        if not self._active:
            return {"solved": False, "message": "No active challenge"}

        ch = self._active.challenge

        passed, message = validate_challenge_output(
            user_output,
            ch.get("expected_pattern", ""),
            ch.get("validation_type", "pattern_match"),
            ch.get("expected_lines", 0)
        )

        # Calculate XP before incrementing attempts (so first-attempt bonus works)
        if passed:
            xp_reward = self._calc_challenge_xp(ch, self._active)
        else:
            xp_reward = 0

        self._active.attempts += 1

        result = {
            "solved":    passed,
            "message":   message,
            "attempts":  self._active.attempts,
            "elapsed":   self._active.elapsed,
            "hints_used":self._active.hints_revealed,
            "xp_earned": xp_reward,
        }

        if passed:
            result["solution"]  = ch.get("solution", "")
            for cb in self._on_complete_callbacks:
                try:
                    cb("challenge", {
                        "challenge_id": ch["id"],
                        "xp":           xp_reward,
                        "hints":        self._active.hints_revealed,
                        "duration":     self._active.elapsed,
                    })
                except Exception as e:
                    logger.error(f"Challenge complete callback error: {e}")
            self._active = None

        return result

    def _calc_challenge_xp(self, challenge: dict, session: ActiveChallenge) -> int:
        """Calculate XP with bonuses/penalties."""
        base_xp = challenge.get("xp_reward", 100)
        # Hint penalty: -10% per hint
        hint_factor = max(0.5, 1.0 - (session.hints_revealed * 0.10))
        # Speed bonus: < 60s gets +20%
        speed_factor = 1.2 if session.elapsed < 60 else 1.0
        # First attempt bonus: +10%
        attempt_factor = 1.1 if session.attempts == 1 else 1.0
        return int(base_xp * hint_factor * speed_factor * attempt_factor)

    def request_hint(self) -> str | None:
        """Request next hint for active challenge."""
        if not self._active:
            return None
        return self._active.next_hint()

    def abandon_challenge(self) -> None:
        self._active = None

    # ── Mission Mode ──────────────────────────────────────────

    def get_missions(self) -> list[dict]:
        completed = self.db.get_completed_missions()
        result = []
        for m in self._missions_data:
            d = dict(m)
            d["completed"] = m["id"] in completed
            d["stages_done"] = self.db.get_mission_progress(m["id"])
            d["total_stages"] = len(m.get("stages", []))
            result.append(d)
        return result

    def get_mission(self, mission_id: str) -> dict | None:
        return next((m for m in self._missions_data if m["id"] == mission_id), None)

    def start_mission(self, mission_id: str) -> ActiveMission | None:
        mission = self.get_mission(mission_id)
        if not mission:
            return None
        # Resume from last completed stage
        last_stage = self.db.get_mission_progress(mission_id)
        am = ActiveMission(mission=mission, current_stage_idx=last_stage)
        am.stages_completed = list(range(last_stage))
        self._active_mission = am
        return am

    @property
    def active_mission(self) -> ActiveMission | None:
        return self._active_mission

    def submit_mission_stage(self, user_output: str) -> dict:
        """Validate current mission stage. Returns result dict."""
        if not self._active_mission:
            return {"passed": False, "message": "No active mission"}

        stage = self._active_mission.current_stage
        if not stage:
            return {"passed": False, "message": "Mission is already complete"}

        passed, message = validate_challenge_output(
            user_output, "", "format_check", 0
        )

        result = {
            "passed":   True,  # Missions are more guided, accept reasonable output
            "message":  f"Stage {stage['stage']} complete! {message}",
            "xp_earned": stage.get("xp", 100),
            "stage":    stage["stage"],
            "is_final": False,
        }

        self._active_mission.stages_completed.append(self._active_mission.current_stage_idx)
        self._active_mission.total_xp_earned += stage.get("xp", 100)
        self._active_mission.current_stage_idx += 1

        if self._active_mission.is_complete:
            result["is_final"] = True
            result["total_xp"] = self._active_mission.total_xp_earned
            result["badge"] = self._active_mission.mission.get("badge", "")

            for cb in self._on_complete_callbacks:
                try:
                    cb("mission", {
                        "mission_id": self._active_mission.mission["id"],
                        "total_xp":   self._active_mission.total_xp_earned,
                    })
                except Exception as e:
                    logger.error(f"Mission complete callback error: {e}")

        return result

    def abandon_mission(self) -> None:
        self._active_mission = None

    # ── Stats ─────────────────────────────────────────────────

    def get_challenge_stats(self) -> dict:
        all_ch = self.get_challenges()
        solved = sum(1 for c in all_ch if c["solved"])
        by_diff: dict[str, dict] = {}
        for ch in all_ch:
            d = ch.get("difficulty", "beginner")
            if d not in by_diff:
                by_diff[d] = {"total": 0, "solved": 0}
            by_diff[d]["total"] += 1
            if ch["solved"]:
                by_diff[d]["solved"] += 1

        return {
            "total":    len(all_ch),
            "solved":   solved,
            "unsolved": len(all_ch) - solved,
            "by_difficulty": by_diff,
        }
