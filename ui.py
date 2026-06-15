"""
ShellMentor - ui.py
Complete Textual TUI: Dashboard, Lessons, Playground, Challenges, Missions,
Achievements, Notes, Analytics, Settings, GitHub integration.
Professional UI with consistent navigation.
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
from github_sync import GitHubSync
from utils import (
    detect_system, SystemInfo, get_install_command,
    load_yaml, THEMES_DIR, difficulty_icon, difficulty_color,
    rarity_color, format_xp, format_duration, truncate, APP_VERSION, APP_NAME
)

logger = logging.getLogger("shellmentor")


# ──────────────────────── Navigation Sidebar ────────────────────────

class NavButton(Button):
    """Navigation button with consistent styling."""
    
    DEFAULT_CSS = """
    NavButton {
        width: 100%;
        height: 3;
        margin: 0;
        padding: 0 2;
        background: #0e1117;
        border: none;
        text-style: bold;
    }
    NavButton:hover {
        background: #1e2030;
    }
    NavButton.-active {
        background: #1e3a5f;
        color: #89b4fa;
        border-left: solid #89b4fa;
    }
    """

class NavigationSidebar(Vertical):
    """Professional navigation sidebar."""
    
    DEFAULT_CSS = """
    NavigationSidebar {
        width: 28;
        background: #0e1117;
        border-right: solid #1e2030;
        padding: 1 0;
    }
    .sidebar-header {
        padding: 0 2;
        margin-bottom: 1;
        text-style: bold;
        color: #89b4fa;
    }
    .nav-spacer {
        height: 0;
    }
    .nav-home-btn {
        width: 100%;
        height: 3;
        margin: 0;
        background: #0e1117;
        border: solid #1e3a5f;
        color: #89b4fa;
        text-style: bold;
    }
    .nav-home-btn:hover {
        background: #1e3a5f;
    }
    """
    
    def __init__(self, current_screen: str = "dashboard"):
        super().__init__()
        self.current_screen = current_screen
        
    def compose(self) -> ComposeResult:
        yield Static("SHELLMENTOR", classes="sidebar-header")
        yield Rule()

        nav_items = [
            ("dashboard",   "DASHBOARD"),
            ("lessons",     "LESSONS"),
            ("playground",  "PLAYGROUND"),
            ("challenges",  "CHALLENGES"),
            ("missions",    "MISSIONS"),
            ("achievements","ACHIEVEMENTS"),
            ("notes",       "NOTES"),
            ("analytics",   "ANALYTICS"),
            ("settings",    "SETTINGS"),
        ]

        for screen_id, label in nav_items:
            btn = NavButton(label, id=f"nav-{screen_id}")
            if screen_id == self.current_screen:
                btn.add_class("-active")
            yield btn
            yield Static("", classes="nav-spacer")

        yield Rule()
        yield Button("MAIN MENU  [Ctrl+D]", id="nav-dashboard-bottom", classes="nav-home-btn")
        yield Static("", classes="nav-spacer")
        yield Button("QUIT", id="nav-quit", variant="error")


# ──────────────────────── Base Screen with Navigation ────────────────────────

class BaseScreen(Screen):
    """Base screen with navigation sidebar."""
    
    BINDINGS = [
        Binding("ctrl+d", "go_dashboard", "Dashboard"),
        Binding("escape", "go_back", "Back"),
    ]
    
    def __init__(self, screen_name: str = "dashboard", **kwargs):
        super().__init__(**kwargs)
        self.screen_name = screen_name
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            yield NavigationSidebar(self.screen_name)
            with Vertical(id="content-area"):
                yield from self.render_content()
        yield Footer()
    
    def render_content(self) -> ComposeResult:
        """Override this method to provide screen-specific content."""
        yield ScrollableContainer(Static("Content area"))
    
    def action_go_dashboard(self) -> None:
        self.app.action_go_dashboard()
    
    def action_go_back(self) -> None:
        self.app.action_go_dashboard()
    
    @on(Button.Pressed, "#nav-quit")
    def handle_quit(self) -> None:
        self.app.action_quit()

    @on(Button.Pressed, "#nav-dashboard-bottom")
    def nav_dashboard_bottom(self) -> None:
        self.app.action_go_dashboard()

    @on(Button.Pressed, "#nav-dashboard")
    def nav_dashboard(self) -> None:
        self.app.action_go_dashboard()
    
    @on(Button.Pressed, "#nav-lessons")
    def nav_lessons(self) -> None:
        self.app.action_go_lessons()
    
    @on(Button.Pressed, "#nav-playground")
    def nav_playground(self) -> None:
        self.app.action_go_playground()
    
    @on(Button.Pressed, "#nav-challenges")
    def nav_challenges(self) -> None:
        self.app.action_go_challenges()
    
    @on(Button.Pressed, "#nav-missions")
    def nav_missions(self) -> None:
        self.app.action_go_missions()
    
    @on(Button.Pressed, "#nav-achievements")
    def nav_achievements(self) -> None:
        self.app.action_go_achievements()
    
    @on(Button.Pressed, "#nav-notes")
    def nav_notes(self) -> None:
        self.app.action_go_notes()
    
    @on(Button.Pressed, "#nav-analytics")
    def nav_analytics(self) -> None:
        self.app.action_go_analytics()
    
    @on(Button.Pressed, "#nav-settings")
    def nav_settings(self) -> None:
        self.app.action_go_settings()


# ──────────────────────── Shared Widgets ────────────────────────

class XPBar(Static):
    """Compact XP progress bar widget."""

    def __init__(self, current_xp: int = 0, next_threshold: int = 500,
                 pct: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.current_xp = current_xp
        self.next_threshold = next_threshold
        self.pct = pct

    def render(self) -> Text:
        filled = int(self.pct / 5)
        bar = "█" * filled + "░" * (20 - filled)
        return Text.from_markup(
            f"[gold1]{format_xp(self.current_xp)}[/] "
            f"[cyan]{bar}[/] "
            f"[grey70]{self.next_threshold:,} XP[/]"
        )


class StatCard(Static):
    """Small stat display card."""

    def __init__(self, label: str, value: str, icon: str = "",
                 color: str = "cyan", **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._icon  = icon
        self._color = color

    def render(self) -> Text:
        return Text.from_markup(
            f"[{self._color}]{self._icon} {self._value}[/]\n"
            f"[grey50]{self._label}[/]"
        )


class SectionHeader(Static):
    """Styled section title."""

    def __init__(self, title: str, subtitle: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._subtitle = subtitle

    def render(self) -> Text:
        t = Text()
        t.append(f"  {self._title}", style="bold cyan")
        if self._subtitle:
            t.append(f"  {self._subtitle}", style="grey50")
        return t


# ──────────────────────── Modal Screens ────────────────────────

class LevelUpModal(ModalScreen):
    """Level-up celebration screen."""

    BINDINGS = [Binding("escape,enter,space", "dismiss", "Continue")]

    def __init__(self, event: LevelUpEvent, **kwargs):
        super().__init__(**kwargs)
        self.event = event

    def compose(self) -> ComposeResult:
        e = self.event
        yield Container(
            Static("LEVEL UP", id="lu-title"),
            Static(f"\n  Level {e.old_level}  ->  Level {e.new_level}", id="lu-levels"),
            Rule(),
            Static(f"  {e.new_title}", id="lu-rank"),
            Static(f"\n  Total XP: {e.xp_total:,}", id="lu-xp"),
            Static("\n  Press ENTER to continue", id="lu-hint"),
            id="lu-container",
        )

    DEFAULT_CSS = """
    LevelUpModal > Container {
        background: #0e1117;
        border: double #89b4fa;
        width: 50;
        height: 16;
        margin: auto;
        padding: 1 2;
        content-align: center middle;
    }
    #lu-title  { color: gold; text-style: bold; text-align: center; }
    #lu-levels { color: cyan; text-align: center; }
    #lu-rank   { color: green; text-style: bold; text-align: center; }
    #lu-xp     { color: gold; text-align: center; }
    #lu-hint   { text-align: center; }
    """

    def action_dismiss(self) -> None:
        self.dismiss()


class AchievementModal(ModalScreen):
    """Achievement earned notification."""

    BINDINGS = [Binding("escape,enter,space", "dismiss", "Continue")]

    def __init__(self, achievement: dict, **kwargs):
        super().__init__(**kwargs)
        self.achievement = achievement

    def compose(self) -> ComposeResult:
        a = self.achievement
        rarity = a.get("rarity", "common")
        color = rarity_color(rarity)
        yield Container(
            Static("ACHIEVEMENT UNLOCKED", id="ach-header"),
            Rule(),
            Static(f"  {a['icon']}  {a['title']}", id="ach-title"),
            Static(f"\n  {a['description']}", id="ach-desc"),
            Static(f"\n  +{a.get('xp_reward',0)} XP  |  [{color}]{rarity.upper()}[/{color}]",
                   id="ach-xp"),
            Static("\n  Press ENTER to continue", id="ach-hint"),
            id="ach-container",
        )

    DEFAULT_CSS = """
    AchievementModal > Container {
        background: #0e1117;
        border: solid gold;
        width: 50;
        height: 14;
        margin: auto;
        padding: 1 2;
    }
    #ach-header { color: gold; text-style: bold; }
    #ach-title  { color: cyan; text-style: bold; }
    #ach-desc   { color: #cdd6f4; }
    #ach-xp     { color: gold; }
    #ach-hint   { color: grey50; }
    """

    def action_dismiss(self) -> None:
        self.dismiss()


class HintModal(ModalScreen):
    """Display a hint."""
    BINDINGS = [Binding("escape,enter", "dismiss", "Close")]

    def __init__(self, hint: str, hint_num: int, **kwargs):
        super().__init__(**kwargs)
        self.hint = hint
        self.hint_num = hint_num

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f"HINT #{self.hint_num}", id="hint-title"),
            Rule(),
            Static(f"\n  {self.hint}\n", id="hint-text"),
            Button("Got it", id="hint-ok", variant="primary"),
            id="hint-container",
        )

    DEFAULT_CSS = """
    HintModal > Container {
        background: #0e1117;
        border: solid yellow;
        width: 55;
        height: 12;
        margin: auto;
        padding: 1 2;
    }
    #hint-title { color: yellow; text-style: bold; }
    #hint-text  { color: #cdd6f4; }
    #hint-ok    { margin: 1 0 0 0; }
    """

    @on(Button.Pressed, "#hint-ok")
    def close(self) -> None:
        self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()


class ConfirmModal(ModalScreen):
    """Generic yes/no confirmation."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f"\n  {self.message}\n"),
            Horizontal(
                Button("Yes", id="yes", variant="primary"),
                Button("No",  id="no",  variant="default"),
                id="confirm-buttons",
            ),
            id="confirm-container",
        )

    DEFAULT_CSS = """
    ConfirmModal > Container {
        background: #0e1117;
        border: solid #89b4fa;
        width: 50;
        height: 10;
        margin: auto;
        padding: 1 2;
    }
    #confirm-buttons { height: 3; margin-top: 1; }
    Button { margin-right: 1; }
    """

    @on(Button.Pressed, "#yes")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def cancel_btn(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ──────────────────────── Screen: Dashboard ────────────────────────

# ──────────────────────── Screen: Dashboard ────────────────────────

# ──────────────────────── Screen: Dashboard ────────────────────────

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

    def render_content(self) -> ComposeResult:
        yield ScrollableContainer(
            Static(id="dash-body"),
            id="dashboard-scroll",
        )

    def on_mount(self) -> None:
        self._refresh_dashboard()
        self._start_animation()

    def _start_animation(self) -> None:
        """Start animated counter for dashboard."""
        self._animation_timer = self.set_interval(1.0, self._update_animated_effects)

    def _update_animated_effects(self) -> None:
        """Update animated elements on dashboard."""
        self._frame += 1
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        self._load_dashboard_async()

    @work(exclusive=True)
    async def _load_dashboard_async(self) -> None:
        app = self.app
        stats = app.progress_engine.get_dashboard_stats()
        next_rank = app.progress_engine.get_next_rank_info()
        recommended = app.learning_engine.get_recommended_next()

        # Resolve username
        try:
            user_row = app.db.conn.execute("SELECT username FROM user LIMIT 1").fetchone()
            username = user_row[0] if user_row and user_row[0] else "Shell Hacker"
        except Exception:
            username = "Shell Hacker"

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
        time_ = format_duration(stats["time_spent"] * 60)
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
  [cyan]║ {stats['lessons']:>3}      ║[/cyan]  [green]║ {stats['challenges']:>3}      ║[/green]  [yellow]║ {stats['missions']:>3}      ║[/yellow]  [magenta]║ {ach_e:>2}/{ach_t:<2}    ║[/magenta]  [white]║ {stats['commands_run']:>5}    ║[/white]  [blue] ║ {time_:>6}   ║[/blue]  [{ac}]║ {acc:>5.1f}% ║[/{ac}]
  [cyan]╚══════════╝[/cyan]  [green]╚══════════╝[/green]  [yellow]╚══════════╝[/yellow]  [magenta]╚══════════╝[/magenta]  [white]╚══════════╝[/white]  [blue]╚══════════╝[/blue]  [{ac}]╚══════════╝[/{ac}]
  [dim]  Lessons    Challenges   Missions   Achievements   Commands     Time       Accuracy[/dim]

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
        result = self.app.learning_engine.complete_lesson(score=100)
        xp = result.get("xp", 0)
        self.app.progress_engine.award_xp(xp, "lesson", "Lesson complete")
        self._populate_lessons(self.current_track)
        self.app.show_notification(f"Lesson complete! +{xp} XP", severity="information")


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
        """Populate file list - synchronous is fine for a few files."""
        flist = self.query_one("#file-list", ListView)
        flist.clear()
        self._file_map = {}

        for f in self.app.playground_engine.list_workspace_files():
            label = f"  [cyan]{f['name']}[/]  [grey50]{f['lines']} lines[/]"
            # Use the actual filename as ID (replace dots with underscores for Textual compatibility)
            safe_id = f['name'].replace('.', '_')
            self._file_map[safe_id] = f['name']
            flist.append(ListItem(Label(Text.from_markup(label)), id=f"file_{safe_id}"))

    def _populate_templates(self) -> None:
        """Populate template list - synchronous is fine."""
        tlist = self.query_one("#template-list", ListView)
        tlist.clear()

        for i, tmpl in enumerate(self.app.playground_engine.get_pipeline_templates()):
            label = f"  [yellow]{truncate(tmpl['name'], 26)}[/]"
            tlist.append(ListItem(Label(Text.from_markup(label)), id=f"tmpl-{i}"))

    @on(ListView.Selected, "#file-list")
    def file_selected(self, event: ListView.Selected) -> None:
        safe_id = event.item.id.replace("file-", "") if event.item.id else None
        if not safe_id:
            return

        # Get actual filename from mapping
        actual_name = self._file_map.get(safe_id, safe_id.replace('_', '.'))

        output = self.query_one("#pg-output", RichLog)
        output.write(Text.from_markup(f"\n[dim]{'-' * 60}[/]"))
        output.write(Text.from_markup(f"[bold]  {actual_name}[/]"))
        output.write(Text.from_markup(f"[dim]{'-' * 60}[/]"))
        preview = self.app.playground_engine.get_file_preview(actual_name, 20)
        for line in preview.splitlines():
            output.write(line)
        output.write(Text.from_markup(f"[dim]{'-' * 60}[/]\n"))
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


# ──────────────────────── Screen: Challenges ────────────────────────

class ChallengesScreen(BaseScreen):
    """Challenge browser and solver."""

    def __init__(self):
        super().__init__(screen_name="challenges")

    def render_content(self) -> ComposeResult:
        with Horizontal(id="ch-layout"):
            with Vertical(id="ch-sidebar"):
                yield Static("CHALLENGES")
                yield Select(
                    [(d, d) for d in ["all", "beginner", "intermediate", "advanced", "expert"]],
                    id="diff-filter",
                    prompt="Filter by difficulty",
                    value="all",
                )
                yield Rule()
                yield ListView(id="ch-list")
                yield Rule()
                with Horizontal():
                    yield Button("Start", id="ch-start", variant="primary")
            with Vertical(id="ch-main"):
                yield ScrollableContainer(id="ch-detail")

    DEFAULT_CSS = """
    #ch-sidebar {
        width: 40;
        background: #0e1117;
        border-right: solid #1e2030;
        padding: 1;
    }
    #ch-main {
        background: #0a0e14;
        padding: 1;
    }
    """

    def on_mount(self) -> None:
        self._populate_challenges()

    def _populate_challenges(self, difficulty: str = "") -> None:
        self._load_challenges_async(difficulty)

    @work(exclusive=True)
    async def _load_challenges_async(self, difficulty: str = "") -> None:
        ch_list = self.query_one("#ch-list", ListView)
        items = []
        for ch in self.app.challenge_engine.get_challenges(difficulty=difficulty):
            status = "[X]" if ch["solved"] else difficulty_icon(ch["difficulty"])
            label = (
                f"  {status} {ch['title']}  "
                f"[gold1]+{ch['xp_reward']}[/]"
            )
            items.append(ListItem(Label(Text.from_markup(label)), id=f"ch-{ch['id']}"))
        await ch_list.remove_children()
        if items:
            await ch_list.mount(*items)

    @on(Select.Changed, "#diff-filter")
    def filter_changed(self, event: Select.Changed) -> None:
        diff = "" if event.value == "all" else str(event.value)
        self._populate_challenges(diff)

    @on(ListView.Selected, "#ch-list")
    def challenge_selected(self, event: ListView.Selected) -> None:
        cid = event.item.id.replace("ch-", "") if event.item.id else None
        if cid:
            self._show_challenge_detail(cid)

    def _show_challenge_detail(self, challenge_id: str) -> None:
        self._load_challenge_detail_async(challenge_id)

    @work(exclusive=True)
    async def _load_challenge_detail_async(self, challenge_id: str) -> None:
        ch = self.app.challenge_engine.get_challenge(challenge_id)
        if not ch:
            return

        detail = self.query_one("#ch-detail", ScrollableContainer)
        await detail.remove_children()
        detail.scroll_home()

        solved = challenge_id in self.app.db.get_solved_challenges()
        diff_color = difficulty_color(ch["difficulty"])

        await detail.mount(Static(
            f"\n  [bold cyan]{ch['title']}[/]"
            f"  {'[green][SOLVED][/]' if solved else ''}\n"
            f"  [{diff_color}]{difficulty_icon(ch['difficulty'])} {ch['difficulty']}[/]  "
            f"[gold1]+{ch['xp_reward']} XP[/]  "
            f"[grey50]Dataset: {ch['dataset']}[/]\n"
        ))
        await detail.mount(Rule())
        await detail.mount(Static(
            f"  [bold]OBJECTIVE[/]\n  {ch['objective']}\n\n"
            f"  [bold]DESCRIPTION[/]\n  {ch['description']}\n"
        ))

        self.app._selected_challenge = challenge_id

    @on(Button.Pressed, "#ch-start")
    def start_challenge(self) -> None:
        cid = getattr(self.app, "_selected_challenge", None)
        if not cid:
            self.app.show_notification("Select a challenge first", severity="warning")
            return
        self.app.push_screen(ChallengeScreen(cid))


class ChallengeScreen(Screen):
    """Active challenge solver."""

    BINDINGS = [
        Binding("escape", "abandon", "Abandon"),
        Binding("ctrl+h", "hint", "Hint"),
        Binding("ctrl+d", "go_dashboard", "Dashboard"),
    ]

    def __init__(self, challenge_id: str, **kwargs):
        super().__init__(**kwargs)
        self.challenge_id = challenge_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="cs-layout"):
            yield ScrollableContainer(id="cs-info")
            yield Rule()
            yield RichLog(id="cs-output", highlight=True, markup=True, auto_scroll=True)
            with Horizontal(id="cs-input-row"):
                yield Static("$", id="cs-prompt")
                yield Input(placeholder="Enter your solution command...", id="cs-input")
                yield Button("Run", id="cs-run", variant="primary")
                yield Button("Hint", id="cs-hint", variant="warning")
                yield Button("Submit", id="cs-submit", variant="success")
                yield Button("Main Menu", id="cs-mainmenu")
        yield Footer()

    DEFAULT_CSS = """
    #cs-layout {
        height: 1fr;
        padding: 1;
    }
    #cs-output {
        height: 1fr;
        background: #060a0f;
        border: solid #1e2030;
        margin: 0 1;
    }
    #cs-input-row {
        height: 3;
        padding: 1;
        border-top: solid #1e2030;
    }
    #cs-prompt {
        width: 3;
        padding: 1 0;
        color: #89b4fa;
    }
    """

    def on_mount(self) -> None:
        self._active = self.app.challenge_engine.start_challenge(self.challenge_id)
        if not self._active:
            self.app.pop_screen()
            return

        ch = self._active.challenge
        info = self.query_one("#cs-info", ScrollableContainer)
        info.mount(Static(
            f"\n  [bold cyan]{ch['title']}[/]\n"
            f"  [bold]{ch['objective']}[/]\n"
            f"  [grey50]Dataset: {ch['dataset']}  |  "
            f"+{ch['xp_reward']} XP  |  "
            f"{len(ch.get('hints', []))} hints available[/]\n"
        ))

        output = self.query_one("#cs-output", RichLog)
        output.write(Text.from_markup(
            f"[grey50]Workspace file: [cyan]{ch['dataset']}[/] is ready.[/]\n"
            f"[grey50]Type your command, press Run to test, then Submit when ready.[/]\n"
        ))
        self.query_one("#cs-input", Input).focus()

    @on(Input.Submitted, "#cs-input")
    @on(Button.Pressed, "#cs-run")
    def run_command(self, event=None) -> None:
        inp = self.query_one("#cs-input", Input)
        command = inp.value.strip()
        if not command:
            return

        if self._active:
            self._active.command_history.append(command)
            self._active.attempts += 1

        result = self.app.playground_engine.execute(command, context="challenge")
        output = self.query_one("#cs-output", RichLog)
        output.write(Text.from_markup(f"[cyan]$ {command}[/]"))
        if result.blocked:
            output.write(Text.from_markup(f"[red]BLOCKED: {result.block_reason}[/]"))
        elif result.stdout:
            output.write(result.stdout.rstrip())
        if result.stderr and not result.blocked:
            output.write(Text.from_markup(f"[red]{result.stderr.rstrip()}[/]"))

    @on(Button.Pressed, "#cs-submit")
    def submit_solution(self) -> None:
        inp = self.query_one("#cs-input", Input)
        command = inp.value.strip()
        if not command:
            self.app.show_notification("Enter a command first", severity="warning")
            return

        result = self.app.playground_engine.execute(command, context="challenge")
        submit_result = self.app.challenge_engine.submit_challenge(result.output)

        output = self.query_one("#cs-output", RichLog)
        if submit_result["solved"]:
            xp = submit_result["xp_earned"]
            self.app.progress_engine.complete_challenge(
                self.challenge_id, xp,
                submit_result["hints_used"],
                submit_result["elapsed"],
                command
            )
            output.write(Text.from_markup(
                f"\n[green]CHALLENGE SOLVED![/] [gold1]+{xp} XP[/]\n"
                f"[grey50]Time: {submit_result['elapsed']:.1f}s  "
                f"Hints: {submit_result['hints_used']}[/]\n"
                f"[dim]Reference: {submit_result.get('solution','')}[/]"
            ))
            self.app.show_notification(
                f"Challenge Solved! +{xp} XP", severity="information"
            )
        else:
            output.write(Text.from_markup(
                f"[yellow]Not quite.[/] {submit_result['message']}\n"
                f"[grey50]Keep trying! Use Ctrl+H for a hint.[/]"
            ))

    @on(Button.Pressed, "#cs-hint")
    def action_hint(self) -> None:
        hint = self.app.challenge_engine.request_hint()
        if hint:
            num = self._active.hints_revealed if self._active else 1
            self.app.push_screen(HintModal(hint, num))
        else:
            self.app.show_notification("No more hints available", severity="warning")

    def action_abandon(self) -> None:
        self.app.challenge_engine.abandon_challenge()
        self.app.pop_screen()

    @on(Button.Pressed, "#cs-mainmenu")
    def go_main_menu(self) -> None:
        self.app.challenge_engine.abandon_challenge()
        self.app.action_go_dashboard()

    def action_go_dashboard(self) -> None:
        self.app.action_go_dashboard()




