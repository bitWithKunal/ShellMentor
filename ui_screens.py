"""
ShellMentor - ui_screens.py
Primary navigation screens: Dashboard, Lessons, Quiz, Playground, Notes,
Analytics, Settings and the first-run Environment Scan.

Challenge / Mission / Achievement screens live in ui_activities.py.
Shared widgets, BaseScreen and modals live in ui_core.py.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.syntax import Syntax
from rich.markdown import Markdown

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container, Horizontal, Vertical, ScrollableContainer, Grid
)
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label,
    ListItem, ListView, Markdown as MarkdownWidget,
    ProgressBar, RichLog, Rule, Select, Static,
    TabbedContent, TabPane, Tabs, Tab, TextArea, Tree, Checkbox, RadioButton, RadioSet
)

from data_manager import DataManager
from learning import LearningEngine
from challenge import ChallengeEngine
from playground import PlaygroundEngine
from progress import ProgressEngine, LevelUpEvent, XPEvent
from utils import (
    detect_system, SystemInfo, get_install_command,
    load_yaml, THEMES_DIR, difficulty_icon, difficulty_color,
    rarity_color, format_xp, format_duration, truncate, APP_VERSION, APP_NAME
)

from ui_core import (
    NavButton, NavigationSidebar, BaseScreen,
    XPBar, StatCard, SectionHeader,
    LevelUpModal, AchievementModal, HintModal, ConfirmModal,
)

logger = logging.getLogger("shellmentor")


class DashboardScreen(BaseScreen):
    """Main dashboard — Professional compact single-screen overview with ASCII art and animations."""

    DEFAULT_CSS = """
    #dashboard-scroll {
        background: #0a0e14;
        padding: 0;
        height: 1fr;
    }
    #dash-body {
        padding: 1 2;
        height: auto;
    }
    .logo-text {
        text-style: bold;
        color: #00d4ff;
        text-align: center;
    }
    .header-glow {
        text-style: bold;
        color: #89b4fa;
    }
    """

    def __init__(self):
        super().__init__(screen_name="dashboard")
        self._frame = 0
        self._animation_timer = None
        self._data_timer = None
        self._cached_stats = None
        self._cached_next_rank = None
        self._cached_recommended = None

    def render_content(self) -> ComposeResult:
        yield ScrollableContainer(
            Static(id="dash-body"),
            id="dashboard-scroll",
        )

    def on_mount(self) -> None:
        self._refresh_dashboard_data()
        self._start_animation()

    def _start_animation(self) -> None:
        """Start animated counter for dashboard."""
        self._animation_timer = self.set_interval(1.0, self._update_animated_effects)
        self._data_timer = self.set_interval(5.0, self._refresh_dashboard_data)

    def _update_animated_effects(self) -> None:
        """Update animated elements on dashboard using cached data."""
        self._frame += 1
        if self._cached_stats:
            self._render_dashboard()

    def _refresh_dashboard_data(self) -> None:
        self._load_dashboard_data_async()

    @work(exclusive=True)
    async def _load_dashboard_data_async(self) -> None:
        app = self.app
        self._cached_stats = app.progress_engine.get_dashboard_stats()
        self._cached_next_rank = app.progress_engine.get_next_rank_info()
        self._cached_recommended = app.learning_engine.get_recommended_next()
        self._render_dashboard()

    def _render_dashboard(self) -> None:
        stats = self._cached_stats
        next_rank = self._cached_next_rank
        recommended = self._cached_recommended
        if not stats:
            return

        app = self.app
        try:
            username = (app.db.get_user().get("username") or "").strip() or "Learner"
        except Exception:
            username = "Learner"

        body = self.query_one("#dash-body", Static)

        # ── helpers ────────────────────────────────────────────────────
        pct = int(next_rank.get("progress_pct", 0))
        xp_needed = next_rank.get("xp_needed", 0)
        streak = stats["streak"]
        filled = int(pct / 5)

        # Animated progress bar (pulsing effect)
        pulse = self._frame % 4
        if pulse == 0:
            bar_fill = "[cyan]" + "█" * filled + "[/cyan]"
        elif pulse == 1:
            bar_fill = "[bold cyan]" + "█" * filled + "[/bold cyan]"
        elif pulse == 2:
            bar_fill = "[bright_cyan]" + "█" * filled + "[/bright_cyan]"
        else:
            bar_fill = "[cyan]" + "█" * filled + "[/cyan]"

        bar = bar_fill + "[grey30]" + "░" * (20 - filled) + "[/grey30]"

        # Animated streak indicators
        if streak > 0:
            streak_anim = self._frame % 3
            if streak_anim == 0:
                streak_txt = f"[bold orange1]>>> {streak}d streak <<<[/bold orange1]"
            elif streak_anim == 1:
                streak_txt = f"[orange1]==> {streak}d streak <==[/orange1]"
            else:
                streak_txt = f"[dim orange1]{streak}d streak[/dim orange1]"
        else:
            streak_txt = "[dim]no streak[/dim]"

        # Animated separator
        sep_anim = self._frame % 2
        if sep_anim == 0:
            sep = "[dim]═[/dim]" * 70
        else:
            sep = "[dim]─[/dim]" * 70

        acc = stats.get("accuracy", 0) or 0
        ac = "green" if acc >= 70 else "yellow" if acc >= 40 else "red"
        # Stored minutes + live in-memory elapsed so the clock ticks every second
        import time as _time
        stored_secs = stats["time_spent"] * 60
        live_secs = max(0, _time.monotonic() - getattr(self.app, "_session_start", _time.monotonic()))
        time_ = format_duration(stored_secs + live_secs)
        ach_e = stats["achievements_earned"]
        ach_t = stats["achievements_total"]

        # ASCII Logo
        ascii_logo = r"""
  ███████╗██╗  ██╗███████╗██╗     ██╗     ███╗   ███╗███████╗███╗   ██╗████████╗ ██████╗ ██████╗ 
  ██╔════╝██║  ██║██╔════╝██║     ██║     ████╗ ████║██╔════╝████╗  ██║╚══██╔══╝██╔═══██╗██╔══██╗
  ███████╗███████║█████╗  ██║     ██║     ██╔████╔██║█████╗  ██╔██╗ ██║   ██║   ██║   ██║██████╔╝
  ╚════██║██╔══██║██╔══╝  ██║     ██║     ██║╚██╔╝██║██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██╔══██╗
  ███████║██║  ██║███████╗███████╗███████╗██║ ╚═╝ ██║███████╗██║ ╚████║   ██║   ╚██████╔╝██║  ██║
  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
        """

        # ── RECOMMENDED label ──────────────────────────────────────────
        if recommended:
            lesson = recommended["lesson"]
            track = recommended["track"]
            diff = difficulty_icon(lesson["difficulty"])
            dcol = difficulty_color(lesson["difficulty"])
            rec_line = (
                f"[bold cyan]{lesson['title']}[/bold cyan]  "
                f"[dim]{track['name']}[/dim]  "
                f"[{dcol}]{diff}[/{dcol}]  "
                f"[dim]~{lesson.get('estimated_minutes', 15)}min[/dim]  "
                f"[gold1]+{lesson.get('xp_reward', 100)}XP[/gold1]"
            )
            rec_hint = "[dim]Press Ctrl+L → Lessons[/dim]"
        else:
            rec_line = "[bold green]★ ALL LESSONS COMPLETE — SHELLMENTOR GRADUATE ★[/bold green]"
            rec_hint = ""

        # ── TOP COMMANDS ───────────────────────────────────────────────
        top_cmds = stats.get("top_commands", [])
        if top_cmds:
            cmd_parts = []
            for i, c in enumerate(top_cmds[:6]):
                if i % 2 == 0:
                    cmd_parts.append(f"[cyan]{c['cmd']}[/cyan][dim]×{c['n']}[/dim]")
                else:
                    cmd_parts.append(f"[green]{c['cmd']}[/green][dim]×{c['n']}[/dim]")
            cmd_str = "  ".join(cmd_parts)
        else:
            cmd_str = "[dim]none yet[/dim]"

        # Animated command counter
        cmd_anim = self._frame % 4
        if cmd_anim == 0:
            cmd_prefix = "[bold cyan]▶▶[/bold cyan]"
        elif cmd_anim == 1:
            cmd_prefix = "[cyan]▶[/cyan]"
        elif cmd_anim == 2:
            cmd_prefix = "[dim cyan]▶[/dim cyan]"
        else:
            cmd_prefix = "[cyan]▶▶[/cyan]"

        # ── BUILD SINGLE MARKUP BLOCK ──────────────────────────────────
        content = f"""
