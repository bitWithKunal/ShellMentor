"""
ShellMentor - main.py
Entry point. Composes the full Textual application with all screens,
global keybindings, event wiring, and first-run flow.
"""

from __future__ import annotations

import getpass
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.theme import Theme
from textual.widgets import Footer, Header, Label, ListItem, ListView, Input
from textual.containers import Container
from textual import on
from textual.screen import Screen

from data_manager import DataManager
from learning import LearningEngine
from challenge import ChallengeEngine
from playground import PlaygroundEngine
from progress import ProgressEngine, LevelUpEvent
from utils import detect_system, APP_VERSION, load_yaml, THEMES_DIR

# ── Import all screens from ui module ──
from ui import (
    DashboardScreen, LessonsScreen, PlaygroundScreen,
    ChallengesScreen, MissionsScreen, AchievementsScreen,
    NotesScreen, AnalyticsScreen, SettingsScreen,
    EnvScanScreen, LevelUpModal, AchievementModal,
    GitHubSpaceScreen,
)

logger = logging.getLogger("shellmentor")

LOG_PATH = Path.home() / ".shellmentor.log"


def configure_logging() -> None:
    """Attach a rotating file handler to ShellMentor's own logger.

    Called from main() rather than at import time so importing this module
    (tests, tooling) does not reconfigure root logging for the whole process.
    """
    if logger.handlers:
        return
    try:
        handler = RotatingFileHandler(
            LOG_PATH, maxBytes=512_000, backupCount=2, encoding="utf-8"
        )
    except OSError:
        return
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False


# ──────────────────────── OS username detection ────────────────────────

def detect_system_username() -> str:
    """Return the real Linux account name, with graceful fallbacks."""
    for getter in (
        lambda: os.environ.get("USER"),
        lambda: os.environ.get("LOGNAME"),
        lambda: getpass.getuser(),
    ):
        try:
            name = getter()
            if name:
                return str(name).strip()
        except Exception:
            continue
    return "Learner"


# ──────────────────────── Theme registry ────────────────────────

def build_themes() -> dict[str, Theme]:
    """Build Textual Theme objects from themes/themes.yaml.

    Falls back to sensible defaults if the file is missing so Settings always
    has something to show.
    """
    themes: dict[str, Theme] = {}
    try:
        data = load_yaml(THEMES_DIR / "themes.yaml") or {}
    except Exception as e:
        logger.warning(f"Could not load themes.yaml: {e}")
        data = {}

    for theme_id, spec in data.get("themes", {}).items():
        colors = spec.get("colors", {})
        base = spec.get("base", "dark")
        try:
            themes[theme_id] = Theme(
                name=theme_id,
                primary=colors.get("primary", "#00d4ff"),
                secondary=colors.get("secondary", "#0099cc"),
                accent=colors.get("accent", "#ff6b35"),
                success=colors.get("success", "#10b981"),
                warning=colors.get("warning", "#f59e0b"),
                error=colors.get("error", "#ef4444"),
                foreground=colors.get("text", "#e6edf3"),
                background=colors.get("surface", "#0d1117"),
                surface=colors.get("surface2", "#161b22"),
                panel=colors.get("surface3", "#21262d"),
                dark=(base != "light"),
                variables={
                    "border": colors.get("border", "#30363d"),
                    "text-muted": colors.get("text_muted", "#7d8590"),
                    "text-dim": colors.get("text_dim", "#484f58"),
                    "xp-color": colors.get("xp_color", "#ffd700"),
                },
            )
        except Exception as e:
            logger.warning(f"Skipping theme '{theme_id}': {e}")

    return themes


# ──────────────────────── CSS ────────────────────────