# ──────────────────────── Screen: Missions (Browser) ────────────────────────

class MissionsScreen(BaseScreen):
    """Mission browser - shows list of available missions."""

    def __init__(self):
        super().__init__(screen_name="missions")

    def render_content(self) -> ComposeResult:
        with Horizontal(id="ms-layout"):
            with Vertical(id="ms-sidebar"):
                yield Static("MISSIONS")
                yield ListView(id="ms-list")
                yield Button("Start Mission", id="ms-start", variant="primary")
                yield Rule()
                yield Button("Main Menu", id="back-to-dashboard", variant="default")
                yield Button("Quit", id="quit-app", variant="error")
            yield ScrollableContainer(id="ms-detail")

    DEFAULT_CSS = """
    #ms-sidebar {
        width: 40;
        background: #0e1117;
        border-right: solid #1e2030;
        padding: 1;
    }
    #ms-detail {
        background: #0a0e14;
        padding: 1;
    }
    Button {
        margin: 0 0 1 0;
    }
    """

    def on_mount(self) -> None:
        self._populate_missions()

    def _populate_missions(self) -> None:
        """Populate missions list - synchronous."""
        ms_list = self.query_one("#ms-list", ListView)
        ms_list.clear()

        for m in self.app.challenge_engine.get_missions():
            done = m.get("completed", False)
            stages = m.get("stages_done", 0)
            total = m.get("total_stages", 0)
            status = "[X]" if done else f"[{stages}/{total}]"
            mission_title = m.get("title", m.get("name", "Unknown Mission"))
            label = f"  {mission_title}  [grey50]{status}[/]"
            ms_list.append(ListItem(Label(Text.from_markup(label)), id=f"ms-{m['id']}"))

    @on(ListView.Selected, "#ms-list")
    def mission_selected(self, event: ListView.Selected) -> None:
        mid = event.item.id.replace("ms-", "") if event.item.id else None
        if mid:
            self._show_mission_detail(mid)

    def _show_mission_detail(self, mission_id: str) -> None:
        mission = self.app.challenge_engine.get_mission(mission_id)
        if not mission:
            return

        detail = self.query_one("#ms-detail", ScrollableContainer)
        detail.remove_children()

        stages = mission.get("stages", [])
        completed_stages = self.app.db.get_mission_progress(mission_id)

        mission_title = mission.get("title", mission.get("name", "Unknown Mission"))
        mission_desc = mission.get("description", "")
        mission_difficulty = mission.get("difficulty", "beginner")
        mission_xp = mission.get("xp_reward", 500)
        mission_badge = mission.get("badge", "")

        widgets = [
            Static(
                f"\n  [bold cyan]{mission_title}[/]\n"
                f"  {mission_desc}\n\n"
                f"  [grey50]{difficulty_icon(mission_difficulty)} {mission_difficulty}  "
                f"|  {len(stages)} stages  "
                f"|  [gold1]+{mission_xp} XP total[/]  "
                f"|  Badge: {mission_badge}[/]\n"
            ),
            Rule(),
            Static("  [bold]MISSION STAGES:[/]\n"),
        ]

        for stage in stages:
            done = stage.get("stage", 0) <= completed_stages
            icon = "[X]" if done else "[ ]"
            stage_title = stage.get("title", f"Stage {stage.get('stage', '?')}")
            stage_xp = stage.get("xp", 0)
            stage_objective = stage.get("objective", "")
            widgets.append(Static(
                f"  {icon} {stage_title}  "
                f"[gold1]+{stage_xp} XP[/]\n"
                f"      [grey50]{stage_objective}[/]\n"
            ))

        detail.mount(*widgets)
        self.app._selected_mission = mission_id

    @on(Button.Pressed, "#ms-start")
    def start_mission(self) -> None:
        mid = getattr(self.app, "_selected_mission", None)
        if not mid:
            self.app.show_notification("Select a mission first", severity="warning")
            return
        self.app.push_screen(MissionScreen(mid))

    @on(Button.Pressed, "#back-to-dashboard")
    def back_to_dashboard(self) -> None:
        self.app.action_go_dashboard()

    @on(Button.Pressed, "#quit-app")
    def quit_app(self) -> None:
        self.app.action_quit()


