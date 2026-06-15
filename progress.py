"""
ShellMentor - progress.py
Gamification engine: XP, levels, achievements, streaks, portfolio generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from utils import (
    DATA_DIR, WORKSPACE_DIR, load_json, generate_portfolio_markdown,
    format_xp, APP_VERSION
)
from data_manager import DataManager

logger = logging.getLogger("shellmentor")


@dataclass
class XPEvent:
    source: str
    amount: int
    label: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LevelUpEvent:
    old_level: int
    new_level: int
    new_title: str
    xp_total: int


class ProgressEngine:
    """Central engine for XP, levels, achievements, and gamification."""

    def __init__(self, db: DataManager):
        self.db = db
        self._achievements_data = self._load_achievements()
        self._on_achievement_callbacks: list[Callable] = []
        self._on_levelup_callbacks: list[Callable] = []
        self._on_xp_callbacks: list[Callable] = []

    # ── Data Loading ──────────────────────────────────────────

    def _load_achievements(self) -> list[dict]:
        data = load_json(DATA_DIR / "achievements.json")
        return data.get("achievements", [])

    def get_ranks(self) -> list[dict]:
        data = load_json(DATA_DIR / "achievements.json")
        return data.get("ranks", [])

    # ── Event Registration ────────────────────────────────────

    def on_achievement(self, callback: Callable) -> None:
        self._on_achievement_callbacks.append(callback)

    def on_levelup(self, callback: Callable) -> None:
        self._on_levelup_callbacks.append(callback)

    def on_xp(self, callback: Callable) -> None:
        self._on_xp_callbacks.append(callback)

    def _fire_achievement(self, achievement: dict) -> None:
        for cb in self._on_achievement_callbacks:
            try:
                cb(achievement)
            except Exception as e:
                logger.error(f"Achievement callback error: {e}")

    def _fire_levelup(self, event: LevelUpEvent) -> None:
        for cb in self._on_levelup_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Level-up callback error: {e}")

    def _fire_xp(self, event: XPEvent) -> None:
        for cb in self._on_xp_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"XP callback error: {e}")

    # ── XP Award ─────────────────────────────────────────────

    def award_xp(self, amount: int, source: str, label: str = "") -> dict:
        """Award XP, check for level-up, fire callbacks. Returns result dict."""
        user_before = self.db.get_user()
        old_level = user_before.get("level", 1)

        result = self.db.add_xp(amount)
        new_level = result["level"]
        leveled_up = result.get("leveled_up", False)

        xp_event = XPEvent(source=source, amount=amount, label=label or source)
        self._fire_xp(xp_event)

        if leveled_up:
            lv_event = LevelUpEvent(
                old_level=old_level,
                new_level=new_level,
                new_title=result["rank_title"],
                xp_total=result["xp"]
            )
            self._fire_levelup(lv_event)

        # Check achievements after every XP award
        newly_earned = self.db.check_and_award_achievements(self._achievements_data)
        for ach in newly_earned:
            self._fire_achievement(ach)

        return result

    # ── Lesson Completion ─────────────────────────────────────

    def complete_lesson(self, lesson_id: str, track_id: str,
                        score: int, xp_reward: int, time_spent: int) -> dict:
        """Record lesson completion and award XP."""
        self.db.record_lesson_completion(
            lesson_id, track_id, score, xp_reward, time_spent
        )
        self.db.update_streak()
        result = self.award_xp(xp_reward, "lesson", f"Lesson: {lesson_id}")
        self._check_track_completion(track_id)
        return result

    def _check_track_completion(self, track_id: str) -> None:
        """Check if all lessons in a track are complete."""
        from learning import LearningEngine
        # Import here to avoid circular; just check lesson count
        lessons_data = load_json(DATA_DIR / "lessons.json")
        tracks = lessons_data.get("tracks", [])
        for track in tracks:
            if track["id"] == track_id:
                lesson_ids = {l["id"] for l in track.get("lessons", [])}
                completed = self.db.get_completed_lessons()
                if lesson_ids.issubset(completed):
                    self.db.add_track_completed(track_id)
                break

    # ── Challenge Completion ──────────────────────────────────

    def complete_challenge(self, challenge_id: str, xp_reward: int,
                            hints_used: int, duration: float, command: str) -> dict:
        """Record challenge completion and award XP."""
        self.db.record_challenge_attempt(
            challenge_id, solved=True, xp=xp_reward,
            hints=hints_used, duration=duration, command=command
        )
        self.db.update_streak()
        result = self.award_xp(xp_reward, "challenge", f"Challenge: {challenge_id}")

        # Speed achievement check
        if duration < 120:
            self._try_award("speed_demon")

        return result

    def attempt_challenge(self, challenge_id: str, hints: int,
                          duration: float, command: str) -> None:
        """Record a failed challenge attempt."""
        self.db.record_challenge_attempt(
            challenge_id, solved=False, xp=0,
            hints=hints, duration=duration, command=command
        )

    # ── Mission Progress ──────────────────────────────────────

    def complete_mission_stage(self, mission_id: str, stage: int,
                                stage_xp: int) -> dict:
        self.db.record_mission_stage(mission_id, stage, completed=True, xp=stage_xp)
        return self.award_xp(stage_xp, "mission", f"Mission stage {stage}")

    def complete_mission(self, mission_id: str, total_xp: int) -> dict:
        self.db.record_mission_stage(mission_id, 999, completed=True, xp=0)
        result = self.award_xp(total_xp, "mission_complete", f"Mission: {mission_id}")
        self._try_award("mission_complete")
        return result

    # ── Quiz Result ───────────────────────────────────────────

    def record_quiz_answer(self, correct: bool, used_hint: bool = False) -> None:
        self.db.record_quiz_result(correct)
        if correct:
            xp = 5 if used_hint else 10
            self.award_xp(xp, "quiz", "Quiz answer")

    # ── Notes ─────────────────────────────────────────────────

    def create_note(self, title: str, content: str, tags: list = None) -> int:
        note_id = self.db.create_note(title, content, tags)
        self._try_award("note_taker")
        return note_id

    # ── Achievement Helpers ───────────────────────────────────

    def _try_award(self, achievement_id: str) -> bool:
        """Try to award a specific achievement by ID."""
        ach = next((a for a in self._achievements_data if a["id"] == achievement_id), None)
        if not ach:
            return False
        earned = self.db.get_earned_achievements()
        if achievement_id in earned:
            return False
        if self.db.award_achievement(achievement_id, ach.get("xp_reward", 0)):
            self._fire_achievement(ach)
            self.db.add_xp(ach.get("xp_reward", 0))
            return True
        return False

    def get_achievement_stats(self) -> dict:
        """Return achievement progress summary."""
        earned = self.db.get_earned_achievements()
        total = len(self._achievements_data)
        return {
            "earned": len(earned),
            "total": total,
            "percent": (len(earned) / total * 100) if total > 0 else 0,
            "earned_ids": earned,
        }

    def get_full_achievements_list(self) -> list[dict]:
        """Return all achievements with earned status."""
        earned = self.db.get_earned_achievements()
        result = []
        for ach in self._achievements_data:
            d = dict(ach)
            d["earned"] = ach["id"] in earned
            result.append(d)
        return result

    # ── Portfolio ─────────────────────────────────────────────

    def generate_portfolio(self, output_path: Path = None) -> tuple[str, Path]:
        """Generate markdown portfolio. Returns (content, path)."""
        user = self.db.get_user()
        progress = self.db.get_progress()
        earned_ids = self.db.get_earned_achievements()
        earned_achs = [a for a in self._achievements_data if a["id"] in earned_ids]

        content = generate_portfolio_markdown(user, earned_achs, progress)

        if output_path is None:
            output_path = Path.home() / "shellmentor-portfolio" / "README.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        self._try_award("portfolio_published")
        logger.info(f"Portfolio generated at {output_path}")
        return content, output_path

    # ── Stats Snapshot ────────────────────────────────────────

    def get_dashboard_stats(self) -> dict:
        """Return all stats needed for dashboard display."""
        user = self.db.get_user()
        progress = self.db.get_progress()
        ach_stats = self.get_achievement_stats()
        analytics = self.db.get_analytics_summary()

        accuracy = 0
        qp = progress.get("quizzes_taken", 0)
        qc = progress.get("quiz_correct", 0)
        if qp > 0:
            accuracy = (qc / qp) * 100

        return {
            "username":        user.get("username", "Learner"),
            "level":           user.get("level", 1),
            "rank_title":      user.get("rank_title", "Terminal Novice"),
            "xp":              user.get("xp", 0),
            "streak":          user.get("streak", 0),
            "lessons":         progress.get("lessons_completed", 0),
            "challenges":      progress.get("challenges_solved", 0),
            "missions":        progress.get("missions_completed", 0),
            "commands_run":    progress.get("commands_executed", 0),
            "time_spent":      progress.get("time_spent_mins", 0),
            "accuracy":        accuracy,
            "achievements_earned": ach_stats["earned"],
            "achievements_total":  ach_stats["total"],
            "top_commands":    analytics.get("top_commands", []),
        }

    def get_next_rank_info(self) -> dict:
        """Return info about the next rank/level."""
        ranks = self.get_ranks()
        user = self.db.get_user()
        current_xp = user.get("xp", 0)
        current_level = user.get("level", 1)

        if current_level < len(ranks):
            next_rank = ranks[current_level]  # ranks are 1-indexed in the list
            xp_needed = next_rank["xp_required"] - current_xp
            return {
                "next_title": next_rank["title"],
                "next_icon": next_rank["icon"],
                "xp_needed": max(0, xp_needed),
                "next_xp_threshold": next_rank["xp_required"],
                "progress_pct": min(100, (current_xp / next_rank["xp_required"]) * 100)
                                if next_rank["xp_required"] > 0 else 100
            }
        return {"next_title": "Max Rank", "xp_needed": 0, "progress_pct": 100,
                "next_icon": "👑", "next_xp_threshold": current_xp}