SHELLMENTOR_CSS = """
/* Every rule below reads from the active Theme's variables ($primary,
 * $surface, $border, ...) instead of a fixed hex value, so picking a theme
 * in Settings actually re-skins the whole app instead of only the few
 * widgets that happened to use Textual's own defaults. */

/* ── Base ──────────────────────────────────────────── */
Screen {
    background: $background;
    color: $text;
}

Header {
    background: $secondary 15%;
    color: $primary;
    border-bottom: heavy $secondary;
    text-style: bold;
}

Footer {
    background: $secondary 15%;
    color: $text-muted;
    border-top: heavy $secondary;
}

/* ── Sidebar panels ────────────────────────────────── */
#lessons-sidebar, #ch-sidebar, #ms-sidebar,
#notes-sidebar, #pg-sidebar {
    width: 30;
    background: $primary 10%;
    border-right: heavy $secondary;
    padding: 0 1;
}

/* ── Content areas ─────────────────────────────────── */
#lesson-content, #ch-detail, #ms-detail,
#notes-editor, #pg-main {
    background: $background;
    padding: 0 1;
}

/* ── Playground output terminal ────────────────────── */
#pg-output {
    background: $surface-darken-1;
    border: solid $secondary;
    margin: 0 1;
}

#pg-input-row {
    height: 3;
    padding: 0 1;
    margin: 0;
    border-top: solid $secondary;
}

#pg-prompt {
    width: 3;
    padding: 1 0;
    color: $primary;
    text-style: bold;
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
    background: $surface;
    color: $text;
    border: solid $secondary;
}

Input:focus {
    border: solid $primary;
}

/* ── Buttons ───────────────────────────────────────── */
Button {
    background: $panel;
    color: $text;
    border: solid $secondary;
    margin: 0 1 1 0;
    text-style: bold;
}

Button:hover {
    background: $panel-lighten-1;
    color: $text;
}

Button:focus {
    border: solid $primary;
}

/* Variant buttons keep a neutral $panel background at rest — $panel is
 * guaranteed distinct from every accent color in every shipped theme, unlike
 * pairing an accent with its own "-background"/"-muted" shade, which came
 * out IDENTICAL to the accent itself under Professional Light (invisible
 * button text). On hover the background goes solid; `color: auto` there
 * picks black or white for contrast instead of a hardcoded white, which
 * would fail against a bright accent (Matrix, Cyber). */
Button.-primary {
    background: $panel;
    color: $primary;
    border: solid $primary;
}

Button.-primary:hover {
    background: $primary;
    color: auto;
}

Button.-success {
    background: $panel;
    color: $success;
    border: solid $success;
}

Button.-success:hover {
    background: $success;
    color: auto;
}

Button.-warning {
    background: $panel;
    color: $warning;
    border: solid $warning;
}

Button.-warning:hover {
    background: $warning;
    color: auto;
}

Button.-error {
    background: $panel;
    color: $error;
    border: solid $error;
}

Button.-error:hover {
    background: $error;
    color: auto;
}

/* ── ListView ──────────────────────────────────────── */
ListView {
    background: $surface;
    border: solid $secondary;
    height: 1fr;
}

ListItem {
    padding: 0 1;
    color: $text;
}

ListItem:hover {
    background: $border;
}

ListItem.-highlighted {
    background: $panel;
    color: $primary;
}

/* ── ScrollableContainer ───────────────────────────── */
ScrollableContainer {
    background: $background;
}

/* ── TextArea ──────────────────────────────────────── */
TextArea {
    background: $surface-darken-1;
    color: $text;
    border: solid $secondary;
    height: 1fr;
}

TextArea:focus {
    border: solid $primary;
}

/* ── Select ────────────────────────────────────────── */
Select {
    background: $surface;
    color: $text;
    border: solid $secondary;
    width: 32;
}

/* ── Rule ──────────────────────────────────────────── */
Rule {
    color: $border;
    margin: 1 0;
}

/* ── RichLog (terminals) ───────────────────────────── */
RichLog {
    background: $surface-darken-1;
    height: 1fr;
}

/* ── Layouts ───────────────────────────────────────── */
#lessons-layout, #ch-layout, #ms-layout,
#notes-layout, #pg-layout, #cs-layout {
    height: 1fr;
}

#cs-output, #mission-output {
    height: 1fr;
    background: $surface-darken-1;
    border: solid $secondary;
    margin: 0 1;
}

#cs-input-row, #mission-input-row {
    height: 3;
    padding: 0 1;
    border-top: solid $secondary;
}

#cs-prompt { width: 3; padding: 1 0; color: $primary; text-style: bold; }

#mission-info {
    max-height: 10;
    padding: 0 1;
    border-bottom: solid $secondary;
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
    background: $surface;
    border: solid $secondary;
}

DataTable > .datatable--header {
    background: $border;
    color: $primary;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: $primary 40%;
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
        ("GIT SPACE",          "github_space"),
        ("EXPORT PORTFOLIO",   "export_portfolio"),
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
        background: $surface;
        border: solid $primary;
        width: 50;
        height: 22;
        padding: 1;
    }
    #palette-list {
        height: 16;
        background: $surface;
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
        Binding("ctrl+t", "go_settings",       "Settings"),
        Binding("ctrl+u", "go_github_space",   "Git Space"),
        Binding("ctrl+d", "go_dashboard",      "Dashboard"),
        Binding("ctrl+q", "quit",              "Quit"),
        Binding("f1",     "go_dashboard",      "Dashboard", show=False),
    ]

    def __init__(self, db_path: Path | None = None, **kwargs):
        super().__init__(**kwargs)
        # Initialize core services. db_path lets tests (and anyone embedding
        # the app) run against a scratch database instead of the real one.
        self.db               = DataManager(db_path)
        self.learning_engine  = LearningEngine(self.db)
        self.progress_engine  = ProgressEngine(self.db)
        self.challenge_engine = ChallengeEngine(self.db, self.progress_engine)
        self.playground_engine= PlaygroundEngine(self.db)

        # Temp state
        self._selected_challenge: str | None = None
        self._selected_mission:   str | None = None
        self._achievement_queue:  list[dict] = []

        # Session time tracking (feeds the live "Time" stat on the dashboard)
        self._session_start: float = time.monotonic()
        self._session_timer = None

        # Pre-build all Textual Theme objects from themes.yaml
        self._theme_registry: dict[str, Theme] = build_themes()

        # Sync real Linux username into DB on first launch
        self._sync_system_username()

        # Wire gamification callbacks
        self.progress_engine.on_achievement(self._on_achievement)
        self.progress_engine.on_levelup(self._on_levelup)

        # Update streak on launch
        self.db.update_streak()

    # ── Theme helpers ─────────────────────────────────────────

    def _sync_system_username(self) -> None:
        """Replace the 'Learner' placeholder with the real OS account name."""
        try:
            current = (self.db.get_user().get("username") or "").strip()
            if current in ("", "Learner"):
                real = detect_system_username()
                if real and real != current:
                    self.db.update_user(username=real)
        except Exception as e:
            logger.warning(f"Could not sync system username: {e}")

    def theme_ids(self) -> list[str]:
        """Ordered list of available theme IDs for the Settings dropdown."""
        return list(self._theme_registry.keys())

    def apply_saved_theme(self) -> None:
        """Read the DB-persisted theme and apply it live to the app."""
        theme_id = self.db.get_theme()
        if theme_id not in self._theme_registry:
            theme_id = next(iter(self._theme_registry), "textual-dark")
        try:
            self.theme = theme_id
        except Exception as e:
            logger.warning(f"Could not apply saved theme '{theme_id}': {e}")

    def set_and_apply_theme(self, theme_id: str) -> bool:
        """Persist and apply a theme live.  Returns True on success."""
        if theme_id not in self._theme_registry:
            return False
        self.db.set_theme(theme_id)
        try:
            self.theme = theme_id
            return True
        except Exception as e:
            logger.warning(f"Theme switch failed for '{theme_id}': {e}")
            return False

    # ── Session timer ─────────────────────────────────────────

    def _flush_session_time(self) -> None:
        """Write full elapsed minutes to the DB; keep the remainder."""
        try:
            elapsed = time.monotonic() - self._session_start
            if elapsed >= 60:
                minutes = int(elapsed // 60)
                self.db.increment_progress(time_spent_mins=minutes)
                self._session_start += minutes * 60
        except Exception as e:
            logger.warning(f"Session time flush failed: {e}")

    def compose(self) -> ComposeResult:
        """Compose the base layout - only Header and Footer."""
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        """Register themes, start session timer, push initial screens."""
        # Register all themes with Textual so self.theme = id works live
        for theme in self._theme_registry.values():
            try:
                self.register_theme(theme)
            except Exception as e:
                logger.warning(f"Could not register theme '{theme.name}': {e}")

        # Apply the theme saved in DB (live, no restart needed)
        self.apply_saved_theme()

        # Flush accrued session time to DB every 30 s
        self._session_timer = self.set_interval(30.0, self._flush_session_time)

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

    def action_go_github_space(self) -> None:
        self._navigate_to(GitHubSpaceScreen)

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
                "github_space":     self.action_go_github_space,
                "export_portfolio": self._export_portfolio,
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

    def on_unmount(self) -> None:
        """Persist remaining session time when the app exits."""
        self._flush_session_time()

    def action_quit(self) -> None:
        """Quit the application gracefully."""
        self._flush_session_time()
        self.db.close()
        self.exit()


# ──────────────────────── Entry Point ────────────────────────

def main() -> None:
    """Launch ShellMentor."""
    # Verify Python 3.10+
    if sys.version_info < (3, 10):
        print(f"ShellMentor requires Python 3.10+. Found: {sys.version}")
        sys.exit(1)

    configure_logging()
    app = ShellMentorApp()
    app.run()


if __name__ == "__main__":
    main()
