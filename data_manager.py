"""
ShellMentor - data_manager.py
SQLite-backed persistence: user progress, sessions, notes, analytics, settings.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

logger = logging.getLogger("shellmentor")

DB_PATH = Path(user_data_dir("ShellMentor", "AndGate")) / "shellmentor.db"


class DataManager:
    """Central SQLite data store for ShellMentor."""

    def __init__(self, db_path: Path | None = None):
        # Resolved at call time (not bound at import time) so tests and callers
        # can point ShellMentor at a scratch database.
        self.db_path = Path(db_path) if db_path is not None else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ── Connection ──────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._connect()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Schema ──────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create all tables if not exist."""
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS user (
                id            INTEGER PRIMARY KEY,
                username      TEXT DEFAULT 'Learner',
                xp            INTEGER DEFAULT 0,
                level         INTEGER DEFAULT 1,
                rank_title    TEXT DEFAULT 'Terminal Novice',
                streak        INTEGER DEFAULT 0,
                challenge_streak INTEGER DEFAULT 0,
                last_active   TEXT,
                created_at    TEXT DEFAULT (datetime('now')),
                theme         TEXT DEFAULT 'professional_dark',
                settings      TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS progress (
                id                  INTEGER PRIMARY KEY,
                user_id             INTEGER DEFAULT 1,
                lessons_completed   INTEGER DEFAULT 0,
                challenges_solved   INTEGER DEFAULT 0,
                missions_completed  INTEGER DEFAULT 0,
                quizzes_taken       INTEGER DEFAULT 0,
                quiz_correct        INTEGER DEFAULT 0,
                commands_executed   INTEGER DEFAULT 0,
                time_spent_mins     INTEGER DEFAULT 0,
                challenges_nohint   INTEGER DEFAULT 0,
                tracks_completed    TEXT DEFAULT '[]',
                FOREIGN KEY (user_id) REFERENCES user(id)
            );

            CREATE TABLE IF NOT EXISTS lesson_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                lesson_id   TEXT NOT NULL,
                track_id    TEXT NOT NULL,
                completed   INTEGER DEFAULT 0,
                score       INTEGER DEFAULT 0,
                xp_earned   INTEGER DEFAULT 0,
                time_spent  INTEGER DEFAULT 0,
                completed_at TEXT,
                attempts    INTEGER DEFAULT 1,
                current_section INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS challenge_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                challenge_id TEXT NOT NULL,
                solved      INTEGER DEFAULT 0,
                xp_earned   INTEGER DEFAULT 0,
                hints_used  INTEGER DEFAULT 0,
                attempts    INTEGER DEFAULT 0,
                best_time   REAL DEFAULT 0,
                solved_at   TEXT,
                last_command TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS mission_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                mission_id  TEXT NOT NULL,
                stage       INTEGER DEFAULT 0,
                completed   INTEGER DEFAULT 0,
                is_final    INTEGER DEFAULT 0,
                xp_earned   INTEGER DEFAULT 0,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER DEFAULT 1,
                achievement_id  TEXT NOT NULL UNIQUE,
                earned_at       TEXT DEFAULT (datetime('now')),
                xp_earned       INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                title       TEXT NOT NULL,
                content     TEXT DEFAULT '',
                tags        TEXT DEFAULT '[]',
                category    TEXT DEFAULT 'general',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                name        TEXT DEFAULT '',
                commands    TEXT DEFAULT '[]',
                outputs     TEXT DEFAULT '[]',
                started_at  TEXT DEFAULT (datetime('now')),
                ended_at    TEXT,
                total_cmds  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS command_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                command     TEXT NOT NULL,
                output      TEXT DEFAULT '',
                exit_code   INTEGER DEFAULT 0,
                context     TEXT DEFAULT 'playground',
                duration_ms REAL DEFAULT 0,
                executed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS analytics (
                id          INTEGER PRIMARY KEY,
                user_id     INTEGER DEFAULT 1,
                event_type  TEXT NOT NULL,
                event_data  TEXT DEFAULT '{}',
                recorded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS bookmarks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                lesson_id   TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, lesson_id)
            );

            CREATE TABLE IF NOT EXISTS certificates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                lesson_id   TEXT NOT NULL,
                track_id    TEXT NOT NULL,
                score       INTEGER DEFAULT 0,
                issued_at   TEXT DEFAULT (datetime('now'))
            );
        """)

        # Ensure default user and progress rows exist
        conn.execute("""
            INSERT OR IGNORE INTO user (id, username) VALUES (1, 'Learner')
        """)
        conn.execute("""
            INSERT OR IGNORE INTO progress (id, user_id) VALUES (1, 1)
        """)
        conn.commit()

        # Migrations for existing databases
        try:
            conn.execute("SELECT current_section FROM lesson_history LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE lesson_history ADD COLUMN current_section INTEGER DEFAULT 0")
            conn.commit()
        try:
            conn.execute("SELECT challenge_streak FROM user LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE user ADD COLUMN challenge_streak INTEGER DEFAULT 0")
            conn.commit()
        try:
            conn.execute("SELECT is_final FROM mission_history LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE mission_history ADD COLUMN is_final INTEGER DEFAULT 0")
            # Legacy rows used stage 999 as the \'mission finished\' sentinel.
            conn.execute("UPDATE mission_history SET is_final=1 WHERE stage>=999")
            conn.commit()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        self._run_repairs()

    # ── Repairs ─────────────────────────────────────────────

    SCHEMA_VERSION = 2

    def _run_repairs(self) -> None:
        """Recompute derived counters that older versions over-counted."""
        conn = self._connect()
        row = conn.execute("SELECT value FROM meta WHERE key=\'schema_version\'").fetchone()
        current = int(row["value"]) if row else 0
        if current >= self.SCHEMA_VERSION:
            return
        try:
            self.recompute_progress_counters()
        except Exception as e:
            logger.warning(f"Progress repair failed: {e}")
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (\'schema_version\', ?)",
            (str(self.SCHEMA_VERSION),)
        )
        conn.commit()

    def recompute_progress_counters(self) -> dict:
        """Rebuild lesson/challenge/mission counters from history tables.

        Earlier releases incremented these on every repeat completion and once
        per mission *stage*, so stored values drift above reality.
        """
        conn = self._connect()
        lessons = conn.execute(
            "SELECT COUNT(DISTINCT lesson_id) c FROM lesson_history WHERE user_id=1 AND completed=1"
        ).fetchone()["c"]
        challenges = conn.execute(
            "SELECT COUNT(DISTINCT challenge_id) c FROM challenge_history WHERE user_id=1 AND solved=1"
        ).fetchone()["c"]
        nohint = conn.execute(
            "SELECT COUNT(DISTINCT challenge_id) c FROM challenge_history "
            "WHERE user_id=1 AND solved=1 AND hints_used=0"
        ).fetchone()["c"]
        missions = conn.execute(
            "SELECT COUNT(DISTINCT mission_id) c FROM mission_history WHERE user_id=1 AND is_final=1"
        ).fetchone()["c"]
        commands = conn.execute(
            "SELECT COUNT(*) c FROM command_history WHERE user_id=1"
        ).fetchone()["c"]
        conn.execute("""
            UPDATE progress SET lessons_completed=?, challenges_solved=?,
                challenges_nohint=?, missions_completed=?, commands_executed=?
            WHERE user_id=1
        """, (lessons, challenges, nohint, missions, commands))
        conn.commit()
        return {"lessons_completed": lessons, "challenges_solved": challenges,
                "challenges_nohint": nohint, "missions_completed": missions,
                "commands_executed": commands}

    # ── User ────────────────────────────────────────────────

    def get_user(self) -> dict:
        row = self.conn.execute("SELECT * FROM user WHERE id=1").fetchone()
        return dict(row) if row else {}

    USER_COLUMNS = frozenset({
        "username", "xp", "level", "rank_title", "streak", "challenge_streak",
        "last_active", "theme", "settings",
    })

    def update_user(self, **kwargs) -> None:
        if not kwargs:
            return
        unknown = set(kwargs) - self.USER_COLUMNS
        if unknown:
            raise ValueError(f"Unknown user column(s): {sorted(unknown)}")
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values())
        self.conn.execute(f"UPDATE user SET {sets} WHERE id=1", vals)
        self.conn.commit()

    def add_xp(self, amount: int) -> dict:
        """Add XP and check for level up. Returns dict with new_level, leveled_up."""
        user = self.get_user()
        new_xp = user.get("xp", 0) + amount
        old_level = user.get("level", 1)
        new_level, rank_title = self._compute_level(new_xp)
        leveled_up = new_level > old_level
        self.update_user(xp=new_xp, level=new_level, rank_title=rank_title,
                         last_active=datetime.now().isoformat())
        return {"xp": new_xp, "level": new_level, "rank_title": rank_title,
                "leveled_up": leveled_up, "xp_gained": amount}

    def _compute_level(self, xp: int) -> tuple[int, str]:
        """Determine level and rank title from XP."""
        thresholds = [
            (50000, 12, "ShellMentor Grandmaster"),
            (32000, 11, "VLSI Investigator"),
            (25000, 10, "Linux Architect"),
            (19000,  9, "Automation Expert"),
            (14000,  8, "Log Investigator"),
            (10000,  7, "Pipeline Master"),
            ( 7000,  6, "Pipeline Builder"),
            ( 4500,  5, "Text Wrangler"),
            ( 2500,  4, "Regex Apprentice"),
            ( 1200,  3, "Pattern Hunter"),
            (  500,  2, "Shell Apprentice"),
            (    0,  1, "Terminal Novice"),
        ]
        for threshold, level, title in thresholds:
            if xp >= threshold:
                return level, title
        return 1, "Terminal Novice"

    def update_streak(self) -> int:
        """Update daily streak. Returns new streak value."""
        user = self.get_user()
        last_active = user.get("last_active", "")
        today = date.today().isoformat()
        streak = user.get("streak", 0)

        if last_active:
            last_date = last_active[:10]
            if last_date == today:
                return streak  # Already active today
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            if last_date == yesterday:
                streak += 1
            else:
                streak = 1  # Reset streak
        else:
            streak = 1

        self.update_user(streak=streak, last_active=datetime.now().isoformat())
        return streak

    # ── Progress ─────────────────────────────────────────────

    def get_progress(self) -> dict:
        row = self.conn.execute("SELECT * FROM progress WHERE user_id=1").fetchone()
        if row:
            d = dict(row)
            d["tracks_completed"] = json.loads(d.get("tracks_completed", "[]"))
            return d
        return {}

    PROGRESS_COLUMNS = frozenset({
        "lessons_completed", "challenges_solved", "missions_completed",
        "quizzes_taken", "quiz_correct", "commands_executed",
        "time_spent_mins", "challenges_nohint",
    })

    def increment_progress(self, **kwargs) -> None:
        """Increment integer progress fields (column names are whitelisted)."""
        unknown = set(kwargs) - self.PROGRESS_COLUMNS
        if unknown:
            raise ValueError(f"Unknown progress column(s): {sorted(unknown)}")
        for field, amount in kwargs.items():
            self.conn.execute(
                f"UPDATE progress SET {field}={field}+? WHERE user_id=1", (amount,)
            )
        self.conn.commit()

    def add_track_completed(self, track_id: str) -> None:
        prog = self.get_progress()
        tracks = prog.get("tracks_completed", [])
        if track_id not in tracks:
            tracks.append(track_id)
            self.conn.execute(
                "UPDATE progress SET tracks_completed=? WHERE user_id=1",
                (json.dumps(tracks),)
            )
            self.conn.commit()

    # ── Lessons ──────────────────────────────────────────────

    def get_completed_lessons(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT lesson_id FROM lesson_history WHERE user_id=1 AND completed=1"
        ).fetchall()
        return {row["lesson_id"] for row in rows}

    def record_lesson_completion(self, lesson_id: str, track_id: str,
                                  score: int, xp: int, time_spent: int) -> None:
        existing = self.conn.execute(
            "SELECT id, completed FROM lesson_history WHERE user_id=1 AND lesson_id=?",
            (lesson_id,)
        ).fetchone()

        first_completion = not (existing and existing["completed"])

        if existing:
            self.conn.execute("""
                UPDATE lesson_history SET completed=1, score=MAX(score,?),
                xp_earned=MAX(xp_earned,?), attempts=attempts+1,
                completed_at=? WHERE id=?
            """, (score, xp, datetime.now().isoformat(), existing["id"]))
        else:
            self.conn.execute("""
                INSERT INTO lesson_history
                (user_id, lesson_id, track_id, completed, score, xp_earned,
                 time_spent, completed_at)
                VALUES (1,?,?,1,?,?,?,?)
            """, (lesson_id, track_id, score, xp, time_spent,
                  datetime.now().isoformat()))

        self.conn.commit()
        self.increment_progress(time_spent_mins=time_spent // 60)
        if first_completion:
            self.increment_progress(lessons_completed=1)

    # ── Challenges ───────────────────────────────────────────

    def get_solved_challenges(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT challenge_id FROM challenge_history WHERE user_id=1 AND solved=1"
        ).fetchall()
        return {row["challenge_id"] for row in rows}

    def record_challenge_attempt(self, challenge_id: str, solved: bool,
                                   xp: int, hints: int, duration: float,
                                   command: str) -> None:
        existing = self.conn.execute(
            "SELECT id, solved, attempts FROM challenge_history WHERE user_id=1 AND challenge_id=?",
            (challenge_id,)
        ).fetchone()

        already_solved = bool(existing["solved"]) if existing else False

        if existing:
            self.conn.execute("""
                UPDATE challenge_history SET
                    solved=MAX(solved,?), attempts=attempts+1,
                    hints_used=hints_used+?,
                    best_time=CASE WHEN ? < best_time OR best_time=0 THEN ? ELSE best_time END,
                    xp_earned=MAX(xp_earned,?),
                    last_command=?,
                    solved_at=CASE WHEN ? AND NOT solved THEN ? ELSE solved_at END
                WHERE id=?
            """, (int(solved), hints, duration, duration, xp, command,
                  int(solved), datetime.now().isoformat(), existing["id"]))
        else:
            self.conn.execute("""
                INSERT INTO challenge_history
                (user_id, challenge_id, solved, xp_earned, hints_used,
                 attempts, best_time, last_command, solved_at)
                VALUES (1,?,?,?,?,1,?,?,?)
            """, (challenge_id, int(solved), xp, hints, duration, command,
                  datetime.now().isoformat() if solved else None))

        self.conn.commit()
        if solved and not already_solved:
            self.increment_progress(challenges_solved=1)
            if hints == 0:
                self.increment_progress(challenges_nohint=1)

    # ── Missions ─────────────────────────────────────────────

    def get_mission_progress(self, mission_id: str) -> int:
        """Return highest stage completed for a mission (excluding the
        mission-completion marker row)."""
        row = self.conn.execute("""
            SELECT MAX(stage) as max_stage FROM mission_history
            WHERE user_id=1 AND mission_id=? AND is_final=0 AND completed=1
        """, (mission_id,)).fetchone()
        return row["max_stage"] or 0

    def get_completed_missions(self) -> set[str]:
        """Missions the user actually finished — not merely started."""
        rows = self.conn.execute(
            "SELECT DISTINCT mission_id FROM mission_history WHERE user_id=1 AND is_final=1"
        ).fetchall()
        return {row["mission_id"] for row in rows}

    def record_mission_stage(self, mission_id: str, stage: int,
                              completed: bool, xp: int) -> None:
        """Record a single completed mission stage. Never touches the
        missions_completed counter — see record_mission_complete()."""
        self.conn.execute("""
            INSERT INTO mission_history
                (user_id, mission_id, stage, completed, is_final, xp_earned, completed_at)
            VALUES (1,?,?,?,0,?,?)
        """, (mission_id, stage, int(completed), xp,
              datetime.now().isoformat() if completed else None))
        self.conn.commit()

    def record_mission_complete(self, mission_id: str, xp: int = 0) -> bool:
        """Mark a mission finished. Returns True if this is the first time."""
        first_time = mission_id not in self.get_completed_missions()
        self.conn.execute("""
            INSERT INTO mission_history
                (user_id, mission_id, stage, completed, is_final, xp_earned, completed_at)
            VALUES (1,?,?,1,1,?,?)
        """, (mission_id, 0, xp, datetime.now().isoformat()))
        self.conn.commit()
        if first_time:
            self.increment_progress(missions_completed=1)
        return first_time

    # ── Achievements ─────────────────────────────────────────

    def get_earned_achievements(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT achievement_id FROM achievements WHERE user_id=1"
        ).fetchall()
        return {row["achievement_id"] for row in rows}

    def award_achievement(self, achievement_id: str, xp: int) -> bool:
        """Award achievement. Returns True only if the row was newly inserted.

        conn.total_changes is cumulative for the whole connection, so it must
        not be used here — cursor.rowcount reports this statement alone.
        """
        try:
            cur = self.conn.execute("""
                INSERT OR IGNORE INTO achievements (user_id, achievement_id, xp_earned)
                VALUES (1,?,?)
            """, (achievement_id, xp))
            self.conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            logger.warning(f"Could not award achievement {achievement_id}: {e}")
            return False

    def check_and_award_achievements(self, achievements_data: list[dict],
                                       context: dict | None = None) -> list[dict]:
        """Check all achievement conditions and award newly earned ones."""
        user = self.get_user()
        progress = self.get_progress()
        earned = self.get_earned_achievements()
        newly_earned = []

        now = datetime.now()
        stats = {
            "total_xp":           user.get("xp", 0),
            "streak":             user.get("streak", 0),
            "lessons_completed":  progress.get("lessons_completed", 0),
            "challenges_solved":  progress.get("challenges_solved", 0),
            "missions_completed": progress.get("missions_completed", 0),
            "challenges_nohint":  progress.get("challenges_nohint", 0),
            "commands_executed":  progress.get("commands_executed", 0),
            "quizzes_taken":      progress.get("quizzes_taken", 0),
            "quiz_correct":       progress.get("quiz_correct", 0),
            "notes_created":      self._count_notes(),
            "tracks_completed":   progress.get("tracks_completed", []),
            "tracks_completed_count": len(progress.get("tracks_completed", [])),
            "current_hour":       now.hour,
            "fastest_solve":      self._fastest_solve_seconds(),
            "longest_pipeline":   self._longest_pipeline(),
            "portfolio_generated": bool(self.get_setting("portfolio_generated", False)),
        }
        if context:
            stats.update(context)

        for ach in achievements_data:
            aid = ach["id"]
            if aid in earned:
                continue

            trigger = ach.get("trigger", "")
            awarded = self._evaluate_trigger(trigger, stats, earned)

            if awarded:
                if self.award_achievement(aid, ach.get("xp_reward", 0)):
                    newly_earned.append(ach)

        # NB: the XP bonus is *not* applied here. ProgressEngine awards it so
        # that a level-up triggered by achievement XP still fires its event.
        return newly_earned

    def _fastest_solve_seconds(self) -> float:
        """Best (lowest) recorded solve time, or 0.0 when nothing is solved."""
        row = self.conn.execute(
            "SELECT MIN(best_time) t FROM challenge_history "
            "WHERE user_id=1 AND solved=1 AND best_time > 0"
        ).fetchone()
        return float(row["t"]) if row and row["t"] is not None else 0.0

    def _longest_pipeline(self) -> int:
        """Most pipe-separated stages seen in any recorded command."""
        rows = self.conn.execute(
            "SELECT command FROM command_history WHERE user_id=1 AND command LIKE \'%|%\'"
        ).fetchall()
        best = 0
        for r in rows:
            best = max(best, len([p for p in r["command"].split("|") if p.strip()]))
        return best

    def _evaluate_trigger(self, trigger: str, stats: dict, earned: set) -> bool:
        """Evaluate a simple trigger expression safely without eval()."""
        import re

        # Handle compound triggers (AND with " and ", OR with " or ")
        if " and " in trigger:
            parts = trigger.split(" and ")
            return all(self._evaluate_trigger(p.strip(), stats, earned) for p in parts)
        if " or " in trigger:
            parts = trigger.split(" or ")
            return any(self._evaluate_trigger(p.strip(), stats, earned) for p in parts)

        # Track id -> the trigger name used in achievements.json. Every track
        # in lessons.json must appear here or its achievement is unreachable.
        track_triggers = {
            "track_grep_complete":       "linux_fundamentals",
            "track_awk_complete":        "text_processing",
            "track_regex_complete":      "regex_academy",
            "track_pipelines_complete":  "shell_pipelines",
            "track_logs_complete":       "log_analysis",
            "track_vlsi_complete":       "vlsi_track",
            "track_scripting_complete":  "shell_scripting",
            "track_filesystem_complete": "file_system",
            "track_process_complete":    "process_management",
            "track_networking_complete": "networking",
            "track_git_complete":        "git_basics",
            "track_useradmin_complete":  "user_admin",
            "track_textadv_complete":    "text_advanced",
            "track_dataanalysis_complete": "data_analysis",
        }
        if trigger in track_triggers:
            return track_triggers[trigger] in stats.get("tracks_completed", [])

        # Handle special boolean triggers. None of these may be a bare True:
        # a trigger that is always satisfied fires on the first XP award and
        # hands out the achievement for nothing.
        boolean_triggers = {
            # A perfect quiz run, taken without hints.
            "quiz_perfect_nohint":   lambda s, e: (
                s.get("quizzes_taken", 0) >= 5
                and s.get("quiz_correct", 0) == s.get("quizzes_taken", 0)
            ),
            # Solved a challenge in under two minutes.
            "challenge_fast":        lambda s, e: 0 < s.get("fastest_solve", 0) < 120,
            # Built a pipeline of at least five stages.
            "pipeline_5_commands":   lambda s, e: s.get("longest_pipeline", 0) >= 5,
            "all_missions_complete": lambda s, e: s.get("missions_completed", 0) >= 10,
            "portfolio_generated":   lambda s, e: bool(s.get("portfolio_generated", False)),
            "all_tracks_complete":   lambda s, e: s.get("tracks_completed_count", 0) >= 14,
            "lesson_before_8am":     lambda s, e: 0 <= s.get("current_hour", 12) < 8,
            "lesson_after_midnight": lambda s, e: 0 <= s.get("current_hour", 12) < 5,
        }
        if trigger in boolean_triggers:
            return boolean_triggers[trigger](stats, earned)

        # Direct stat comparisons: "lessons_completed >= 1"
        match = re.match(r'^(\w+)\s*(>=|<=|>|<|==)\s*(\d+)$', trigger.strip())
        if match:
            stat_name, op, threshold = match.group(1), match.group(2), int(match.group(3))
            value = stats.get(stat_name, 0)
            if op == ">=":
                return value >= threshold
            elif op == "<=":
                return value <= threshold
            elif op == ">":
                return value > threshold
            elif op == "<":
                return value < threshold
            elif op == "==":
                return value == threshold

        return False

    def _count_notes(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as c FROM notes WHERE user_id=1").fetchone()
        return row["c"] if row else 0

    # ── Notes ────────────────────────────────────────────────

    def create_note(self, title: str, content: str,
                    tags: list[str] = None, category: str = "general") -> int:
        cur = self.conn.execute("""
            INSERT INTO notes (user_id, title, content, tags, category)
            VALUES (1,?,?,?,?)
        """, (title, content, json.dumps(tags or []), category))
        self.conn.commit()
        return cur.lastrowid

    def get_notes(self, search: str = "") -> list[dict]:
        if search:
            rows = self.conn.execute("""
                SELECT * FROM notes WHERE user_id=1
                AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                ORDER BY updated_at DESC
            """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM notes WHERE user_id=1 ORDER BY updated_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["tags"] = json.loads(d.get("tags", "[]"))
            result.append(d)
        return result

    def update_note(self, note_id: int, title: str, content: str) -> None:
        self.conn.execute("""
            UPDATE notes SET title=?, content=?, updated_at=? WHERE id=? AND user_id=1
        """, (title, content, datetime.now().isoformat(), note_id))
        self.conn.commit()

    def delete_note(self, note_id: int) -> None:
        self.conn.execute("DELETE FROM notes WHERE id=? AND user_id=1", (note_id,))
        self.conn.commit()

    # ── Command History ──────────────────────────────────────

    def record_command(self, command: str, output: str, exit_code: int,
                       context: str = "playground", duration_ms: float = 0) -> None:
        stored_output = output[:2000]
        if len(output) > 2000:
            stored_output += "\n[... output truncated ...]"
        self.conn.execute("""
            INSERT INTO command_history (user_id, command, output, exit_code, context, duration_ms)
            VALUES (1,?,?,?,?,?)
        """, (command, stored_output, exit_code, context, duration_ms))
        self.conn.commit()
        self.increment_progress(commands_executed=1)

    def get_command_history(self, limit: int = 100, context: str = "") -> list[dict]:
        if context:
            rows = self.conn.execute("""
                SELECT * FROM command_history WHERE user_id=1 AND context=?
                ORDER BY id DESC LIMIT ?
            """, (context, limit)).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT * FROM command_history WHERE user_id=1
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ── Sessions ─────────────────────────────────────────────

    def start_session(self, name: str = "") -> int:
        cur = self.conn.execute("""
            INSERT INTO sessions (user_id, name) VALUES (1,?)
        """, (name or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",))
        self.conn.commit()
        return cur.lastrowid

    def append_session_command(self, session_id: int, command: str, output: str) -> None:
        row = self.conn.execute(
            "SELECT commands, outputs, total_cmds FROM sessions WHERE id=?",
            (session_id,)
        ).fetchone()
        if row:
            cmds = json.loads(row["commands"])
            outs = json.loads(row["outputs"])
            cmds.append(command)
            outs.append(output)
            self.conn.execute("""
                UPDATE sessions SET commands=?, outputs=?, total_cmds=?
                WHERE id=?
            """, (json.dumps(cmds), json.dumps(outs), len(cmds), session_id))
            self.conn.commit()

    def close_session(self, session_id: int) -> None:
        self.conn.execute(
            "UPDATE sessions SET ended_at=? WHERE id=?",
            (datetime.now().isoformat(), session_id)
        )
        self.conn.commit()

    def get_sessions(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE user_id=1 ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Analytics ────────────────────────────────────────────

    def record_event(self, event_type: str, data: dict = None) -> None:
        self.conn.execute("""
            INSERT INTO analytics (user_id, event_type, event_data)
            VALUES (1,?,?)
        """, (event_type, json.dumps(data or {})))
        self.conn.commit()

    def get_analytics_summary(self) -> dict:
        """Build a comprehensive analytics summary."""
        user = self.get_user()
        progress = self.get_progress()

        # Top commands used
        top_cmds = self.conn.execute("""
            SELECT SUBSTR(command, 1, INSTR(command||' ', ' ')-1) as cmd, COUNT(*) as n
            FROM command_history WHERE user_id=1
            GROUP BY cmd ORDER BY n DESC LIMIT 10
        """).fetchall()

        # Lessons per track
        per_track = self.conn.execute("""
            SELECT track_id, COUNT(*) as n
            FROM lesson_history WHERE user_id=1 AND completed=1
            GROUP BY track_id
        """).fetchall()

        accuracy = 0
        qp = progress.get("quizzes_taken", 0)
        qc = progress.get("quiz_correct", 0)
        if qp > 0:
            accuracy = (qc / qp) * 100

        # Weekly activity (last 7 days)
        weekly_activity = self.conn.execute("""
            SELECT DATE(executed_at) as day, COUNT(*) as n
            FROM command_history WHERE user_id=1
            AND executed_at >= datetime('now', '-7 days')
            GROUP BY day ORDER BY day
        """).fetchall()

        # Challenge performance by difficulty
        ch_by_diff = self.conn.execute("""
            SELECT 
                CASE 
                    WHEN challenge_id IN (SELECT challenge_id FROM challenge_history WHERE user_id=1 AND solved=1) THEN 'solved'
                    ELSE 'attempted'
                END as status,
                COUNT(*) as n
            FROM challenge_history WHERE user_id=1
            GROUP BY status
        """).fetchall()

        # Average solve time
        avg_time = self.conn.execute("""
            SELECT AVG(best_time) as avg_time, MIN(best_time) as best_time
            FROM challenge_history WHERE user_id=1 AND solved=1 AND best_time > 0
        """).fetchone()

        return {
            "user": dict(user),
            "progress": dict(progress),
            "accuracy": accuracy,
            "top_commands": [dict(r) for r in top_cmds],
            "lessons_per_track": [dict(r) for r in per_track],
            "weekly_activity": [dict(r) for r in weekly_activity],
            "challenge_stats": {
                "solved": sum(1 for r in ch_by_diff if r["status"] == "solved"),
                "attempted": sum(1 for r in ch_by_diff if r["status"] == "attempted"),
            },
            "avg_solve_time": dict(avg_time) if avg_time else {"avg_time": 0, "best_time": 0},
        }

    # ── Settings ─────────────────────────────────────────────

    def get_setting(self, key: str, default: Any = None) -> Any:
        user = self.get_user()
        settings = json.loads(user.get("settings", "{}"))
        return settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        user = self.get_user()
        settings = json.loads(user.get("settings", "{}"))
        settings[key] = value
        self.update_user(settings=json.dumps(settings))

    def get_theme(self) -> str:
        user = self.get_user()
        return user.get("theme", "professional_dark")

    def set_theme(self, theme_name: str) -> None:
        self.update_user(theme=theme_name)

    def record_quiz_result(self, correct: bool) -> None:
        self.increment_progress(quizzes_taken=1)
        if correct:
            self.increment_progress(quiz_correct=1)

    # ── Bookmarks ─────────────────────────────────────────────

    def toggle_bookmark(self, lesson_id: str) -> bool:
        """Toggle bookmark for a lesson. Returns True if now bookmarked."""
        existing = self.conn.execute(
            "SELECT id FROM bookmarks WHERE user_id=1 AND lesson_id=?",
            (lesson_id,)
        ).fetchone()
        if existing:
            self.conn.execute(
                "DELETE FROM bookmarks WHERE id=?", (existing["id"],)
            )
            self.conn.commit()
            return False
        self.conn.execute(
            "INSERT OR IGNORE INTO bookmarks (user_id, lesson_id) VALUES (1,?)",
            (lesson_id,)
        )
        self.conn.commit()
        return True

    def is_bookmarked(self, lesson_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM bookmarks WHERE user_id=1 AND lesson_id=?",
            (lesson_id,)
        ).fetchone()
        return row is not None

    def get_bookmarked_lessons(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT lesson_id FROM bookmarks WHERE user_id=1"
        ).fetchall()
        return {row["lesson_id"] for row in rows}

    # ── Certificates ─────────────────────────────────────────

    def issue_certificate(self, lesson_id: str, track_id: str, score: int) -> int:
        """Issue a certificate for lesson completion. Returns cert ID."""
        cur = self.conn.execute(
            "INSERT INTO certificates (user_id, lesson_id, track_id, score) VALUES (1,?,?,?)",
            (lesson_id, track_id, score)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_certificates(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM certificates WHERE user_id=1 ORDER BY issued_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def has_certificate(self, lesson_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM certificates WHERE user_id=1 AND lesson_id=?",
            (lesson_id,)
        ).fetchone()
        return row is not None

    # ── Lesson Bookmark (resume position) ────────────────────

    def save_lesson_position(self, lesson_id: str, section: int,
                             track_id: str = "") -> None:
        """Save current section for resume.

        Inserts a placeholder history row when the lesson has never been
        completed — otherwise there is nothing to UPDATE and the position is
        silently dropped.
        """
        cur = self.conn.execute("""
            UPDATE lesson_history SET current_section=?
            WHERE user_id=1 AND lesson_id=?
        """, (section, lesson_id))
        if cur.rowcount == 0:
            self.conn.execute("""
                INSERT INTO lesson_history
                    (user_id, lesson_id, track_id, completed, current_section, attempts)
                VALUES (1,?,?,0,?,0)
            """, (lesson_id, track_id, section))
        self.conn.commit()

    def get_lesson_position(self, lesson_id: str) -> int:
        """Get saved section for resume."""
        row = self.conn.execute(
            "SELECT current_section FROM lesson_history WHERE user_id=1 AND lesson_id=?",
            (lesson_id,)
        ).fetchone()
        if row and row["current_section"]:
            return row["current_section"]
        return 0

    def get_challenge_streak(self) -> int:
        user = self.get_user()
        return user.get("challenge_streak", 0)

    def increment_challenge_streak(self) -> int:
        user = self.get_user()
        streak = user.get("challenge_streak", 0) + 1
        self.update_user(challenge_streak=streak)
        return streak

    def reset_challenge_streak(self) -> None:
        self.update_user(challenge_streak=0)

    def get_recent_challenge_history(self, limit: int = 20) -> list[dict]:
        """Get recent challenge attempts."""
        rows = self.conn.execute("""
            SELECT challenge_id, solved, hints_used, best_time, xp_earned
            FROM challenge_history WHERE user_id=1
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def reset_all_progress(self) -> None:
        """Reset all user progress, achievements, and history. Preserves theme and settings."""
        user = self.get_user()
        theme = user.get("theme", "professional_dark")
        settings = user.get("settings", "{}")
        self.conn.executescript("""
            DELETE FROM lesson_history;
            DELETE FROM challenge_history;
            DELETE FROM mission_history;
            DELETE FROM achievements;
            DELETE FROM command_history;
            DELETE FROM sessions;
            DELETE FROM bookmarks;
            DELETE FROM certificates;
            UPDATE user SET xp=0, level=1, rank_title='Terminal Novice', streak=0,
                challenge_streak=0, last_active=NULL;
            UPDATE progress SET lessons_completed=0, challenges_solved=0,
                missions_completed=0, quizzes_taken=0, quiz_correct=0,
                commands_executed=0, time_spent_mins=0, challenges_nohint=0,
                tracks_completed='[]';
        """)
        self.update_user(theme=theme, settings=settings)
        self.conn.commit()
        # Personal notes are deliberately preserved; only progress is reset.
        self.set_setting("portfolio_generated", False)
