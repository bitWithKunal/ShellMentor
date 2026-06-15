"""
ShellMentor - main.py
Entry point. Composes the full Textual application with all screens,
global keybindings, event wiring, and first-run flow.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static, Label, ListItem, ListView, Input
from textual.containers import Container, Horizontal, Vertical
from textual import on
from textual.screen import Screen

from data_manager import DataManager
from learning import LearningEngine
from challenge import ChallengeEngine
from playground import PlaygroundEngine
from progress import ProgressEngine, LevelUpEvent, XPEvent
from github_sync import GitHubSync
from utils import (
    detect_system, APP_NAME, APP_VERSION,
    load_yaml, THEMES_DIR, DATA_DIR, format_xp
)

# ── Import all screens from ui module ──
from ui import (
    DashboardScreen, LessonsScreen, PlaygroundScreen,
    ChallengesScreen, MissionsScreen, AchievementsScreen,
    NotesScreen, AnalyticsScreen, SettingsScreen,
    EnvScanScreen, LevelUpModal, AchievementModal,
    QuizScreen, ChallengeScreen, MissionScreen,
)

# ── Logging ──
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(Path.home() / ".shellmentor.log"),
    ]
)
logger = logging.getLogger("shellmentor")


# ──────────────────────── CSS ────────────────────────

SHELLMENTOR_CSS = """
/* ── Base ──────────────────────────────────────────── */
Screen {
    background: #0a0e14;
    color: #cdd6f4;
}

Header {
    background: #0e1117;
    color: #89b4fa;
    border-bottom: solid #1e2030;
}

Footer {
    background: #0e1117;
    color: #585b70;
    border-top: solid #1e2030;
}

/* ── Sidebar panels ────────────────────────────────── */
#lessons-sidebar, #ch-sidebar, #ms-sidebar,
#notes-sidebar, #pg-sidebar {
    width: 30;
    background: #0e1117;
    border-right: solid #1e2030;
    padding: 0 1;
}

/* ── Content areas ─────────────────────────────────── */
#lesson-content, #ch-detail, #ms-detail,
#notes-editor, #pg-main {
    background: #0a0e14;
    padding: 0 1;
}

/* ── Playground output terminal ────────────────────── */
#pg-output {
    background: #060a0f;
    border: solid #1e2030;
    margin: 0 1;
}

#pg-input-row {
    height: 3;
    padding: 0 1;
    margin: 0;
    border-top: solid #1e2030;
}

#pg-prompt {
    width: 3;
    padding: 1 0;
    color: #89b4fa;
}

/* ── Dashboard ─────────────────────────────────────── */
#dashboard-scroll, #scan-body {
    padding: 0 2;
}

#dash-top, #dash-mid, #dash-bot {
    padding: 0 1;
}

/* ── Input ─────────────────────────────────────────── */
Input {
    background: #0e1117;
    color: #cdd6f4;
    border: solid #1e2030;
}

Input:focus {
    border: solid #89b4fa;
}

/* ── Buttons ───────────────────────────────────────── */
Button {
    background: #1e2030;
    color: #cdd6f4;
    border: solid #313244;
    margin: 0 1 1 0;
}

Button:hover {
    background: #313244;
    color: #cdd6f4;
}

Button.-primary {
    background: #1e3a5f;
    color: #89b4fa;
    border: solid #1e6feb;
}

Button.-primary:hover {
    background: #1e6feb;
    color: #ffffff;
}

Button.-success {
    background: #1a3a2a;
    color: #a6e3a1;
    border: solid #2ea043;
}

Button.-success:hover {
    background: #2ea043;
    color: #ffffff;
}

Button.-error {
    background: #3a1a1a;
    color: #f38ba8;
    border: solid #b91c1c;
}

Button.-error:hover {
    background: #b91c1c;
    color: #ffffff;
}

/* ── ListView ──────────────────────────────────────── */
ListView {
    background: #0e1117;
    border: solid #1e2030;
    height: 1fr;
}

ListItem {
    padding: 0 1;
    color: #cdd6f4;
}

ListItem:hover {
    background: #1e2030;
}

ListItem.-highlighted {
    background: #1e2030;
}

/* ── ScrollableContainer ───────────────────────────── */
ScrollableContainer {
    background: #0a0e14;
}

/* ── TextArea ──────────────────────────────────────── */
TextArea {
    background: #060a0f;
    color: #cdd6f4;
    border: solid #1e2030;
    height: 1fr;
}

TextArea:focus {
    border: solid #89b4fa;
}

/* ── Select ────────────────────────────────────────── */
Select {
    background: #0e1117;
    color: #cdd6f4;
    border: solid #1e2030;
    width: 32;
}

/* ── Rule ──────────────────────────────────────────── */
Rule {
    color: #1e2030;
    margin: 1 0;
}

