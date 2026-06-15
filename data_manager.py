"""
ShellMentor - data_manager.py
SQLite-backed persistence: user progress, sessions, notes, analytics, settings.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

logger = logging.getLogger("shellmentor")

DB_PATH = Path(user_data_dir("ShellMentor", "AndGate")) / "shellmentor.db"


class DataManager:
    """Central SQLite data store for ShellMentor."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
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
                last_active   TEXT,
                created_at    TEXT DEFAULT (datetime('now')),
                github_token  TEXT DEFAULT '',
                github_user   TEXT DEFAULT '',
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
                attempts    INTEGER DEFAULT 1
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
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER DEFAULT 1,
                event_type  TEXT NOT NULL,
                event_data  TEXT DEFAULT '{}',
                recorded_at TEXT DEFAULT (datetime('now'))
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

    # ── User ────────────────────────────────────────────────

    def get_user(self) -> dict:
        row = self.conn.execute("SELECT * FROM user WHERE id=1").fetchone()
        return dict(row) if row else {}

    def update_user(self, **kwargs) -> None:
        if not kwargs:
            return
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
            yesterday = (date.today() - __import__('datetime').timedelta(days=1)).isoformat()
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

    def increment_progress(self, **kwargs) -> None:
        """Increment integer progress fields."""
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
            "SELECT id FROM lesson_history WHERE user_id=1 AND lesson_id=?",
            (lesson_id,)
        ).fetchone()

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
        self.increment_progress(lessons_completed=1, time_spent_mins=time_spent // 60)

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

        if existing:
            already_solved = existing["solved"]
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
        if solved:
            self.increment_progress(challenges_solved=1)
            if hints == 0:
                self.increment_progress(challenges_nohint=1)

    # ── Missions ─────────────────────────────────────────────

    def get_mission_progress(self, mission_id: str) -> int:
        """Return highest stage completed for a mission."""
        row = self.conn.execute("""
            SELECT MAX(stage) as max_stage FROM mission_history
            WHERE user_id=1 AND mission_id=?
        """, (mission_id,)).fetchone()
        return row["max_stage"] or 0

    def get_completed_missions(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT mission_id FROM mission_history WHERE user_id=1 AND completed=1"
        ).fetchall()
        return {row["mission_id"] for row in rows}

    def record_mission_stage(self, mission_id: str, stage: int,
                              completed: bool, xp: int) -> None:
        self.conn.execute("""
            INSERT INTO mission_history (user_id, mission_id, stage, completed, xp_earned, completed_at)
            VALUES (1,?,?,?,?,?)
        """, (mission_id, stage, int(completed), xp,
              datetime.now().isoformat() if completed else None))
        self.conn.commit()
        if completed:
            self.increment_progress(missions_completed=1)

    # ── Achievements ─────────────────────────────────────────

    def get_earned_achievements(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT achievement_id FROM achievements WHERE user_id=1"
        ).fetchall()
        return {row["achievement_id"] for row in rows}

    def award_achievement(self, achievement_id: str, xp: int) -> bool:
        """Award achievement. Returns True if newly earned."""
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO achievements (user_id, achievement_id, xp_earned)
                VALUES (1,?,?)
            """, (achievement_id, xp))
            self.conn.commit()
            return self.conn.total_changes > 0
        except Exception:
            return False

    def check_and_award_achievements(self, achievements_data: list[dict]) -> list[dict]:
        """Check all achievement conditions and award newly earned ones."""
        user = self.get_user()
        progress = self.get_progress()
        earned = self.get_earned_achievements()
        newly_earned = []

        stats = {
            "total_xp":          user.get("xp", 0),
            "streak":            user.get("streak", 0),
            "lessons_completed": progress.get("lessons_completed", 0),
            "challenges_solved": progress.get("challenges_solved", 0),
            "missions_completed":progress.get("missions_completed", 0),
            "challenges_nohint": progress.get("challenges_nohint", 0),
            "notes_created":     self._count_notes(),
        }

        for ach in achievements_data:
            aid = ach["id"]
            if aid in earned:
                continue

            trigger = ach.get("trigger", "")
            awarded = self._evaluate_trigger(trigger, stats, earned)

            if awarded:
                if self.award_achievement(aid, ach.get("xp_reward", 0)):
                    newly_earned.append(ach)
                    # Add the XP bonus
                    self.add_xp(ach.get("xp_reward", 0))

        return newly_earned

    def _evaluate_trigger(self, trigger: str, stats: dict, earned: set) -> bool:
        """Evaluate a simple trigger expression."""
        try:
            # Direct stat comparisons: "lessons_completed >= 1"
            for stat, value in stats.items():
                trigger = trigger.replace(stat, str(value))
            # Safe eval of simple numeric comparisons
            if any(op in trigger for op in [">=", "<=", ">", "<", "=="]):
                return bool(eval(trigger))  # noqa: S307 - controlled expressions only
        except Exception:
            pass
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
        self.conn.execute("""
            INSERT INTO command_history (user_id, command, output, exit_code, context, duration_ms)
            VALUES (1,?,?,?,?,?)
        """, (command, output[:2000], exit_code, context, duration_ms))
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

        return {
            "user": dict(user),
            "progress": dict(progress),
            "accuracy": accuracy,
            "top_commands": [dict(r) for r in top_cmds],
            "lessons_per_track": [dict(r) for r in per_track],
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
