"""
ShellMentor - learning.py
Lesson delivery engine: tracks, lessons, quizzes, command translator.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from utils import DATA_DIR, load_json, difficulty_icon, difficulty_color
from data_manager import DataManager

logger = logging.getLogger("shellmentor")


@dataclass
class QuizSession:
    lesson_id: str
    questions: list[dict]
    current_idx: int = 0
    correct: int = 0
    total: int = 0
    used_hints: bool = False
    started_at: float = field(default_factory=time.time)
    answers: list[dict] = field(default_factory=list)

    @property
    def current_question(self) -> dict | None:
        if self.current_idx < len(self.questions):
            return self.questions[self.current_idx]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_idx >= len(self.questions)

    @property
    def score_pct(self) -> float:
        return (self.correct / self.total * 100) if self.total > 0 else 0

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    def answer(self, user_answer: str) -> dict:
        q = self.current_question
        if not q:
            return {"correct": False, "message": "No question active"}

        correct_answer = q.get("answer", "")
        is_correct = user_answer.strip() == correct_answer.strip()
        self.total += 1
        if is_correct:
            self.correct += 1

        result = {
            "correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "explanation": q.get("explanation", ""),
            "xp": q.get("xp", 10) if is_correct else 0,
        }
        self.answers.append(result)
        self.current_idx += 1
        return result


@dataclass
class LessonSession:
    lesson: dict
    track_id: str
    started_at: float = field(default_factory=time.time)
    current_section: int = 0
    exercises_done: list[str] = field(default_factory=list)
    quiz_session: QuizSession | None = None

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    @property
    def progress_pct(self) -> float:
        sections = len(self.lesson.get("sections", []))
        if sections == 0:
            return 100.0
        return min(100.0, (self.current_section / sections) * 100)


class LearningEngine:
    """Manages tracks, lessons, quizzes, and learning state."""

    def __init__(self, db: DataManager):
        self.db = db
        self._data = self._load_data()
        self._active_lesson: LessonSession | None = None

    def _load_data(self) -> dict:
        return load_json(DATA_DIR / "lessons.json")

    def reload(self) -> None:
        self._data = self._load_data()

    # ── Track / Lesson Access ─────────────────────────────────

    def get_tracks(self) -> list[dict]:
        return self._data.get("tracks", [])

    def get_track(self, track_id: str) -> dict | None:
        return next((t for t in self.get_tracks() if t["id"] == track_id), None)

    def get_lesson(self, lesson_id: str) -> dict | None:
        for track in self.get_tracks():
            for lesson in track.get("lessons", []):
                if lesson["id"] == lesson_id:
                    return lesson, track["id"]
        return None, None

    def get_track_lessons(self, track_id: str) -> list[dict]:
        track = self.get_track(track_id)
        if not track:
            return []
        completed = self.db.get_completed_lessons()
        lessons = []
        for i, lesson in enumerate(track.get("lessons", [])):
            d = dict(lesson)
            d["completed"] = lesson["id"] in completed
            d["locked"] = (i > 0 and
                           track["lessons"][i-1]["id"] not in completed)
            lessons.append(d)
        return lessons

    def get_all_track_stats(self) -> list[dict]:
        """Return tracks with completion stats."""
        completed = self.db.get_completed_lessons()
        result = []
        for track in self.get_tracks():
            lessons = track.get("lessons", [])
            total = len(lessons)
            done = sum(1 for l in lessons if l["id"] in completed)
            result.append({
                **track,
                "lessons_total": total,
                "lessons_done":  done,
                "pct_complete":  (done / total * 100) if total > 0 else 0,
                "locked":        False,  # tracks are always accessible
            })
        return result

    # ── Lesson Session ────────────────────────────────────────

    def start_lesson(self, lesson_id: str) -> LessonSession | None:
        lesson, track_id = self.get_lesson(lesson_id)
        if not lesson:
            return None
        self._active_lesson = LessonSession(lesson=lesson, track_id=track_id)
        return self._active_lesson

    @property
    def active_lesson(self) -> LessonSession | None:
        return self._active_lesson

    def advance_section(self) -> bool:
        """Advance to next section. Returns True if more sections remain."""
        if not self._active_lesson:
            return False
        sections = self._active_lesson.lesson.get("sections", [])
        if self._active_lesson.current_section < len(sections):
            self._active_lesson.current_section += 1
            return self._active_lesson.current_section < len(sections)
        return False

    def start_quiz(self) -> QuizSession | None:
        """Start quiz for the active lesson."""
        if not self._active_lesson:
            return None
        questions = self._active_lesson.lesson.get("quiz", [])
        if not questions:
            return None
        session = QuizSession(
            lesson_id=self._active_lesson.lesson["id"],
            questions=questions
        )
        self._active_lesson.quiz_session = session
        return session

    def complete_lesson(self, score: int) -> dict:
        """Mark active lesson as complete and return XP info."""
        if not self._active_lesson:
            return {}
        lesson = self._active_lesson.lesson
        xp = lesson.get("xp_reward", 100)
        time_spent = int(self._active_lesson.elapsed_seconds)
        self.db.record_lesson_completion(
            lesson["id"], self._active_lesson.track_id,
            score, xp, time_spent
        )
        result = {"xp": xp, "lesson": lesson["title"], "time": time_spent}
        self._active_lesson = None
        return result

    # ── Exercise Validation ───────────────────────────────────

    def validate_exercise(self, exercise: dict, user_command: str,
                           actual_output: str) -> dict:
        """Validate a lesson exercise response."""
        solution = exercise.get("solution", "")
        # Structural similarity check (not exact match, check key command elements)
        user_cmd = user_command.strip().lower()
        sol_cmd  = solution.strip().lower()

        # Extract key parts: command name, flags, file
        import shlex
        try:
            user_tokens = set(shlex.split(user_cmd))
            sol_tokens  = set(shlex.split(sol_cmd))
            overlap = len(user_tokens & sol_tokens) / max(len(sol_tokens), 1)
            correct = overlap >= 0.6 or user_cmd == sol_cmd
        except Exception:
            correct = False

        return {
            "correct":  correct,
            "solution": solution,
            "hint":     exercise.get("hint", ""),
            "xp":       exercise.get("xp", 20) if correct else 0,
        }

    # ── Command Translator ────────────────────────────────────

    TRANSLATIONS: dict[str, dict] = {
        "find lines matching pattern": {
            "grep": "grep 'PATTERN' file.txt",
            "sed":  "sed -n '/PATTERN/p' file.txt",
            "awk":  "awk '/PATTERN/' file.txt",
            "rg":   "rg 'PATTERN' file.txt",
        },
        "count matching lines": {
            "grep": "grep -c 'PATTERN' file.txt",
            "awk":  "awk '/PATTERN/{n++} END{print n}' file.txt",
            "rg":   "rg -c 'PATTERN' file.txt",
        },
        "replace text": {
            "sed":  "sed 's/OLD/NEW/g' file.txt",
            "awk":  "awk '{gsub(/OLD/,\"NEW\"); print}' file.txt",
            "perl": "perl -pe 's/OLD/NEW/g' file.txt",
        },
        "extract column": {
            "cut":  "cut -d',' -f2 file.csv",
            "awk":  "awk -F',' '{print $2}' file.csv",
            "sed":  "sed 's/[^,]*,//;s/,.*//' file.csv",
        },
        "count unique values": {
            "sort|uniq": "sort file.txt | uniq -c | sort -rn",
            "awk":       "awk '{count[$0]++} END{for(k in count) print count[k],k}' file.txt | sort -rn",
        },
        "delete lines matching pattern": {
            "sed":  "sed '/PATTERN/d' file.txt",
            "grep": "grep -v 'PATTERN' file.txt",
            "awk":  "awk '!/PATTERN/' file.txt",
        },
        "print specific lines": {
            "sed":  "sed -n '5,10p' file.txt",
            "awk":  "awk 'NR>=5 && NR<=10' file.txt",
            "head": "head -10 file.txt | tail -6",
        },
    }

    def get_translations(self, task: str) -> dict | None:
        """Get equivalent commands for a task."""
        task_lower = task.lower()
        for key, val in self.TRANSLATIONS.items():
            if any(word in task_lower for word in key.split()):
                return {"task": key, "equivalents": val}
        return None

    def get_all_translations(self) -> dict:
        return self.TRANSLATIONS

    # ── Search ────────────────────────────────────────────────

    def search(self, query: str) -> list[dict]:
        """Search across all lessons, tracks, and commands."""
        query_lower = query.lower()
        results = []

        for track in self.get_tracks():
            for lesson in track.get("lessons", []):
                score = 0
                if query_lower in lesson["title"].lower():
                    score += 10
                if query_lower in lesson.get("introduction", "").lower():
                    score += 5
                if any(query_lower in tag for tag in lesson.get("tags", [])):
                    score += 8
                for section in lesson.get("sections", []):
                    if query_lower in section.get("content", "").lower():
                        score += 3
                    if query_lower in section.get("example", "").lower():
                        score += 4

                if score > 0:
                    results.append({
                        "type": "lesson",
                        "id": lesson["id"],
                        "track_id": track["id"],
                        "title": lesson["title"],
                        "subtitle": track["name"],
                        "icon": lesson.get("icon", "📖"),
                        "score": score,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:20]

    # ── Regex Visualizer ──────────────────────────────────────

    def explain_regex(self, pattern: str) -> list[dict]:
        """Break down a regex pattern into explained components."""
        explanations = []
        i = 0
        while i < len(pattern):
            ch = pattern[i]

            if ch == '^':
                explanations.append({"token": "^", "meaning": "Start of line"})
            elif ch == '$':
                explanations.append({"token": "$", "meaning": "End of line"})
            elif ch == '.':
                explanations.append({"token": ".", "meaning": "Any single character (except newline)"})
            elif ch == '*':
                explanations.append({"token": "*", "meaning": "Zero or more of the preceding"})
            elif ch == '+':
                explanations.append({"token": "+", "meaning": "One or more of the preceding"})
            elif ch == '?':
                explanations.append({"token": "?", "meaning": "Zero or one of the preceding"})
            elif ch == '|':
                explanations.append({"token": "|", "meaning": "OR — match either side"})
            elif ch == '\\':
                if i + 1 < len(pattern):
                    next_ch = pattern[i+1]
                    meanings = {
                        'd': 'Any digit [0-9]',
                        'D': 'Any non-digit',
                        'w': 'Word character [a-zA-Z0-9_]',
                        'W': 'Non-word character',
                        's': 'Whitespace',
                        'S': 'Non-whitespace',
                        'b': 'Word boundary',
                        'n': 'Newline',
                        't': 'Tab',
                        '.': 'Literal dot',
                        '*': 'Literal asterisk',
                        '+': 'Literal plus',
                        '(': 'Literal parenthesis',
                        ')': 'Literal parenthesis',
                        '[': 'Literal bracket',
                    }
                    meaning = meanings.get(next_ch, f'Escaped character: {next_ch}')
                    explanations.append({"token": f"\\{next_ch}", "meaning": meaning})
                    i += 1
            elif ch == '[':
                end = pattern.find(']', i)
                if end != -1:
                    cls = pattern[i:end+1]
                    explanations.append({"token": cls, "meaning": f"Character class: matches one of {cls}"})
                    i = end
            elif ch == '(':
                explanations.append({"token": "(", "meaning": "Start of capture group"})
            elif ch == ')':
                explanations.append({"token": ")", "meaning": "End of capture group"})
            elif ch == '{':
                end = pattern.find('}', i)
                if end != -1:
                    quant = pattern[i:end+1]
                    explanations.append({"token": quant, "meaning": f"Quantifier: repeat {quant}"})
                    i = end
            else:
                # Literal character(s)
                explanations.append({"token": ch, "meaning": f"Literal character: '{ch}'"})

            i += 1

        return explanations

    # ── Recommended Learning Path ─────────────────────────────

    def get_recommended_next(self) -> dict | None:
        """Return the next recommended lesson for the user."""
        completed = self.db.get_completed_lessons()
        for track in sorted(self.get_tracks(), key=lambda t: t.get("order", 99)):
            for lesson in track.get("lessons", []):
                if lesson["id"] not in completed:
                    return {
                        "lesson": lesson,
                        "track": track,
                        "reason": "Next in sequence"
                    }
        return None
