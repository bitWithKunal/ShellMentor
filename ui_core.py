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

