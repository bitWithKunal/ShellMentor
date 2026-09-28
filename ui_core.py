"""
ShellMentor - ui_core.py
Shared UI foundation: imports, navigation sidebar, BaseScreen, shared
widgets (XPBar, StatCard, SectionHeader) and all modal screens.

This module is imported by ui_screens.py and ui_activities.py. Splitting the
former monolithic ui.py keeps each file focused and avoids the layout bugs
that crept in when everything lived in one giant file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, Footer, Header, Rule, Static

from progress import LevelUpEvent
from utils import rarity_color, safe_export_filename

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
        background: $surface;
        color: $text-muted;
        border: none;
        border-left: wide $surface;
        text-style: bold;
    }
    NavButton:hover {
        background: $panel;
        color: $text;
        border-left: wide $secondary;
    }
    NavButton.-active {
        background: $panel;
        color: $primary;
        border-left: wide $primary;
    }
    """

class NavigationSidebar(Vertical):
    """Professional navigation sidebar."""

    DEFAULT_CSS = """
    NavigationSidebar {
        width: 28;
        background: $primary 10%;
        border-right: heavy $secondary;
        padding: 1 0;
    }
    .sidebar-header {
        padding: 0 2;
        margin-bottom: 1;
        text-style: bold;
        color: $accent;
    }
    .nav-spacer {
        height: 0;
    }
    .nav-home-btn {
        width: 100%;
        height: 3;
        margin: 0;
        background: $surface;
        border: solid $primary-darken-1;
        color: $primary;
        text-style: bold;
    }
    .nav-home-btn:hover {
        background: $primary;
        color: auto;
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
            ("github_space","GIT SPACE"),
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

    @on(Button.Pressed, "#nav-github_space")
    def nav_github_space(self) -> None:
        self.app.action_go_github_space()


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
        background: $surface;
        border: double $primary;
        width: 50;
        height: 16;
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
        background: $surface;
        border: solid gold;
        width: 50;
        height: 14;
        padding: 1 2;
    }
    #ach-header { color: gold; text-style: bold; }
    #ach-title  { color: cyan; text-style: bold; }
    #ach-desc   { color: $text; }
    #ach-xp     { color: gold; }
    #ach-hint   { color: $text-muted; }
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
        background: $surface;
        border: solid yellow;
        width: 55;
        height: 12;
        padding: 1 2;
    }
    #hint-title { color: yellow; text-style: bold; }
    #hint-text  { color: $text; }
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
            Static("⚠  PLEASE CONFIRM", id="confirm-title"),
            Rule(),
            Static(self.message, id="confirm-message"),
            Horizontal(
                Button("Yes, continue", id="yes", variant="error"),
                Button("Cancel", id="no", variant="default"),
                id="confirm-buttons",
            ),
            id="confirm-container",
        )

    DEFAULT_CSS = """
    ConfirmModal > Container {
        background: $surface;
        border: thick $warning;
        width: 60;
        height: auto;
        max-width: 90%;
        padding: 1 2;
    }
    #confirm-title {
        color: $warning;
        text-style: bold;
    }
    #confirm-message {
        color: $text;
        padding: 1 0;
        width: 100%;
    }
    #confirm-buttons {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    #confirm-buttons Button { margin-left: 1; margin-right: 0; }
    """

    @on(Button.Pressed, "#yes")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def cancel_btn(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class CertificateModal(ModalScreen):
    """Lesson completion certificate."""

    BINDINGS = [Binding("escape,enter,space", "dismiss", "Continue")]

    def __init__(self, lesson_title: str, track_id: str, score: int, xp: int, **kwargs):
        super().__init__(**kwargs)
        self.lesson_title = lesson_title
        self.track_id = track_id
        self.score = score
        self.xp = xp

    def compose(self) -> ComposeResult:
        now = self._issued_at().strftime("%Y-%m-%d %H:%M")
        grade = self._grade()
        yield Container(
            Static("CERTIFICATE OF COMPLETION", id="cert-header"),
            Rule(),
            Static(f"\n  This certifies that the learner has successfully completed", id="cert-body1"),
            Static(f"\n  [bold cyan]{self.lesson_title}[/]", id="cert-title"),
            Static(f"\n  Track: {self.track_id}  |  Score: {self.score}%  |  Grade: {grade}", id="cert-score"),
            Static(f"\n  XP Earned: +{self.xp}  |  Date: {now}", id="cert-xp"),
            Rule(),
            Static(f"\n  ShellMentor — Professional Linux Learning Platform", id="cert-footer"),
            Horizontal(
                Button("💾  Save to File", id="cert-save", variant="primary"),
                Button("Continue", id="cert-continue", variant="default"),
                id="cert-buttons",
            ),
            id="cert-container",
        )

    DEFAULT_CSS = """
    CertificateModal > Container {
        background: $surface;
        border: double gold;
        width: 58;
        height: 20;
        padding: 1 2;
    }
    #cert-header { color: gold; text-style: bold; text-align: center; }
    #cert-body1  { color: $text; }
    #cert-title  { color: cyan; text-style: bold; }
    #cert-score  { color: green; }
    #cert-xp     { color: gold; }
    #cert-footer { color: $text-muted; text-align: center; }
    #cert-buttons { align: center middle; height: 3; margin-top: 1; }
    """

    def _issued_at(self):
        from datetime import datetime
        return datetime.now()

    def _grade(self) -> str:
        return "A" if self.score >= 90 else "B" if self.score >= 80 else "C"

    def action_dismiss(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#cert-continue")
    def continue_pressed(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#cert-save")
    def save_to_file(self) -> None:
        now = self._issued_at()
        text = (
            "==============================================\n"
            "          CERTIFICATE OF COMPLETION\n"
            "==============================================\n\n"
            f"This certifies that the learner has successfully completed\n\n"
            f"    {self.lesson_title}\n\n"
            f"Track:      {self.track_id}\n"
            f"Score:      {self.score}%\n"
            f"Grade:      {self._grade()}\n"
            f"XP Earned:  +{self.xp}\n"
            f"Date:       {now.strftime('%Y-%m-%d %H:%M')}\n\n"
            "ShellMentor — Professional Linux Command-Line Learning Platform\n"
        )
        export_dir = Path.home() / "ShellMentor_Exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        safe = safe_export_filename(self.lesson_title, default="lesson")
        stamp = now.strftime("%Y%m%d_%H%M%S")
        path = export_dir / f"certificate_{safe}_{stamp}.txt"
        path.write_text(text, encoding="utf-8")
        self.app.show_notification(f"Certificate saved: {path}", severity="information")

