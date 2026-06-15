"""
ShellMentor - ui_activities.py
Interactive learning activities: Challenges (browser + solver),
Missions (browser + runner) and the Achievements gallery.

This is where the active-session screens live. Each solver screen provides a
clearly laid-out control bar with Run / Submit / Hint / Main Menu / Quit so the
user is never stuck without a way to submit an answer or return to the menu.

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
from github_sync import GitHubSync
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
        Binding("ctrl+s", "submit", "Submit"),
        Binding("ctrl+d", "go_dashboard", "Main Menu"),
        Binding("ctrl+q", "quit", "Quit"),
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
            with Horizontal(id="cs-button-row"):
                yield Button("Submit", id="cs-submit", variant="success")
                yield Button("Hint", id="cs-hint", variant="warning")
                yield Button("Main Menu", id="cs-mainmenu", variant="default")
                yield Button("Quit", id="cs-quit", variant="error")
        yield Footer()

    DEFAULT_CSS = """
    #cs-layout {
        height: 1fr;
        padding: 1;
    }
    #cs-info {
        max-height: 10;
        height: auto;
        padding: 0 1;
    }
    #cs-output {
        height: 1fr;
        min-height: 5;
        background: #060a0f;
        border: solid #1e2030;
        margin: 0 1;
    }
    #cs-input-row {
        height: 3;
        padding: 0 1;
        border-top: solid #1e2030;
    }
    #cs-input-row #cs-input {
        width: 1fr;
    }
    #cs-input-row Button {
        width: 12;
    }
    #cs-prompt {
        width: 3;
        padding: 1 0;
        color: #89b4fa;
    }
    #cs-button-row {
        height: 3;
        padding: 0 1;
        align: left middle;
    }
    #cs-button-row Button {
        width: 16;
        margin: 0 1 0 0;
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
        self._do_submit()

    def action_submit(self) -> None:
        self._do_submit()

    def _do_submit(self) -> None:
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

    @on(Button.Pressed, "#cs-quit")
    def quit_app(self) -> None:
        self.app.challenge_engine.abandon_challenge()
        self.app.action_quit()

    def action_go_dashboard(self) -> None:
        self.app.challenge_engine.abandon_challenge()
        self.app.action_go_dashboard()

    def action_quit(self) -> None:
        self.app.challenge_engine.abandon_challenge()
        self.app.action_quit()





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
        with Vertical(id="mission-layout"):
            yield ScrollableContainer(id="mission-info", classes="panel")
            yield RichLog(id="mission-output", highlight=True, markup=True, auto_scroll=True)
            with Horizontal(id="mission-input-row"):
                yield Static("$", id="mission-prompt")
                yield Input(placeholder="Enter command for this stage...", id="mission-input")
                yield Button("Run", id="m-run", variant="primary")
                yield Button("Next Stage", id="m-next", variant="success")
            with Horizontal(id="mission-button-row"):
                yield Button("Hint", id="m-hint", variant="warning")
                yield Button("Main Menu", id="m-mainmenu", variant="default")
                yield Button("Quit", id="m-quit", variant="error")
        yield Footer()

    DEFAULT_CSS = """
    #mission-layout {
        height: 1fr;
        padding: 1;
    }
    #mission-info {
        max-height: 10;
        height: auto;
        padding: 0 1;
        border-bottom: solid #1e2030;
    }
    #mission-output {
        height: 1fr;
        min-height: 5;
        background: #060a0f;
        border: solid #1e2030;
        margin: 0 1;
    }
    #mission-prompt {
        width: 3;
        padding: 1 0;
        color: #89b4fa;
    }
    #mission-input-row {
        height: 3;
        padding: 0 1;
        border-top: solid #1e2030;
    }
    #mission-input-row #mission-input {
        width: 1fr;
    }
    #mission-input-row Button {
        width: 14;
        margin: 0 0 0 1;
    }
    #mission-button-row {
        height: 3;
        padding: 0 1;
        align: left middle;
    }
    #mission-button-row Button {
        width: 16;
        margin: 0 1 0 0;
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
        with Vertical(id="ach-layout"):
            yield ScrollableContainer(id="ach-scroll")
            with Horizontal(id="ach-button-row"):
                yield Button("Main Menu", id="ach-mainmenu", variant="default")
                yield Button("Quit", id="ach-quit", variant="error")

    DEFAULT_CSS = """
    #ach-layout {
        height: 1fr;
    }
    #ach-scroll {
        height: 1fr;
        padding: 1;
    }
    #ach-button-row {
        height: 3;
        padding: 0 1;
        align: left middle;
        border-top: solid #1e2030;
    }
    #ach-button-row Button {
        width: 16;
        margin: 0 1 0 0;
    }
    """

    @on(Button.Pressed, "#ach-mainmenu")
    def ach_main_menu(self) -> None:
        self.app.action_go_dashboard()

    @on(Button.Pressed, "#ach-quit")
    def ach_quit(self) -> None:
        self.app.action_quit()

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