[dim cyan]{ascii_logo}[/dim cyan]

[bold white]  ═══════════════════════════════════════════════════════════════════════════════════════════════════[/bold white]

  [bold white]›› {username}[/bold white]  [dim]·[/dim]  [gold1]{stats['rank_title']}[/gold1]  [dim]·[/dim]  [cyan]Level {stats['level']}[/cyan]  [dim]·[/dim]  [gold1]{format_xp(stats['xp'])} XP[/gold1]  [dim]·[/dim]  {streak_txt}

  [dim]Progress to {next_rank['next_title']}:[/dim]
  {bar}  [bold]{pct}%[/bold]  [dim]({xp_needed:,} XP remaining)[/dim]

  {sep}

  [cyan]╔══════════╗[/cyan]  [green]╔══════════╗[/green]  [yellow]╔══════════╗[/yellow]  [magenta]╔══════════╗[/magenta]  [white]╔══════════╗[/white]  [blue]╔══════════╗[/blue]  [{ac}]╔══════════╗[/{ac}]
  [cyan]║ {stats['lessons']:>3}      ║[/cyan]  [green]║ {stats['challenges']:>3}      ║[/green]  [yellow]║ {stats['missions']:>3}      ║[/yellow]  [magenta]║ {ach_e:>2}/{ach_t:<2}    ║[/magenta]  [white]║ {stats['commands_run']:>5}    ║[/white]  [blue]║ {time_:>6}   ║[/blue]  [{ac}]║ {acc:>5.1f}%   ║[/{ac}]
  [cyan]╚══════════╝[/cyan]  [green]╚══════════╝[/green]  [yellow]╚══════════╝[/yellow]  [magenta]╚══════════╝[/magenta]  [white]╚══════════╝[/white]  [blue]╚══════════╝[/blue]  [{ac}]╚══════════╝[/{ac}]
  [dim]  Lessons      Challenges     Missions     Achievements   Commands      Time          Accuracy[/dim]

  {sep}

  [bold grey50]▶ RECOMMENDED NEXT[/bold grey50]
  {rec_line}
  {rec_hint}

  {sep}

  [bold grey50]▶ KEYBOARD SHORTCUTS[/bold grey50]
  [dim]Ctrl+L[/dim] Lessons    [dim]Ctrl+G[/dim] Playground   [dim]Ctrl+H[/dim] Challenges   [dim]Ctrl+M[/dim] Missions
  [dim]Ctrl+A[/dim] Achievements [dim]Ctrl+N[/dim] Notes       [dim]Ctrl+R[/dim] Analytics   [dim]Ctrl+D[/dim] Dashboard
  [dim]Ctrl+P[/dim] Command Palette  [dim]Ctrl+Q[/dim] Quit

  {sep}

  [bold grey50]▶ TOP COMMANDS {cmd_prefix}[/bold grey50]
  {cmd_str}

  {sep}