# ──────────────────────── Screen: Mission Runner ────────────────────────

class MissionScreen(Screen):
    """Active mission runner."""

    BINDINGS = [
        Binding("escape", "abandon", "Abandon Mission"),
        Binding("ctrl+h", "hint", "Hint"),
        Binding("ctrl+d", "go_dashboard", "Dashboard"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, mission_id: str, **kwargs):
        super().__init__(**kwargs)
        self.mission_id = mission_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield ScrollableContainer(id="mission-info", classes="panel")
            yield RichLog(id="mission-output", highlight=True, markup=True, auto_scroll=True)
            with Horizontal(id="mission-input-row"):
                yield Static("$")
                yield Input(placeholder="Enter command for this stage...", id="mission-input")
                yield Button("Run", id="m-run", variant="primary")
                yield Button("Next Stage", id="m-next", variant="success")
            with Horizontal(id="mission-button-row"):
                yield Button("Hint", id="m-hint", variant="warning")
                yield Button("Main Menu", id="m-mainmenu", variant="default")
                yield Button("Quit", id="m-quit", variant="error")
        yield Footer()

    DEFAULT_CSS = """
    #mission-info {
        max-height: 12;
        padding: 1;
        border-bottom: solid #1e2030;
    }
    #mission-output {
        height: 1fr;
        background: #060a0f;
        border: solid #1e2030;
        margin: 0 1;
    }
    #mission-input-row {
        height: 3;
        padding: 1;
        border-top: solid #1e2030;
    }
    #mission-button-row {
        height: 3;
        padding: 1;
        border-top: solid #1e2030;
        align: center middle;
    }
    Button {
        margin: 0 1;
    }
    """

    def on_mount(self) -> None:
        self._active = self.app.challenge_engine.start_mission(self.mission_id)
        if not self._active:
            self.app.pop_screen()
            return
        self._update_stage_info()
        self.query_one("#mission-input", Input).focus()

    def _update_stage_info(self) -> None:
        info = self.query_one("#mission-info", ScrollableContainer)
        info.remove_children()
        stage = self._active.current_stage
        if not stage:
            return

        mission = self._active.mission
        total = len(mission.get("stages", []))
        mission_title = mission.get("title", mission.get("name", "Unknown Mission"))
        stage_title = stage.get("title", f"Stage {stage.get('stage', '?')}")
        stage_objective = stage.get("objective", "")
        stage_dataset = stage.get("dataset", "")
        stage_xp = stage.get("xp", 0)

        info.mount(Static(
            f"\n  [bold cyan]{mission_title}[/]  "
            f"[grey50]Stage {stage['stage']}/{total}[/]  "
            f"[gold1]{self._active.progress_pct:.0f} percent complete[/]\n\n"
            f"  [bold]{stage_title}[/]\n"
            f"  [yellow]OBJECTIVE:[/] {stage_objective}\n"
            f"  [grey50]Dataset: {stage_dataset}  |  +{stage_xp} XP[/]\n"
        ))

    @on(Input.Submitted, "#mission-input")
    @on(Button.Pressed, "#m-run")
    def run_command(self, event=None) -> None:
        inp = self.query_one("#mission-input", Input)
        command = inp.value.strip()
        if not command:
            return
        result = self.app.playground_engine.execute(command, context="mission")
        output = self.query_one("#mission-output", RichLog)
        output.write(Text.from_markup(f"[cyan]$ {command}[/]"))
        if result.blocked:
            output.write(Text.from_markup(f"[red]BLOCKED: {result.block_reason}[/]"))
        elif result.stdout:
            output.write(result.stdout.rstrip())
        if result.stderr and not result.blocked:
            output.write(Text.from_markup(f"[red]{result.stderr.rstrip()}[/]"))

    @on(Button.Pressed, "#m-next")
    def next_stage(self) -> None:
        inp = self.query_one("#mission-input", Input)
        command = inp.value.strip()
        if not command:
            self.app.show_notification("Run a command first", severity="warning")
            return

        result = self.app.playground_engine.execute(command, context="mission")
        stage_result = self.app.challenge_engine.submit_mission_stage(result.output)
        output = self.query_one("#mission-output", RichLog)

        xp = stage_result["xp_earned"]
        self.app.progress_engine.complete_mission_stage(
            self.mission_id, stage_result["stage"], xp
        )
        output.write(Text.from_markup(
            f"\n[green]STAGE COMPLETE![/] [gold1]+{xp} XP[/]\n"
        ))

        if stage_result.get("is_final"):
            total_xp = stage_result.get("total_xp", 0)
            badge = stage_result.get("badge", "")
            output.write(Text.from_markup(
                f"\n[bold gold1]MISSION COMPLETE! {badge}[/]\n"
                f"[gold1]Total XP earned: +{total_xp}[/]\n"
            ))
            self.app.progress_engine.complete_mission(self.mission_id, 0)
            self.app.show_notification(f"Mission Complete! {badge}", severity="information")
            self.app.pop_screen()
        else:
            inp.value = ""
            self._update_stage_info()

    @on(Button.Pressed, "#m-hint")
    def action_hint(self) -> None:
        stage = self._active.current_stage if self._active else None
        if stage:
            hint = stage.get("hint", "No hint available")
            self.app.push_screen(HintModal(hint, 1))

    def action_abandon(self) -> None:
        self.app.challenge_engine.abandon_mission()
        self.app.pop_screen()

    @on(Button.Pressed, "#m-mainmenu")
    def go_main_menu(self) -> None:
        self.app.challenge_engine.abandon_mission()
        self.app.action_go_dashboard()

    @on(Button.Pressed, "#m-quit")
    def quit_app(self) -> None:
        self.app.challenge_engine.abandon_mission()
        self.app.action_quit()

    def action_go_dashboard(self) -> None:
        self.app.challenge_engine.abandon_mission()
        self.app.action_go_dashboard()

    def action_quit(self) -> None:
        self.app.challenge_engine.abandon_mission()
        self.app.action_quit()


# ──────────────────────── Screen: Achievements ────────────────────────

class AchievementsScreen(BaseScreen):

    def __init__(self):
        super().__init__(screen_name="achievements")

    def render_content(self) -> ComposeResult:
        yield ScrollableContainer(id="ach-scroll")

    DEFAULT_CSS = """
    #ach-scroll {
        padding: 1;
    }
    """

    def on_mount(self) -> None:
        self._render_achievements()

    def _render_achievements(self) -> None:
        scroll = self.query_one("#ach-scroll", ScrollableContainer)
        scroll.remove_children()

        stats = self.app.progress_engine.get_achievement_stats()
        all_ach = self.app.progress_engine.get_full_achievements_list()

        widgets = [Static(
            f"\n  [bold cyan]ACHIEVEMENTS[/]  "
            f"[grey50]{stats['earned']}/{stats['total']} earned "
            f"({stats['percent']:.0f}%)[/]\n"
        )]

        for rarity in ("legendary", "epic", "rare", "uncommon", "common"):
            group = [a for a in all_ach if a.get("rarity") == rarity]
            if not group:
                continue
            color = rarity_color(rarity)
            widgets.append(Rule())
            widgets.append(Static(
                f"  [{color}]{rarity.upper()}[/{color}]  "
                f"[grey50]{sum(1 for a in group if a['earned'])}/{len(group)}[/]\n"
            ))
            for ach in group:
                earned = ach["earned"]
                dim = "" if earned else "grey50"
                widgets.append(Static(
                    f"  {'[X]' if earned else '[ ]'} "
                    f"[{dim}]{ach['icon']} [bold]{ach['title']}[/bold]  "
                    f"[gold1]+{ach.get('xp_reward', 0)} XP[/]  "
                    f"[{color}]{rarity}[/{color}]\n"
                    f"    {ach['description']}[/{dim}]"
                ))

        scroll.mount(*widgets)


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
        if self._current_note_id:
            self.app.db.delete_note(self._current_note_id)
            self._current_note_id = None
            self.query_one("#note-title", Input).value = ""
            self.query_one("#note-content", TextArea).load_text("")
            self._refresh_notes()

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
        self._render()

    def _render(self) -> None:
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
        self._build_settings()

    def _build_settings(self) -> None:
        """Build settings UI synchronously."""
        scroll = self.query_one("#settings-scroll", ScrollableContainer)
        scroll.remove_children()

        user = self.app.db.get_user()
        current_theme = user.get("theme", "professional_dark")

        # Get available themes
        themes_data = load_yaml(THEMES_DIR / "themes.yaml")
        theme_list = list(themes_data.get("themes", {}).keys()) if themes_data else []

        # Build theme options
        theme_options = []
        if theme_list:
            for theme in theme_list:
                display_name = theme.replace('_', ' ').title()
                theme_options.append((theme, display_name))
        else:
            # Fallback themes if themes.yaml not found
            theme_options = [
                ("professional_dark", "Professional Dark"),
                ("professional_light", "Professional Light"),
                ("nord", "Nord"),
                ("dracula", "Dracula"),
                ("matrix", "Matrix"),
                ("solarized", "Solarized"),
                ("cyber", "Cyber"),
            ]
            theme_list = [t[0] for t in theme_options]

        # Validate current_theme
        if current_theme not in theme_list:
            current_theme = theme_list[0] if theme_list else "professional_dark"

        # Build all widgets in a list
        widget_list = []

        # Header
        widget_list.append(Static("\n  [bold cyan]SETTINGS[/]  [dim]Configure ShellMentor[/]\n"))
        widget_list.append(Rule())

        # PROFILE SECTION
        widget_list.append(Static("\n  [bold]PROFILE[/]", classes="settings-section-header"))
        widget_list.append(Static(""))
        widget_list.append(Static("  USERNAME", classes="settings-label"))
        widget_list.append(Input(
            value=user.get("username", "Learner"),
            placeholder="Enter your name",
            id="username-input"
        ))
        widget_list.append(Button("Save Username", id="save-username", variant="primary"))
        widget_list.append(Static(""))

        # APPEARANCE SECTION
        widget_list.append(Rule())
        widget_list.append(Static("\n  [bold]APPEARANCE[/]", classes="settings-section-header"))
        widget_list.append(Static(""))
        widget_list.append(Static("  THEME", classes="settings-label"))
        widget_list.append(Static("  Select the color scheme for the interface", classes="settings-hint"))

        theme_select = Select(
            theme_options,
            id="theme-select",
            prompt="Choose a theme",
            allow_blank=False,
        )
        widget_list.append(theme_select)
        widget_list.append(Button("Apply Theme", id="apply-theme", variant="primary"))
        widget_list.append(Static(""))

        # GITHUB INTEGRATION SECTION
        widget_list.append(Rule())
        widget_list.append(Static("\n  [bold]GITHUB INTEGRATION[/]", classes="settings-section-header"))
        widget_list.append(Static(""))

        if self.app.github_sync.is_authenticated:
            gh_user = self.app.github_sync.github_username
            widget_list.append(Static(f"  Connected as: @{gh_user}", classes="settings-label"))
            widget_list.append(Static("  Your portfolio can be published to GitHub Pages", classes="settings-hint"))
            widget_list.append(Button("Publish Portfolio", id="publish-portfolio", variant="success"))
            widget_list.append(Button("Disconnect GitHub", id="gh-disconnect", variant="error"))
        else:
            widget_list.append(Static("  Not Connected", classes="settings-label"))
            widget_list.append(
                Static("  Authenticate with GitHub to publish your learning portfolio", classes="settings-hint"))
            widget_list.append(Input(
                placeholder="GitHub Personal Access Token (repo scope required)",
                id="pat-input",
                password=True
            ))
            widget_list.append(Button("Connect with Token", id="gh-pat", variant="primary"))

        widget_list.append(Static(""))

        # DATA MANAGEMENT SECTION
        widget_list.append(Rule())
        widget_list.append(Static("\n  [bold]DATA MANAGEMENT[/]", classes="settings-section-header"))
        widget_list.append(Static(""))
        widget_list.append(Static("  DATABASE LOCATION", classes="settings-label"))
        widget_list.append(Static(f"  [dim]{self.app.db.db_path}[/dim]", classes="settings-hint"))
        widget_list.append(
            Static("  All progress, notes, and achievements are stored locally", classes="settings-hint"))
        widget_list.append(Button("Export Portfolio", id="export-portfolio", variant="primary"))
        widget_list.append(Button("Reset Progress", id="reset-progress", variant="error"))
        widget_list.append(Static(""))

        # KEYBOARD SHORTCUTS SECTION
        widget_list.append(Rule())
        widget_list.append(Static("\n  [bold]KEYBOARD SHORTCUTS[/]", classes="settings-section-header"))
        widget_list.append(Static(""))

        # Navigation Shortcuts
        widget_list.append(Static("  NAVIGATION", classes="settings-label"))
        widget_list.append(Container(
            Container(
                Static("  Ctrl + L", classes="shortcut-key"),
                Static("Lessons", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + G", classes="shortcut-key"),
                Static("Playground", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + H", classes="shortcut-key"),
                Static("Challenges", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + M", classes="shortcut-key"),
                Static("Missions", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + A", classes="shortcut-key"),
                Static("Achievements", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + N", classes="shortcut-key"),
                Static("Notes", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + R", classes="shortcut-key"),
                Static("Analytics", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + D", classes="shortcut-key"),
                Static("Dashboard", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            classes="shortcut-grid"
        ))

        widget_list.append(Static(""))

        # Action Shortcuts
        widget_list.append(Static("  ACTIONS", classes="settings-label"))
        widget_list.append(Container(
            Container(
                Static("  Ctrl + P", classes="shortcut-key"),
                Static("Command Palette", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Ctrl + Q", classes="shortcut-key"),
                Static("Quit Application", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            Container(
                Static("  Escape", classes="shortcut-key"),
                Static("Back to Dashboard", classes="shortcut-desc"),
                classes="shortcut-row"
            ),
            classes="shortcut-grid"
        ))

        widget_list.append(Static(""))
        widget_list.append(Rule())

        # Mount all widgets
        for widget in widget_list:
            scroll.mount(widget)

        # Set theme select value after mount
        def set_theme_value():
            try:
                theme_select.value = current_theme
            except Exception:
                pass

        self.call_after_refresh(set_theme_value)

    @on(Button.Pressed, "#save-username")
    def save_username(self) -> None:
        name = self.query_one("#username-input", Input).value.strip()
        if name:
            self.app.db.update_user(username=name)
            self.app.show_notification(f"Username updated: {name}", severity="information")
            self._build_settings()

    @on(Button.Pressed, "#apply-theme")
    def apply_theme(self) -> None:
        theme_select = self.query_one("#theme-select", Select)
        if theme_select.value and theme_select.value != Select.BLANK:
            self.app.db.set_theme(str(theme_select.value))
            self.app.show_notification(
                f"Theme changed to '{theme_select.value}'. Restart to apply.",
                severity="information"
            )

    @on(Button.Pressed, "#gh-pat")
    def connect_pat(self) -> None:
        pat = self.query_one("#pat-input", Input).value.strip()
        if not pat:
            self.app.show_notification("GitHub token required", severity="warning")
            return
        ok, msg = self.app.github_sync.authenticate_pat(pat)
        if ok:
            self.app.show_notification(msg, severity="information")
            self._build_settings()
        else:
            self.app.show_notification(f"Authentication failed: {msg}", severity="error")

    @on(Button.Pressed, "#gh-disconnect")
    def disconnect_gh(self) -> None:
        self.app.github_sync.disconnect()
        self._build_settings()
        self.app.show_notification("Disconnected from GitHub", severity="information")

    @on(Button.Pressed, "#publish-portfolio")
    def publish_portfolio(self) -> None:
        content, path = self.app.progress_engine.generate_portfolio()
        result = self.app.github_sync.publish_portfolio(content)
        if result.success:
            self.app.show_notification(
                f"Portfolio published: {result.repo_url}", severity="information"
            )
        else:
            self.app.show_notification(f"Publish failed: {result.error}", severity="error")

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
                self.app.db.conn.executescript("""
                    DELETE FROM lesson_history;
                    DELETE FROM challenge_history;
                    DELETE FROM mission_history;
                    DELETE FROM achievements;
                    DELETE FROM command_history;
                    DELETE FROM sessions;
                    UPDATE user SET xp=0, level=1, rank_title='Terminal Novice', streak=0;
                    UPDATE progress SET lessons_completed=0, challenges_solved=0,
                        missions_completed=0, quizzes_taken=0, quiz_correct=0,
                        commands_executed=0, time_spent_mins=0, tracks_completed='[]';
                """)
                self.app.db.conn.commit()
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