/* ── RichLog (terminals) ───────────────────────────── */
RichLog {
    background: #060a0f;
    height: 1fr;
}

/* ── Layouts ───────────────────────────────────────── */
#lessons-layout, #ch-layout, #ms-layout,
#notes-layout, #pg-layout, #cs-layout {
    height: 1fr;
}

#cs-output, #mission-output {
    height: 1fr;
    background: #060a0f;
    border: solid #1e2030;
    margin: 0 1;
}

#cs-input-row, #mission-input-row {
    height: 3;
    padding: 0 1;
    border-top: solid #1e2030;
}

#cs-prompt { width: 3; padding: 1 0; color: #89b4fa; }

#mission-info {
    max-height: 10;
    padding: 0 1;
    border-bottom: solid #1e2030;
}

/* ── Settings / Analytics ──────────────────────────── */
#settings-scroll, #analytics-scroll {
    padding: 0 2;
}

/* ── Modal ─────────────────────────────────────────── */
ModalScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.75);
}

/* ── DataTable ─────────────────────────────────────── */
DataTable {
    background: #0e1117;
    border: solid #1e2030;
}

DataTable > .datatable--header {
    background: #1e2030;
    color: #89b4fa;
}

DataTable > .datatable--cursor {
    background: #1e3a5f 80%;
}
"""


# ──────────────────────── Command Palette Screen ────────────────────────

class CommandPaletteScreen(Screen):
    """Quick global command palette."""

    BINDINGS = [Binding("escape", "dismiss_palette", "Close")]

    COMMANDS = [
        ("DASHBOARD",          "dashboard"),
        ("LESSONS",            "lessons"),
        ("PLAYGROUND",         "playground"),
        ("CHALLENGES",         "challenges"),
        ("MISSIONS",           "missions"),
        ("ACHIEVEMENTS",       "achievements"),
        ("NOTES",              "notes"),
        ("ANALYTICS",          "analytics"),
        ("SETTINGS",           "settings"),
        ("EXPORT PORTFOLIO",   "export_portfolio"),
        ("REFRESH DASHBOARD",  "refresh"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="palette-container"):
            yield Static("  [bold cyan]COMMAND PALETTE[/]\n")
            yield Input(placeholder="Search commands...", id="palette-search")
            yield ListView(id="palette-list")

    def on_mount(self) -> None:
        self._populate(self.COMMANDS)
        self.query_one("#palette-search").focus()

    def _populate(self, commands: list) -> None:
        lst = self.query_one("#palette-list", ListView)
        lst.clear()
        for label, action in commands:
            lst.append(ListItem(
                Label(f"  {label}"),
                id=f"cmd-{action}"
            ))

    @on(ListView.Selected, "#palette-list")
    def item_selected(self, event: ListView.Selected) -> None:
        if event.item.id:
            action = event.item.id.replace("cmd-", "")
            self.dismiss(action)

    def action_dismiss_palette(self) -> None:
        self.dismiss(None)

    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center middle;
        background: rgba(0,0,0,0.7);
    }
    #palette-container {
        background: #161b22;
        border: solid #00d4ff;
        width: 50;
        height: 22;
        padding: 1;
    }
    #palette-list {
        height: 16;
        background: #161b22;
    }
    """

    @on(Input.Changed, "#palette-search")
    def search_changed(self, event: Input.Changed) -> None:
        query = event.value.lower()
        filtered = [(l, a) for l, a in self.COMMANDS if query in l.lower()]
        self._populate(filtered)


# ──────────────────────── Main App ────────────────────────