[dim]  ShellMentor v{APP_VERSION} — Master the Linux Command Line[/dim]
        """

        body.update(content)



# ──────────────────────── Screen: Lessons ────────────────────────

class LessonsScreen(BaseScreen):
    """Track and lesson browser with lesson viewer."""

    def __init__(self):
        super().__init__(screen_name="lessons")
        self.current_track = ""
        self.current_lesson_id = ""
        self._exercise_inputs = []
        self._exercise_results = []

    def render_content(self) -> ComposeResult:
        with Horizontal(id="lessons-layout"):
            with Vertical(id="lessons-sidebar"):
                yield Static("LEARNING TRACKS", id="track-header")
                yield ListView(id="tracks-list")
                yield Rule()
                yield Static("LESSONS", id="lessons-header")
                yield ListView(id="lessons-list")
            with ScrollableContainer(id="lesson-content"):
                yield Static(
                    "\n  Select a track and lesson to begin.\n"
                    "  Use arrow keys to navigate.\n",
                    id="lesson-placeholder"
                )

    DEFAULT_CSS = """
    #lessons-sidebar {
        width: 40;
        background: #0e1117;
        border-right: solid #1e2030;
        padding: 1;
    }
    #lesson-content {
        background: #0a0e14;
        padding: 1;
    }
    """

    def on_mount(self) -> None:
        self._populate_tracks()

    def _populate_tracks(self) -> None:
        self._load_tracks_async()

    @work(exclusive=True)
    async def _load_tracks_async(self) -> None:
        tracks_list = self.query_one("#tracks-list", ListView)
        items = []
        for track in self.app.learning_engine.get_all_track_stats():
            pct = track["pct_complete"]
            filled = int(pct / 20)
            bar = "X" * filled + "." * (5 - filled)
            label = (
                f"{track['name']}  "
                f"[cyan]{bar}[/]  "
                f"[grey50]{track['lessons_done']}/{track['lessons_total']}[/]"
            )
            items.append(ListItem(Label(Text.from_markup(label)), id=f"track-{track['id']}"))
        await tracks_list.remove_children()
        if items:
            await tracks_list.mount(*items)


    @on(ListView.Selected, "#tracks-list")
    def track_selected(self, event: ListView.Selected) -> None:
        track_id = event.item.id.replace("track-", "") if event.item.id else None
        if track_id:
            self.current_track = track_id
            self._populate_lessons(track_id)

    def _populate_lessons(self, track_id: str) -> None:
        self._load_lessons_async(track_id)

    @work(exclusive=True)
    async def _load_lessons_async(self, track_id: str) -> None:
        lessons_list = self.query_one("#lessons-list", ListView)
        items = []
        for lesson in self.app.learning_engine.get_track_lessons(track_id):
            status = "[X]" if lesson["completed"] else ("[LOCKED]" if lesson.get("locked") else "[ ]")
            diff   = difficulty_icon(lesson["difficulty"])
            label  = (
                f"{status} {lesson['title']}  "
                f"{diff}  [gold1]+{lesson['xp_reward']}[/]"
            )
            items.append(ListItem(Label(Text.from_markup(label)), id=f"lesson-{lesson['id']}"))
        await lessons_list.remove_children()
        if items:
            await lessons_list.mount(*items)

    @on(ListView.Selected, "#lessons-list")
    def lesson_selected(self, event: ListView.Selected) -> None:
        lesson_id = event.item.id.replace("lesson-", "") if event.item.id else None
        if lesson_id:
            self._show_lesson(lesson_id)

    def _show_lesson(self, lesson_id: str) -> None:
        self.current_lesson_id = lesson_id
        self.app.learning_engine.start_lesson(lesson_id)
        self._load_lesson_async(lesson_id)

    @work(exclusive=True)
    async def _load_lesson_async(self, lesson_id: str) -> None:
        lesson, track_id = self.app.learning_engine.get_lesson(lesson_id)
        if not lesson:
            return

        content = self.query_one("#lesson-content", ScrollableContainer)
        await content.remove_children()

        self._exercise_inputs = []
        self._exercise_results = []

        completed = lesson_id in self.app.db.get_completed_lessons()
        status_line = "[green][COMPLETED][/]" if completed else "[yellow][IN PROGRESS][/]"

        widgets = [
            Static(
                f"\n  [bold cyan]{lesson['title']}[/]  {status_line}\n"
                f"  [grey50]{difficulty_icon(lesson['difficulty'])} {lesson['difficulty']}  |  "
                f"~{lesson.get('estimated_minutes',15)} min  |  "
                f"[gold1]+{lesson['xp_reward']} XP[/][/grey50]\n"
            ),
            Rule(),
            Static(f"  [bold]INTRODUCTION[/]\n  {lesson.get('introduction','')}\n"),
            Static(
                f"  [bold cyan]PURPOSE:[/] {lesson.get('purpose','')}\n"
                f"  [bold cyan]SYNTAX:[/]  [green]{lesson.get('syntax','')}[/]\n"
            ),
            Rule(),
        ]

        for i, section in enumerate(lesson.get("sections", []), 1):
            widgets.append(Static(
                f"  [bold]{i}. {section['title']}[/]\n"
                f"  {section['content']}\n"
            ))
            widgets.append(Static(
                f"  [green]$ {section['example']}[/]\n"
                f"  [grey50]-> {section['explanation']}[/]\n"
            ))

        widgets.append(Rule())

        mistakes = lesson.get("common_mistakes", [])
        if mistakes:
            widgets.append(Static("  [bold red]COMMON MISTAKES[/]"))
            for m in mistakes:
                widgets.append(Static(f"  - {m}"))
            widgets.append(Static(""))

        practices = lesson.get("best_practices", [])
        if practices:
            widgets.append(Static("  [bold green]BEST PRACTICES[/]"))
            for p in practices:
                widgets.append(Static(f"  - {p}"))
            widgets.append(Static(""))

        widgets.append(Rule())

        exercises = lesson.get("exercises", [])
        if exercises:
            widgets.append(Static("  [bold yellow]EXERCISES[/]\n"))
            for ex_idx, ex in enumerate(exercises):
                widgets.append(Static(
                    f"  [cyan]Exercise {ex_idx + 1}:[/] {ex['prompt']}\n"
                    f"  [grey50]+{ex['xp']} XP[/]\n"
                ))
                inp = Input(placeholder="Enter your command...")
                res = Static("")
                self._exercise_inputs.append(inp)
                self._exercise_results.append(res)
                widgets.append(inp)
                widgets.append(res)
                widgets.append(Static(""))

        quiz = lesson.get("quiz", [])
        if quiz:
            widgets.append(Rule())
            widgets.append(Static(f"  [bold]QUIZ - {len(quiz)} questions[/]\n"))
            widgets.append(Button(
                f"  Start Quiz  (+{sum(q.get('xp', 10) for q in quiz)} XP)",
                id="start-quiz", variant="primary",
            ))

        widgets.append(Static(""))
        widgets.append(Button("  Mark as Complete", id="complete-lesson", variant="success"))
        widgets.append(Static("\n"))

        await content.mount(*widgets)

    @on(Input.Submitted)
    def exercise_submitted(self, event: Input.Submitted) -> None:
        if event.input not in self._exercise_inputs:
            return

        command = event.value.strip()
        if not command:
            return

        ex_idx = self._exercise_inputs.index(event.input)
        lesson, _ = self.app.learning_engine.get_lesson(self.current_lesson_id)
        if not lesson:
            return
        exercises = lesson.get("exercises", [])
        if ex_idx >= len(exercises):
            return
        exercise = exercises[ex_idx]

        result = self.app.playground_engine.sandbox.run(command)
        validation = self.app.learning_engine.validate_exercise(exercise, command, result.stdout)

        if ex_idx < len(self._exercise_results):
            result_widget = self._exercise_results[ex_idx]
            if validation["correct"]:
                result_widget.update(
                    f"  [green]CORRECT! +{validation['xp']} XP[/]  "
                    f"[grey50]{truncate(result.stdout, 40)}[/]"
                )
                self.app.progress_engine.award_xp(validation["xp"], "exercise", f"Exercise {ex_idx}")
            else:
                hint = f"  Hint: {validation['hint']}" if validation.get("hint") else ""
                result_widget.update(
                    f"  [red]INCORRECT.[/]{hint}\n"
                    f"  [grey50]{truncate(result.output, 50)}[/]"
                )

    @on(Button.Pressed, "#start-quiz")
    def start_quiz(self) -> None:
        quiz_session = self.app.learning_engine.start_quiz()
        if quiz_session:
            self.app.push_screen(QuizScreen(quiz_session))

    @on(Button.Pressed, "#complete-lesson")
    def complete_lesson(self) -> None:
        if not self.current_lesson_id:
            return
        # Calculate score from exercise results
        total = len(self._exercise_results)
        correct = sum(1 for r in self._exercise_results if "CORRECT" in (r.render() or ""))
        score = int((correct / total * 100)) if total > 0 else 100
        # Get completion info from learning engine (no DB write yet)
        info = self.app.learning_engine.complete_lesson(score=score)
        if not info:
            return
        # Single call to progress engine: records + awards XP + streak + achievements
        self.app.progress_engine.complete_lesson(
            info["lesson_id"], info["track_id"],
            info["score"], info["xp"], info["time"]
        )
        self._populate_lessons(self.current_track)
        self.app.show_notification(f"Lesson complete! +{info['xp']} XP", severity="information")



# ──────────────────────── Screen: Quiz ────────────────────────

class QuizScreen(Screen):
    """Interactive quiz screen."""

    BINDINGS = [Binding("escape", "quit_quiz", "Quit Quiz"), Binding("ctrl+d", "go_dashboard", "Main Menu")]

    def __init__(self, session, **kwargs):
        super().__init__(**kwargs)
        self.session = session

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ScrollableContainer(id="quiz-body")
        with Horizontal(id="quiz-nav-row"):
            yield Button("Abandon Quiz", id="quiz-abandon", variant="error")
            yield Button("Main Menu", id="quiz-mainmenu")
        yield Footer()

    DEFAULT_CSS = """
    #quiz-body {
        padding: 1;
        height: 1fr;
    }
    #quiz-nav-row {
        height: 3;
        padding: 0 1;
        border-top: solid #1e2030;
        background: #0e1117;
    }
    """

    def on_mount(self) -> None:
        self._show_question()

    def _show_question(self) -> None:
        self._load_question_async()

    @work(exclusive=True)
    async def _load_question_async(self) -> None:
        body = self.query_one("#quiz-body")
        q = self.session.current_question
        if not q:
            await self._load_results_async()
            return

        await body.remove_children()
        idx   = self.session.current_idx + 1
        total = len(self.session.questions)
        q_type = q.get("type", "multiple_choice")
        widgets = [
            Static(
                f"\n  [bold cyan]Question {idx} of {total}[/]  "
                f"[grey50]{self.session.correct} correct so far[/]\n"
            ),
            Rule(),
            Static(f"\n  [bold]{q['question']}[/]\n"),
        ]
        if q_type in ("multiple_choice", "output_prediction"):
            for i, opt in enumerate(q.get("options", []), 1):
                widgets.append(Button(f"  {i}. {opt}", id=f"opt-{i}", variant="default"))
        elif q_type == "fill_in_blank":
            widgets.append(Input(placeholder="Type your answer...", id="quiz-input"))
            widgets.append(Button("  Submit Answer", id="quiz-submit", variant="primary"))
        widgets.append(Static(f"\n  [gold1]+{q.get('xp', 10)} XP[/] for correct answer\n"))
        await body.mount(*widgets)

    @on(Button.Pressed)
    def option_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("opt-"):
            opt_idx = int(bid.split("-")[1]) - 1
            q = self.session.current_question
            if q:
                options = q.get("options", [])
                if opt_idx < len(options):
                    self._submit_answer(options[opt_idx])
        elif bid == "quiz-submit":
            inp = self.query_one("#quiz-input", Input)
            self._submit_answer(inp.value)

    def _submit_answer(self, answer: str) -> None:
        result = self.session.answer(answer)
        self.app.progress_engine.record_quiz_answer(result["correct"])
        self._load_answer_async(result)

    @work(exclusive=True)
    async def _load_answer_async(self, result: dict) -> None:
        body = self.query_one("#quiz-body")
        await body.remove_children()
        color = "green" if result["correct"] else "red"
        icon  = "[X]" if result["correct"] else "[ ]"
        widgets = [Static(
            f"\n  [{color}]{icon} {'CORRECT!' if result['correct'] else 'INCORRECT'}[/]\n"
        )]
        if not result["correct"]:
            widgets.append(Static(f"  [grey50]Correct answer: {result['correct_answer']}[/]\n"))
        if result.get("explanation"):
            widgets.append(Static(f"  {result['explanation']}\n"))
        if result["correct"] and result.get("xp", 0) > 0:
            widgets.append(Static(f"  [gold1]+{result['xp']} XP[/]\n"))
        widgets.append(Button(
            "  Next Question" if not self.session.is_complete else "  See Results",
            id="next-q", variant="primary",
        ))
        await body.mount(*widgets)

    @on(Button.Pressed, "#next-q")
    def next_question(self) -> None:
        if self.session.is_complete:
            self._load_results_async()
        else:
            self._show_question()

    def _show_results(self) -> None:
        self._load_results_async()

    @work(exclusive=True)
    async def _load_results_async(self) -> None:
        body = self.query_one("#quiz-body")
        await body.remove_children()
        pct   = self.session.score_pct
        color = "green" if pct >= 70 else "yellow" if pct >= 50 else "red"
        await body.mount(
            Static(
                f"\n  [bold]QUIZ COMPLETE![/]\n\n"
                f"  Score: [{color}]{self.session.correct}/{self.session.total} ({pct:.0f}%)[/{color}]\n"
                f"  Time:  {self.session.elapsed_seconds:.0f}s\n"
            ),
            Button("  Done", id="quiz-done", variant="primary"),
        )

    @on(Button.Pressed, "#quiz-done")
    def quiz_done(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#quiz-abandon")
    def quiz_abandon(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#quiz-mainmenu")
    def quiz_mainmenu(self) -> None:
        self.app.action_go_dashboard()

    def action_quit_quiz(self) -> None:
        self.app.pop_screen()

    def action_go_dashboard(self) -> None:
        self.app.action_go_dashboard()



# ──────────────────────── Screen: Playground ────────────────────────
class PlaygroundScreen(BaseScreen):
    """Interactive command playground."""

    def __init__(self):
        super().__init__(screen_name="playground")
        self._file_map = {}

    def render_content(self) -> ComposeResult:
        with Horizontal(id="pg-layout"):
            with Vertical(id="pg-sidebar"):
                yield Static("WORKSPACE FILES")
                yield ListView(id="file-list")
                yield Rule()
                yield Static("PIPELINE TEMPLATES")
                yield ListView(id="template-list")
            with Vertical(id="pg-main"):
                yield RichLog(
                    id="pg-output",
                    highlight=True,
                    markup=True,
                    auto_scroll=True,
                    wrap=True,
                )
                with Horizontal(id="pg-input-row"):
                    yield Static("$", id="pg-prompt")
                    yield Input(
                        placeholder="Enter command (workspace files available)...",
                        id="pg-input",
                    )
                    yield Button("Run", id="pg-run", variant="primary")

    DEFAULT_CSS = """
    #pg-sidebar {
        width: 35;
        background: #0e1117;
        border-right: solid #1e2030;
        padding: 1;
    }
    #pg-main {
        background: #0a0e14;
        padding: 1;
    }
    #pg-output {
        height: 1fr;
        background: #060a0f;
        border: solid #1e2030;
    }
    #pg-input-row {
        height: 3;
        padding: 1;
        border-top: solid #1e2030;
    }
    #pg-prompt {
        width: 3;
        padding: 1 0;
        color: #89b4fa;
    }
    """

    def on_mount(self) -> None:
        self._populate_files()
        self._populate_templates()
        output = self.query_one("#pg-output", RichLog)
        files = self.app.playground_engine.list_workspace_files()
        if files:
            fnames = ", ".join(f["name"] for f in files)
        else:
            fnames = "No files found. Check workspace directory."
        output.write(Text.from_markup(
            f"[bold]ShellMentor Playground[/]  [dim]v{APP_VERSION}[/]\n"
            f"[dim]{'-' * 60}[/]\n"
            f"[dim]Workspace:[/] {fnames}\n"
            f"[dim]Click a file to preview | Click a template to load | Up/Down for history[/]\n"
        ))
        self.query_one("#pg-input", Input).focus()

    def _populate_files(self) -> None:
        flist = self.query_one("#file-list", ListView)
        flist.clear()

        self._file_map = {}

        for f in self.app.playground_engine.list_workspace_files():
            label = (
                f"  [cyan]{f['name']}[/]  "
                f"[grey50]{f['lines']} lines[/]"
            )

            safe_id = f["name"].replace(".", "_")

            self._file_map[safe_id] = f["name"]

            flist.append(
                ListItem(
                    Label(Text.from_markup(label)),
                    id=f"file_{safe_id}"
                )
            )

    def _populate_templates(self) -> None:
        """Populate template list - synchronous is fine."""
        tlist = self.query_one("#template-list", ListView)
        tlist.clear()

        for i, tmpl in enumerate(self.app.playground_engine.get_pipeline_templates()):
            label = f"  [yellow]{truncate(tmpl['name'], 26)}[/]"
            tlist.append(ListItem(Label(Text.from_markup(label)), id=f"tmpl-{i}"))

    @on(ListView.Selected, "#file-list")
    def file_selected(self, event: ListView.Selected) -> None:
        """Handle workspace file selection and preview."""

        if not event.item or not event.item.id:
            return

        # IDs are created as: file_<safe_filename>
        if not event.item.id.startswith("file_"):
            return

        # Remove prefix correctly
        safe_id = event.item.id[len("file_"):]

        # Get original filename from mapping
        actual_name = self._file_map.get(safe_id)

        if not actual_name:
            output = self.query_one("#pg-output", RichLog)
            output.write(
                Text.from_markup(
                    f"[red]Error:[/] Could not resolve filename for ID '{safe_id}'"
                )
            )
            return

        output = self.query_one("#pg-output", RichLog)

        output.write(Text.from_markup(f"\n[dim]{'-' * 60}[/]"))
        output.write(Text.from_markup(f"[bold]  {actual_name}[/]"))
        output.write(Text.from_markup(f"[dim]{'-' * 60}[/]"))

        preview = self.app.playground_engine.get_file_preview(
            actual_name,
            20
        )

        for line in preview.splitlines():
            output.write(line)

        output.write(Text.from_markup(f"[dim]{'-' * 60}[/]\n"))

        # Auto-fill command input
        inp = self.query_one("#pg-input", Input)
        inp.value = f"cat {actual_name}"
        inp.focus()

    @on(ListView.Selected, "#template-list")
    def template_selected(self, event: ListView.Selected) -> None:
        idx = int(event.item.id.replace("tmpl-", "")) if event.item.id else -1
        if idx >= 0:
            templates = self.app.playground_engine.get_pipeline_templates()
            if idx < len(templates):
                tmpl = templates[idx]
                inp = self.query_one("#pg-input", Input)
                inp.value = tmpl["command"]
                inp.focus()

    @on(Input.Submitted, "#pg-input")
    @on(Button.Pressed, "#pg-run")
    def run_command(self, event=None) -> None:
        inp = self.query_one("#pg-input", Input)
        command = inp.value.strip()
        if not command:
            return

        output = self.query_one("#pg-output", RichLog)
        output.write(Text.from_markup(f"\n[cyan]$ {command}[/]"))

        result = self.app.playground_engine.execute(command, context="playground")

        if result.blocked:
            output.write(Text.from_markup(
                f"[red]BLOCKED:[/] {result.block_reason}"
            ))
        elif result.stdout:
            output.write(result.stdout.rstrip())
        if result.stderr and not result.blocked:
            output.write(Text.from_markup(f"[red]{result.stderr.rstrip()}[/]"))

        dur_text = f"[grey50]({result.duration_ms:.0f}ms)[/]"
        if result.exit_code != 0 and not result.blocked:
            output.write(Text.from_markup(
                f"[yellow]exit {result.exit_code}[/] {dur_text}"
            ))
        else:
            output.write(Text.from_markup(dur_text))

        inp.value = ""



# ──────────────────────── Screen: Notes ────────────────────────

class NotesScreen(BaseScreen):

    def __init__(self):
        super().__init__(screen_name="notes")
        self._current_note_id: int | None = None

    def render_content(self) -> ComposeResult:
        with Horizontal(id="notes-layout"):
            with Vertical(id="notes-sidebar"):
                yield Static("NOTES")
                yield Input(placeholder="Search notes...", id="notes-search")
                yield Rule()
                yield ListView(id="notes-list")
                yield Button("+ New Note", id="new-note-btn", variant="primary")
                yield Button("Delete",  id="del-note-btn", variant="error")
            with Vertical(id="notes-editor"):
                yield Input(placeholder="Note title...", id="note-title")
                yield TextArea(id="note-content", language="markdown")
                with Horizontal():
                    yield Button("Save", id="save-note-btn", variant="success")
                    yield Button("Export", id="export-note-btn")

    DEFAULT_CSS = """
    #notes-sidebar {
        width: 35;
        background: #0e1117;
        border-right: solid #1e2030;
        padding: 1;
    }
    #notes-editor {
        background: #0a0e14;
        padding: 1;
    }
    #note-content {
        height: 1fr;
    }
    """

    def on_mount(self) -> None:
        self._refresh_notes()

    def _refresh_notes(self, search: str = "") -> None:
        self._load_notes_async(search)

    @work(exclusive=True)
    async def _load_notes_async(self, search: str = "") -> None:
        notes = self.app.db.get_notes(search)
        nlist = self.query_one("#notes-list", ListView)
        items = []
        for note in notes:
            label = (
                f"  {truncate(note['title'], 28)}\n"
                f"  [grey50]{note['updated_at'][:10]}[/]"
            )
            items.append(ListItem(Label(Text.from_markup(label)), id=f"note-{note['id']}"))
        await nlist.remove_children()
        if items:
            await nlist.mount(*items)

    @on(Input.Changed, "#notes-search")
    def search_changed(self, event: Input.Changed) -> None:
        self._refresh_notes(event.value)

    @on(ListView.Selected, "#notes-list")
    def note_selected(self, event: ListView.Selected) -> None:
        note_id = int(event.item.id.replace("note-", "")) if event.item.id else None
        if note_id is not None:
            notes = self.app.db.get_notes()
            note = next((n for n in notes if n["id"] == note_id), None)
            if note:
                self._current_note_id = note_id
                self.query_one("#note-title", Input).value = note["title"]
                self.query_one("#note-content", TextArea).load_text(note["content"])

    @on(Button.Pressed, "#new-note-btn")
    def action_new_note(self) -> None:
        self._current_note_id = None
        self.query_one("#note-title", Input).value = ""
        self.query_one("#note-content", TextArea).load_text("")
        self.query_one("#note-title", Input).focus()

    @on(Button.Pressed, "#save-note-btn")
    def save_note(self) -> None:
        title   = self.query_one("#note-title", Input).value.strip()
        content = self.query_one("#note-content", TextArea).text
        if not title:
            self.app.show_notification("Enter a title", severity="warning")
            return
        if self._current_note_id:
            self.app.db.update_note(self._current_note_id, title, content)
        else:
            self._current_note_id = self.app.progress_engine.create_note(title, content)
        self._refresh_notes()
        self.app.show_notification("Note saved", severity="information")

    @on(Button.Pressed, "#del-note-btn")
    def delete_note(self) -> None:
        if not self._current_note_id:
            return
        def handle_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self.app.db.delete_note(self._current_note_id)
                self._current_note_id = None
                self.query_one("#note-title", Input).value = ""
                self.query_one("#note-content", TextArea).load_text("")
                self._refresh_notes()
                self.app.show_notification("Note deleted", severity="information")
        self.app.push_screen(ConfirmModal("Delete this note?"), handle_confirm)

    @on(Button.Pressed, "#export-note-btn")
    def export_note(self) -> None:
        title   = self.query_one("#note-title", Input).value
        content = self.query_one("#note-content", TextArea).text
        if title and content:
            path = Path.home() / f"{title.replace(' ','_')}.md"
            path.write_text(f"# {title}\n\n{content}")
            self.app.show_notification(f"Exported to {path}", severity="information")



# ──────────────────────── Screen: Analytics ────────────────────────
# ──────────────────────── Screen: Analytics ────────────────────────

class AnalyticsScreen(BaseScreen):
    """Analytics dashboard showing learning statistics."""

    def __init__(self):
        super().__init__(screen_name="analytics")

    def render_content(self) -> ComposeResult:
        yield ScrollableContainer(id="analytics-scroll")

    DEFAULT_CSS = """
    #analytics-scroll {
        padding: 1;
    }
    .analytics-card {
        background: #0e1117;
        border: solid #1e2030;
        margin: 1 0;
        padding: 0 1;
    }
    .analytics-title {
        text-style: bold;
        color: #89b4fa;
        padding: 1 0;
        border-bottom: solid #1e2030;
    }
    .stat-row {
        padding: 0 1;
        margin: 0 0;
    }
    .stat-label {
        color: #585b70;
        width: 25;
    }
    .stat-value {
        color: #89b4fa;
        text-style: bold;
    }
    """

    def on_mount(self) -> None:
        self._render_analytics()

    def _render_analytics(self) -> None:
        """Render analytics dashboard synchronously."""
        scroll = self.query_one("#analytics-scroll", ScrollableContainer)
        scroll.remove_children()

        # Get data
        stats = self.app.progress_engine.get_dashboard_stats()
        analytics = self.app.db.get_analytics_summary()
        ch_stats = self.app.challenge_engine.get_challenge_stats()
        acc = stats.get("accuracy", 0) or 0
        acc_color = "green" if acc >= 70 else "yellow" if acc >= 40 else "red"

        # Build widgets
        widgets = []

        # Header
        widgets.append(Static("\n  [bold cyan]ANALYTICS DASHBOARD[/]  [dim]Learning Statistics[/]\n"))
        widgets.append(Rule())

        # Learning Progress Card
        widgets.append(Container(
            Static("  LEARNING PROGRESS", classes="analytics-title"),
            Static(
                f"\n  [dim]Lessons completed:[/]        [cyan]{stats['lessons']}[/]\n"
                f"  [dim]Challenges solved:[/]        [green]{stats['challenges']}[/]\n"
                f"  [dim]Missions completed:[/]       [yellow]{stats['missions']}[/]\n"
                f"  [dim]Achievements:[/]             [gold1]{stats['achievements_earned']}/{stats['achievements_total']}[/]\n"
                f"  [dim]Time spent:[/]               [blue]{format_duration(stats['time_spent'] * 60)}[/]\n"
                f"  [dim]Quiz accuracy:[/]            [{acc_color}]{acc:.1f}%[/{acc_color}]\n"
                f"  [dim]Current streak:[/]           [orange1]{stats['streak']} days[/]\n"
                f"  [dim]Commands run:[/]             [white]{stats['commands_run']}[/]\n"
            ),
            classes="analytics-card"
        ))

        # Challenge Breakdown Card
        widgets.append(Container(
            Static("  CHALLENGE BREAKDOWN", classes="analytics-title"),
            classes="analytics-card"
        ))

        challenge_content = []
        by_diff = ch_stats.get("by_difficulty", {})
        if by_diff:
            for diff, data in sorted(by_diff.items()):
                solved = data.get("solved", 0)
                total = data.get("total", 0)
                bar_len = int((solved / max(total, 1)) * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                challenge_content.append(
                    f"  {difficulty_icon(diff)} {diff:<14} [cyan]{bar}[/]  [grey50]{solved}/{total}[/]"
                )
        else:
            challenge_content.append("  [grey50]No challenges attempted yet.[/]")

        widgets.append(Static("\n".join(challenge_content)))
        widgets.append(Static(""))

        # Most Used Commands Card
        widgets.append(Container(
            Static("  MOST USED COMMANDS", classes="analytics-title"),
            classes="analytics-card"
        ))

        command_content = []
        top = stats.get("top_commands", [])
        if top:
            max_n = max((c.get("n", 0) for c in top), default=1) or 1
            for i, cmd in enumerate(top, 1):
                name = cmd.get("cmd") or "(empty)"
                n = cmd.get("n", 0)
                bar_w = max(1, int(n / max_n * 20))
                command_content.append(
                    f"  {i:2}. [cyan]{name:<15}[/]  [green]{'█' * bar_w}[/]  [grey50]{n}x[/]"
                )
        else:
            command_content.append("  [grey50]No commands run yet.[/]")

        widgets.append(Static("\n".join(command_content)))
        widgets.append(Static(""))

        # Lessons Per Track Card
        widgets.append(Container(
            Static("  LESSONS PER TRACK", classes="analytics-title"),
            classes="analytics-card"
        ))

        track_content = []
        per_track = analytics.get("lessons_per_track", [])
        if per_track:
            for td in per_track:
                track_content.append(
                    f"  [cyan]{str(td.get('track_id', '?')):<25}[/]  [gold1]{td.get('n', 0)} lessons[/]"
                )
        else:
            track_content.append("  [grey50]No lessons completed yet.[/]")

        widgets.append(Static("\n".join(track_content)))
        widgets.append(Static(""))

        scroll.mount(*widgets)



# ──────────────────────── Screen: Settings ────────────────────────

# ──────────────────────── Screen: Settings ────────────────────────

# ──────────────────────── Screen: Settings ────────────────────────

# ──────────────────────── Screen: Settings ────────────────────────

# ──────────────────────── Screen: Settings ────────────────────────

# ──────────────────────── Screen: Settings ────────────────────────

class SettingsScreen(BaseScreen):
    """Professional settings screen with categories and clean layout."""

    def __init__(self):
        super().__init__(screen_name="settings")

    def render_content(self) -> ComposeResult:
        yield ScrollableContainer(id="settings-scroll")

    DEFAULT_CSS = """
    #settings-scroll {
        padding: 1 2;
    }
    .settings-section {
        margin-bottom: 1;
        padding: 0 1;
        border: solid #1e2030;
        background: #0e1117;
    }
    .settings-section-header {
        padding: 1 0;
        text-style: bold;
        color: #89b4fa;
        border-bottom: solid #1e2030;
    }
    .settings-row {
        padding: 0 1;
        margin: 1 0;
    }
    .settings-label {
        margin-bottom: 0;
        color: #cdd6f4;
        text-style: bold;
    }
    .settings-hint {
        color: #585b70;
        text-style: italic;
        margin-top: 0;
    }
    .shortcut-grid {
        margin: 1 0;
        padding: 1;
        background: #0a0e14;
        border: solid #1e2030;
    }
    .shortcut-row {
        margin: 0 0;
        padding: 0 1;
    }
    .shortcut-key {
        color: #89b4fa;
        text-style: bold;
        width: 12;
    }
    .shortcut-desc {
        color: #cdd6f4;
    }
    Button {
        margin: 0 1 0 0;
    }
    """

    def on_mount(self) -> None:
        self.run_worker(self._build_settings_async(), exclusive=True)

    async def _build_settings_async(self) -> None:
        """Rebuild settings — runs in a worker so remove_children awaits properly."""
        scroll = self.query_one("#settings-scroll", ScrollableContainer)
        await scroll.remove_children()
        await self._mount_settings_widgets(scroll)

    def _build_settings(self) -> None:
        """Sync entry point used by call_after_refresh; triggers async rebuild."""
        self.run_worker(self._build_settings_async(), exclusive=True)

    async def _mount_settings_widgets(self, scroll: ScrollableContainer) -> None:
        """Build and mount all settings widgets into *scroll*."""

        user = self.app.db.get_user()
        current_theme = user.get("theme", "professional_dark")

        # Prefer the app's registered theme ids (includes all YAML themes)
        if hasattr(self.app, "theme_ids"):
            theme_list = list(self.app.theme_ids())
        else:
            themes_data = load_yaml(THEMES_DIR / "themes.yaml")
            theme_list = list((themes_data or {}).get("themes", {}).keys())

        # Fallback so the dropdown always has options
        if not theme_list:
            theme_list = [
                "professional_dark", "professional_light", "nord",
                "dracula", "matrix", "solarized", "cyber",
            ]

        # Validate saved theme
        if current_theme not in theme_list:
            current_theme = theme_list[0]

        # Select expects (label, value) — value MUST be the theme id
        theme_options = [
            (t.replace("_", " ").title(), t) for t in theme_list
        ]

        # Build all widgets
        widget_list = []

        # ── Header ──
        widget_list.append(Static("\n  [bold cyan]⚙  SETTINGS[/]  [dim]Configure ShellMentor[/]\n"))
        widget_list.append(Rule())

        # ── PROFILE ──
        widget_list.append(Static("\n  [bold cyan]👤  PROFILE[/]", classes="settings-section-header"))
        widget_list.append(Static(""))
        widget_list.append(Static("  Display Name", classes="settings-label"))
        widget_list.append(Static(
            "  This name appears on the dashboard and in your portfolio.",
            classes="settings-hint"
        ))
        widget_list.append(Input(
            value=user.get("username", "Learner"),
            placeholder="Enter your display name",
            id="username-input",
        ))
        widget_list.append(Button("💾  Save Username", id="save-username", variant="primary"))
        widget_list.append(Static(""))

        # ── APPEARANCE ──
        widget_list.append(Rule())
        widget_list.append(Static("\n  [bold cyan]🎨  APPEARANCE[/]", classes="settings-section-header"))
        widget_list.append(Static(""))
        widget_list.append(Static("  Theme", classes="settings-label"))
        widget_list.append(Static(
            "  Pick a colour scheme — the preview updates live as you select.",
            classes="settings-hint"
        ))

        theme_select = Select(
            theme_options,
            id="theme-select",
            prompt="Choose a theme",
            allow_blank=False,
            value=current_theme,
        )
        widget_list.append(theme_select)
        widget_list.append(Button("✅  Apply & Save Theme", id="apply-theme", variant="success"))
        widget_list.append(Static(""))

        # Current theme info row
        widget_list.append(Static(
            f"  [dim]Current saved theme:[/dim]  [cyan]{current_theme.replace('_',' ').title()}[/cyan]",
            id="current-theme-label",
        ))
        widget_list.append(Static(""))

        # ── DATA MANAGEMENT ──
        widget_list.append(Rule())
        widget_list.append(Static("\n  [bold cyan]🗄  DATA MANAGEMENT[/]", classes="settings-section-header"))
        widget_list.append(Static(""))
        widget_list.append(Static("  Database Location", classes="settings-label"))
        widget_list.append(Static(f"  [dim]{self.app.db.db_path}[/dim]", classes="settings-hint"))
        widget_list.append(Static(
            "  All progress, notes and achievements are stored locally on your machine.",
            classes="settings-hint"
        ))
        widget_list.append(Button("📄  Export Portfolio (Markdown)", id="export-portfolio", variant="primary"))
        widget_list.append(Button("⚠  Reset All Progress", id="reset-progress", variant="error"))
        widget_list.append(Static(""))

        # ── KEYBOARD SHORTCUTS ──
        widget_list.append(Rule())
        widget_list.append(Static("\n  [bold cyan]⌨  KEYBOARD SHORTCUTS[/]", classes="settings-section-header"))
        widget_list.append(Static(""))

        shortcuts = [
            ("Ctrl+L", "Lessons"),
            ("Ctrl+G", "Playground"),
            ("Ctrl+H", "Challenges"),
            ("Ctrl+M", "Missions"),
            ("Ctrl+A", "Achievements"),
            ("Ctrl+N", "Notes"),
            ("Ctrl+R", "Analytics"),
            ("Ctrl+D", "Dashboard"),
            ("Ctrl+P", "Command Palette"),
            ("Ctrl+Q", "Quit"),
            ("Escape", "Back to Dashboard"),
        ]
        rows = []
        for key, desc in shortcuts:
            rows.append(Container(
                Static(f"  [bold cyan]{key}[/]", classes="shortcut-key"),
                Static(desc, classes="shortcut-desc"),
                classes="shortcut-row",
            ))
        widget_list.append(Container(*rows, classes="shortcut-grid"))
        widget_list.append(Static(""))
        widget_list.append(Rule())

        # Mount all widgets in one awaited call to avoid DuplicateId race
        await scroll.mount(*widget_list)

    @on(Button.Pressed, "#save-username")
    def save_username(self) -> None:
        name = self.query_one("#username-input", Input).value.strip()
        if name:
            self.app.db.update_user(username=name)
            self.app.show_notification(f"✅ Username saved: {name}", severity="information")
            self._build_settings()
        else:
            self.app.show_notification("Username cannot be empty", severity="warning")

    @on(Select.Changed, "#theme-select")
    def preview_theme_live(self, event: Select.Changed) -> None:
        """Preview the chosen theme immediately — before the user clicks Apply."""
        value = event.value
        if value and value != Select.BLANK:
            try:
                self.app.theme = str(value)
            except Exception:
                pass

    @on(Button.Pressed, "#apply-theme")
    def apply_theme(self) -> None:
        """Persist and apply the selected theme live."""
        try:
            theme_select = self.query_one("#theme-select", Select)
        except Exception:
            self.app.show_notification("Theme selector not found", severity="error")
            return

        value = theme_select.value
        if not value or value == Select.BLANK:
            self.app.show_notification("Please choose a theme first", severity="warning")
            return

        theme_id = str(value)
        applied = False
        if hasattr(self.app, "set_and_apply_theme"):
            applied = self.app.set_and_apply_theme(theme_id)
        else:
            # Fallback for older app versions
            self.app.db.set_theme(theme_id)
            try:
                self.app.theme = theme_id
                applied = True
            except Exception:
                pass

        display = theme_id.replace("_", " ").title()
        if applied:
            self.app.show_notification(f"✅ Theme applied: {display}", severity="information")
            # Defer rebuild so remove_children() finishes before re-mount
            self._build_settings()
        else:
            self.app.show_notification(
                f"Could not apply theme '{display}' — check that themes.yaml is in place.",
                severity="error",
            )

    @on(Button.Pressed, "#export-portfolio")
    def export_portfolio(self) -> None:
        content, path = self.app.progress_engine.generate_portfolio()
        self.app.show_notification(
            f"Portfolio exported: {path}", severity="information"
        )

    @on(Button.Pressed, "#reset-progress")
    def reset_progress(self) -> None:
        def handle_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self.app.db.reset_all_progress()
                self.app.show_notification("All progress has been reset", severity="warning")
                self._build_settings()

        self.app.push_screen(ConfirmModal("Warning: This action cannot be undone. Reset all progress?"), handle_confirm)



# ──────────────────────── Screen: Environment Scan ────────────────────────

class EnvScanScreen(Screen):
    """First-run environment scan. User must confirm before proceeding."""

    BINDINGS = [Binding("enter,space", "continue_app", "Continue to ShellMentor")]

    def __init__(self, system_info: SystemInfo, **kwargs):
        super().__init__(**kwargs)
        self.system_info = system_info

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ScrollableContainer(id="scan-body")
        yield Footer()

    DEFAULT_CSS = """
    #scan-body {
        padding: 2;
    }
    """

    def on_mount(self) -> None:
        body = self.query_one("#scan-body", ScrollableContainer)
        si   = self.system_info

        widgets = [
            Static(
                f"\n"
                f"  [bold]ShellMentor {APP_VERSION}[/]   [dim]Environment Report[/]\n"
                f"  [dim]{'-'*50}[/]\n"
            ),
        ]

        widgets.append(Static(
            f"  SYSTEM\n"
            f"  [dim]{'-'*30}[/]\n"
            f"  Distribution   [cyan]{si.distro_name} {si.distro_version}[/]\n"
            f"  Kernel         [cyan]{si.kernel}[/]\n"
            f"  Shell          [cyan]{si.shell}[/]\n"
            f"  Terminal       [cyan]{si.terminal}[/]\n"
            f"  Desktop        [cyan]{si.desktop_env}[/]\n"
            f"  Python         [cyan]{si.python_version}[/]\n"
            f"  Pkg Manager    [cyan]{si.pkg_manager or 'None detected'}[/]\n"
        ))
        widgets.append(Rule())

        tool_pairs = [
            ("grep","sed"), ("awk","gawk"), ("sort","uniq"),
            ("cut","tr"), ("find","xargs"), ("rg","fd"),
            ("fzf","bat"), ("git","sqlite3"),
        ]
        widgets.append(Static("  TOOL AVAILABILITY\n  [dim]Core tools (green) and optional tools (yellow)[/]\n"))

        rows = ""
        for left, right in tool_pairs:
            lf = si.tools.get(left, False)
            rf = si.tools.get(right, False)
            ls = f"[green]  {left:<10}[/]" if lf else f"[yellow]  {left:<10}[/]"
            rs = f"[green]  {right:<10}[/]" if rf else f"[yellow]  {right:<10}[/]"
            li = "[dim]installed[/]" if lf else "[dim]missing  [/]"
            ri = "[dim]installed[/]" if rf else "[dim]missing  [/]"
            rows += f"  {ls} {li}    {rs} {ri}\n"
        widgets.append(Static(rows))

        if si.missing_tools:
            install_cmd = get_install_command(si, si.missing_tools)
            widgets.append(Rule())
            widgets.append(Static(
                f"  OPTIONAL TOOLS\n"
                f"  [dim]The following optional tools unlock extra features:[/]\n"
                f"  [dim]{', '.join(si.missing_tools)}[/]\n"
                f"\n"
                f"  Install command:\n"
                f"  [cyan]{install_cmd}[/]\n"
                f"  [dim](You can install these later)[/]\n"
            ))

        widgets.append(Rule())
        widgets.append(Static(
            f"\n"
            f"  [bold]Ready to start.[/]\n"
            f"  [dim]Press ENTER or SPACE to launch ShellMentor.[/]\n"
        ))

        body.mount(*widgets)

    def action_continue_app(self) -> None:
        self.dismiss()


# ──────────────────────── Screen: GitHub Space ────────────────────────

class GitHubSpaceScreen(BaseScreen):
    """Local git workspace — init, add, commit, push, pull, status, log."""

    def __init__(self):
        super().__init__(screen_name="github_space")
        self._repo_path = str(Path.home() / "shellmentor-portfolio")

    def render_content(self) -> ComposeResult:
        with Horizontal(id="gh-layout"):
            with Vertical(id="gh-sidebar"):
                yield Static("GIT COMMANDS")
                yield Button("git init",        id="git-init",      variant="primary")
                yield Button("git status",      id="git-status",    variant="default")
                yield Button("git add .",       id="git-add",       variant="default")
                yield Button("git commit",      id="git-commit",    variant="default")
                yield Button("git push",        id="git-push",      variant="success")
                yield Button("git pull",        id="git-pull",      variant="warning")
                yield Button("git log",         id="git-log",       variant="default")
                yield Rule()
                yield Static("REPO PATH")
                yield Input(value=self._repo_path, id="repo-path-input")
                yield Button("Set Path", id="set-repo-path", variant="primary")
            with Vertical(id="gh-main"):
                yield RichLog(id="gh-output", highlight=True, markup=True, auto_scroll=True)

    DEFAULT_CSS = """
    #gh-layout { height: 1fr; }
    #gh-sidebar {
        width: 30;
        background: #0e1117;
        border-right: solid #1e2030;
        padding: 1;
    }
    #gh-sidebar Button { width: 100%; margin: 0 0 1 0; }
    #gh-main { background: #0a0e14; padding: 1; }
    #gh-output { height: 1fr; background: #060a0f; border: solid #1e2030; }
    """

    def on_mount(self) -> None:
        output = self.query_one("#gh-output", RichLog)
        output.write(Text.from_markup(
            f"[bold]Git Workspace[/]  [dim]{self._repo_path}[/]\n"
            f"[dim]{'-' * 50}[/]\n"
            f"[dim]Click a command button to run it.[/]\n"
        ))

    def _run_git(self, args: list[str], capture_output: bool = True) -> tuple[int, str, str]:
        import subprocess
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self._repo_path,
                capture_output=capture_output,
                text=True,
                timeout=30,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 127, "", "git: command not found. Install git first."
        except subprocess.TimeoutExpired:
            return 124, "", "git command timed out after 30s."
        except Exception as e:
            return 1, "", str(e)

    def _show_output(self, cmd: str, rc: int, stdout: str, stderr: str) -> None:
        output = self.query_one("#gh-output", RichLog)
        color = "green" if rc == 0 else "red"
        output.write(Text.from_markup(f"\n[cyan]$ {cmd}[/]"))
        if stdout.strip():
            output.write(stdout.rstrip())
        if stderr.strip():
            output.write(Text.from_markup(f"[red]{stderr.rstrip()}[/]"))
        if rc != 0:
            output.write(Text.from_markup(f"[red]exit {rc}[/]"))
        else:
            output.write(Text.from_markup("[green]OK[/]"))

    @on(Button.Pressed, "#git-init")
    def git_init(self) -> None:
        from pathlib import Path as _P
        _P(self._repo_path).mkdir(parents=True, exist_ok=True)
        rc, out, err = self._run_git(["init"])
        self._show_output("git init", rc, out, err)

    @on(Button.Pressed, "#git-status")
    def git_status(self) -> None:
        rc, out, err = self._run_git(["status"])
        self._show_output("git status", rc, out, err)

    @on(Button.Pressed, "#git-add")
    def git_add(self) -> None:
        rc, out, err = self._run_git(["add", "."])
        self._show_output("git add .", rc, out, err)

    @on(Button.Pressed, "#git-commit")
    def git_commit(self) -> None:
        from datetime import datetime
        msg = f"ShellMentor portfolio update — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        rc, out, err = self._run_git(["commit", "-m", msg])
        self._show_output(f'git commit -m "{msg}"', rc, out, err)

    @on(Button.Pressed, "#git-push")
    def git_push(self) -> None:
        rc, out, err = self._run_git(["push"])
        self._show_output("git push", rc, out, err)

    @on(Button.Pressed, "#git-pull")
    def git_pull(self) -> None:
        rc, out, err = self._run_git(["pull"])
        self._show_output("git pull", rc, out, err)

    @on(Button.Pressed, "#git-log")
    def git_log(self) -> None:
        rc, out, err = self._run_git(["log", "--oneline", "-20"])
        self._show_output("git log --oneline -20", rc, out, err)

    @on(Button.Pressed, "#set-repo-path")
    def set_repo_path(self) -> None:
        new_path = self.query_one("#repo-path-input", Input).value.strip()
        if new_path:
            self._repo_path = new_path
            from pathlib import Path as _P
            _P(new_path).mkdir(parents=True, exist_ok=True)
            output = self.query_one("#gh-output", RichLog)
            output.write(Text.from_markup(f"[green]Repo path set to:[/] {new_path}"))