class ShellMentorApp(App):
    """ShellMentor — Professional Linux Command-Line Learning Platform."""

    TITLE = f"ShellMentor v{APP_VERSION}"
    SUB_TITLE = "Linux Command-Line Mastery"

    CSS = SHELLMENTOR_CSS

    BINDINGS = [
        Binding("ctrl+p", "command_palette",   "Command Palette"),
        Binding("ctrl+l", "go_lessons",        "Lessons"),
        Binding("ctrl+g", "go_playground",     "Playground"),
        Binding("ctrl+h", "go_challenges",     "Challenges"),
        Binding("ctrl+m", "go_missions",       "Missions"),
        Binding("ctrl+a", "go_achievements",   "Achievements"),
        Binding("ctrl+n", "go_notes",          "Notes"),
        Binding("ctrl+r", "go_analytics",      "Analytics"),
        Binding("ctrl+s", "go_settings",       "Settings"),
        Binding("ctrl+d", "go_dashboard",      "Dashboard"),
        Binding("ctrl+q", "quit",              "Quit"),
        Binding("f1",     "go_dashboard",      "Dashboard", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize core services
        self.db               = DataManager()
        self.learning_engine  = LearningEngine(self.db)
        self.challenge_engine = ChallengeEngine(self.db)
        self.playground_engine= PlaygroundEngine(self.db)
        self.progress_engine  = ProgressEngine(self.db)
        self.github_sync      = GitHubSync(self.db)

        # Temp state
        self._selected_challenge: str | None = None
        self._selected_mission:   str | None = None
        self._achievement_queue:  list[dict] = []

        # Wire gamification callbacks
        self.progress_engine.on_achievement(self._on_achievement)
        self.progress_engine.on_levelup(self._on_levelup)

        # Update streak on launch
        self.db.update_streak()

    def compose(self) -> ComposeResult:
        """Compose the base layout - only Header and Footer."""
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted - push the initial screens."""
        # Push dashboard as the main screen
        self.push_screen(DashboardScreen())
        
        # Show environment scan on first launch (no commands executed yet)
        if self.db.get_progress().get("commands_executed", 0) == 0:
            system_info = detect_system()
            self.push_screen(
                EnvScanScreen(system_info),
                self._on_env_scan_done
            )

    def _on_env_scan_done(self, result=None) -> None:
        """Callback after environment scan is dismissed."""
        self.show_notification("Welcome to ShellMentor! Press Ctrl+P for command palette.", severity="information")

    # ── Navigation Actions ────────────────────────────────────

    def action_go_dashboard(self) -> None:
        self._navigate_to(DashboardScreen)

    def action_go_lessons(self) -> None:
        self._navigate_to(LessonsScreen)

    def action_go_playground(self) -> None:
        self._navigate_to(PlaygroundScreen)

    def action_go_challenges(self) -> None:
        self._navigate_to(ChallengesScreen)

    def action_go_missions(self) -> None:
        self._navigate_to(MissionsScreen)

    def action_go_achievements(self) -> None:
        self._navigate_to(AchievementsScreen)

    def action_go_notes(self) -> None:
        self._navigate_to(NotesScreen)

    def action_go_analytics(self) -> None:
        self._navigate_to(AnalyticsScreen)

    def action_go_settings(self) -> None:
        self._navigate_to(SettingsScreen)

    def action_command_palette(self) -> None:
        def handle_result(action: str | None) -> None:
            if not action:
                return
            action_map = {
                "dashboard":        self.action_go_dashboard,
                "lessons":          self.action_go_lessons,
                "playground":       self.action_go_playground,
                "challenges":       self.action_go_challenges,
                "missions":         self.action_go_missions,
                "achievements":     self.action_go_achievements,
                "notes":            self.action_go_notes,
                "analytics":        self.action_go_analytics,
                "settings":         self.action_go_settings,
                "export_portfolio": self._export_portfolio,
                "refresh":          lambda: None,
            }
            fn = action_map.get(action)
            if fn:
                fn()

        self.push_screen(CommandPaletteScreen(), handle_result)

    def _navigate_to(self, screen_class: type) -> None:
        """Pop back to base then push new screen."""
        # Pop all screens except the root (first screen in stack)
        # Keep at least 1 screen (the base) and the current screen might be different
        while len(self.screen_stack) > 1:
            try:
                self.pop_screen()
            except Exception:
                break
        
        # Push the new screen if we're not already on it
        if not isinstance(self.screen, screen_class):
            self.push_screen(screen_class())

    # ── Gamification Callbacks ────────────────────────────────

    def _on_achievement(self, achievement: dict) -> None:
        """Queue achievement modal for display."""
        self._achievement_queue.append(achievement)
        self._show_next_achievement()

    def _show_next_achievement(self) -> None:
        """Show the next achievement in queue."""
        if self._achievement_queue:
            ach = self._achievement_queue.pop(0)
            self.push_screen(
                AchievementModal(ach),
                lambda _: self._show_next_achievement()
            )

    def _on_levelup(self, event: LevelUpEvent) -> None:
        """Show level-up modal."""
        self.push_screen(LevelUpModal(event))

    # ── Notifications ─────────────────────────────────────────

    def show_notification(self, message: str, severity: str = "information") -> None:
        """Show a Textual notification toast."""
        self.notify(message, severity=severity, timeout=3)

    # ── Portfolio Export ──────────────────────────────────────

    def _export_portfolio(self) -> None:
        """Export portfolio to markdown file."""
        try:
            content, path = self.progress_engine.generate_portfolio()
            self.show_notification(f"Portfolio saved: {path}", severity="information")
        except Exception as e:
            self.show_notification(f"Export failed: {e}", severity="error")

    # ── Quit ──────────────────────────────────────────────────

    def action_quit(self) -> None:
        """Quit the application gracefully."""
        self.db.close()
        self.exit()


# ──────────────────────── Entry Point ────────────────────────

def main() -> None:
    """Launch ShellMentor."""
    # Verify Python 3.10+
    if sys.version_info < (3, 10):
        print(f"ShellMentor requires Python 3.10+. Found: {sys.version}")
        sys.exit(1)

    app = ShellMentorApp()
    app.run()


if __name__ == "__main__":
    main()
