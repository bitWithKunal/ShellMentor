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

from rich.text import Text

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Footer, Header, Input, Label, ListItem, ListView,
    RichLog, Rule, Select, Static, Switch,
)

from utils import difficulty_icon, difficulty_color, rarity_color

from ui_core import BaseScreen, HintModal, ConfirmModal

logger = logging.getLogger("shellmentor")


# ──────────────────────── Screen: Challenges ────────────────────────

class ChallengesScreen(BaseScreen):
    """Challenge browser and solver."""

    def __init__(self):
        super().__init__(screen_name="challenges")

    def render_content(self) -> ComposeResult:
        with Horizontal(id="ch-layout"):
            with Vertical(id="ch-sidebar"):
                yield Static("[bold orange1]CHALLENGES[/]")
                yield Select(
                    [(d, d) for d in ["all", "beginner", "intermediate", "advanced", "expert"]],
                    id="diff-filter",
                    prompt="Filter by difficulty",
                    value="all",
                )
                yield Rule()
                yield ListView(id="ch-list")
                yield Rule()
                with Horizontal(id="ch-timed-row"):
                    yield Static("⏱ Timed Mode", id="ch-timed-label")
                    yield Switch(value=False, id="ch-timed-switch")
                yield Select(
                    [("2 min", 120), ("5 min", 300), ("10 min", 600), ("15 min", 900)],
                    id="ch-timed-duration",
                    value=300,
                    allow_blank=False,
                )
                with Horizontal():
                    yield Button("Start", id="ch-start", variant="primary")
            with Vertical(id="ch-main"):
                yield ScrollableContainer(id="ch-detail")

    DEFAULT_CSS = """
    #ch-sidebar {
        width: 40;
        background: $surface;
        border-right: solid $secondary;
        padding: 1;
    }
    #ch-main {
        background: $background;
        padding: 1;
    }
    #ch-timed-row {
        height: 3;
        align: left middle;
    }
    #ch-timed-row #ch-timed-label {
        width: 1fr;
        color: $text;
    }
    """

    def on_mount(self) -> None:
        self._populate_challenges()
        self._show_difficulty_suggestion()
        # Seed the duration picker from the user's saved default (Settings ->
        # Challenge Timer); the switch itself always starts off, since a
        # timed run is an explicit per-attempt opt-in.
        minutes = self.app.db.get_setting("timed_challenge_minutes", 5)
        seconds = int(minutes) * 60
        valid_durations = {120, 300, 600, 900}
        duration_select = self.query_one("#ch-timed-duration", Select)
        duration_select.value = seconds if seconds in valid_durations else 300

    @work(exclusive=True)
    async def _show_difficulty_suggestion(self) -> None:
        suggestion = self.app.challenge_engine.suggest_difficulty()
        sidebar = self.query_one("#ch-sidebar", Vertical)
        # query_one() raises when there is no match, so use query() here.
        for old in self.query("#diff-suggestion"):
            await old.remove()
        if not suggestion:
            return
        if suggestion == "up":
            await sidebar.mount(
                Static("  [green]>> Try harder challenges![/]", id="diff-suggestion"),
                before=self.query_one("#ch-list"),
            )
        elif suggestion == "down":
            await sidebar.mount(
                Static("  [yellow]<< Try easier challenges[/]", id="diff-suggestion"),
                before=self.query_one("#ch-list"),
            )

    def _populate_challenges(self, difficulty: str = "") -> None:
        self._load_challenges_async(difficulty)

    @work(exclusive=True)
    async def _load_challenges_async(self, difficulty: str = "") -> None:
        ch_list = self.query_one("#ch-list", ListView)
        items = []
        for ch in self.app.challenge_engine.get_challenges(difficulty=difficulty):
            status = "✔" if ch["solved"] else difficulty_icon(ch["difficulty"])
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
            f"  {'[green]✔ SOLVED[/]' if solved else ''}\n"
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
        timed = self.query_one("#ch-timed-switch", Switch).value
        time_override = int(self.query_one("#ch-timed-duration", Select).value) if timed else None
        self.app.push_screen(ChallengeScreen(cid, time_limit_override=time_override))


class ChallengeScreen(Screen):
    """Active challenge solver."""

    BINDINGS = [
        Binding("escape", "abandon", "Abandon"),
        Binding("ctrl+h", "hint", "Hint"),
        Binding("ctrl+s", "submit", "Submit"),
        Binding("ctrl+d", "go_dashboard", "Main Menu"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, challenge_id: str, time_limit_override: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.challenge_id = challenge_id
        self.time_limit_override = time_limit_override

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="cs-layout"):
            yield ScrollableContainer(id="cs-info")
            yield Static("", id="cs-timer")
            yield Rule()
            yield RichLog(id="cs-output", highlight=True, markup=True, auto_scroll=True)
            with Horizontal(id="cs-input-row"):
                yield Static("$", id="cs-prompt")
                yield Input(placeholder="Enter your solution command...", id="cs-input")
                yield Button("Run", id="cs-run", variant="primary")
            with Horizontal(id="cs-button-row"):
                yield Button("Submit", id="cs-submit", variant="success")
                yield Button("Hint", id="cs-hint", variant="warning")
                yield Button("Retry", id="cs-retry", variant="default")
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
        background: $surface-darken-1;
        border: solid $secondary;
        margin: 0 1;
    }
    #cs-input-row {
        height: 3;
        padding: 0 1;
        border-top: solid $secondary;
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
        color: $primary;
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
        self._active = self.app.challenge_engine.start_challenge(
            self.challenge_id, time_limit_override=self.time_limit_override,
        )
        if not self._active:
            self.app.pop_screen()
            return

        self._timer = None
        ch = self._active.challenge
        info = self.query_one("#cs-info", ScrollableContainer)
        info.mount(Static(
            f"\n  [bold cyan]{ch['title']}[/]\n"
            f"  [bold]{ch['objective']}[/]\n"
            f"  [grey50]Dataset: {ch['dataset']}  |  "
            f"+{ch['xp_reward']} XP  |  "
            f"{len(ch.get('hints', []))} hints available[/]\n"
        ))

        # Start countdown timer if a time limit is active — either the
        # challenge's own, or the Timed Mode override chosen before starting.
        if self._active.time_limit > 0:
            self._refresh_time_display()
            self._timer = self.set_interval(1.0, self._tick_timer)

        output = self.query_one("#cs-output", RichLog)
        output.write(Text.from_markup(
            f"[grey50]Workspace file: [cyan]{ch['dataset']}[/] is ready.[/]\n"
            f"[grey50]Type your command, press Run to test, then Submit when ready.[/]\n"
        ))
        self.query_one("#cs-input", Input).focus()

    def _tick_timer(self) -> None:
        if not self._active:
            return
        if self._active.is_expired:
            if self._timer:
                self._timer.stop()
            self._on_timeout()
            return
        self._refresh_time_display()

    def _refresh_time_display(self) -> None:
        if not self._active or self._active.time_limit <= 0:
            return
        remaining = self._active.time_remaining
        mins, secs = divmod(int(remaining), 60)
        color = "red" if remaining < 30 else "yellow" if remaining < 60 else "green"
        timer = self.query_one("#cs-timer", Static)
        timer.update(Text.from_markup(
            f"  [{color}]TIME REMAINING: {mins}:{secs:02d}[/{color}]"
        ))

    def on_unmount(self) -> None:
        """Stop the countdown when the screen is dismissed."""
        timer = getattr(self, "_timer", None)
        if timer:
            timer.stop()
            self._timer = None

    def _write_explanation(self, output: RichLog, solution: str) -> None:
        """Write a stage-by-stage breakdown of *solution* to the output log.

        Purely descriptive — built from PlaygroundEngine.explain_pipeline(),
        which never runs the command. This is the "why this works" companion
        to just printing the reference command.
        """
        if not solution:
            return
        stages = self.app.playground_engine.explain_pipeline(solution)
        if len(stages) <= 1:
            return
        output.write(Text.from_markup("[bold]Why this works:[/]"))
        for stage in stages:
            output.write(Text.from_markup(
                f"  [cyan]{stage['stage']}.[/] [bold]{stage['command']}[/] "
                f"[grey50]— {stage['description']}[/]"
            ))

    def _on_timeout(self) -> None:
        output = self.query_one("#cs-output", RichLog)
        output.write(Text.from_markup(
            f"\n[red]TIME'S UP![/] Challenge auto-abandoned.\n"
        ))
        # The session is over — no more submissions against a dead challenge.
        self.query_one("#cs-input", Input).disabled = True
        self.query_one("#cs-submit", Button).disabled = True
        info = self.app.challenge_engine.abandon_challenge()
        if info and info.get("solution"):
            output.write(Text.from_markup(
                f"[bold]Solution:[/] {info['solution']}\n"
            ))
            self._write_explanation(output, info["solution"])
        self.app.show_notification("Time's up! Challenge abandoned.", severity="warning")

    @on(Input.Submitted, "#cs-input")
    @on(Button.Pressed, "#cs-run")
    def run_command(self, event=None) -> None:
        inp = self.query_one("#cs-input", Input)
        command = inp.value.strip()
        if not command:
            return

        if self._active:
            self._active.command_history.append(command)

        result = self.app.playground_engine.submit_command(command, context="challenge")
        output = self.query_one("#cs-output", RichLog)
        output.write(Text.from_markup(f"[cyan]$ {command}[/]"))
        if result.stdout:
            output.write(result.stdout.rstrip())
        if result.stderr:
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

        # submit_challenge() records the attempt itself; recording it here as
        # well double-counted every submission in "Commands run".
        submit_result = self.app.challenge_engine.submit_challenge(command)

        output = self.query_one("#cs-output", RichLog)
        if submit_result["solved"]:
            xp = submit_result["xp_earned"]
            output.write(Text.from_markup(
                f"\n[green]CHALLENGE SOLVED![/] [gold1]+{xp} XP[/]\n"
                f"[grey50]Time: {submit_result['elapsed']:.1f}s  "
                f"Hints: {submit_result['hints_used']}[/]\n"
                f"[dim]Reference: {submit_result.get('solution','')}[/]"
            ))
            self._write_explanation(output, submit_result.get("solution", ""))
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

    @on(Button.Pressed, "#cs-retry")
    def retry_challenge(self) -> None:
        self._active = self.app.challenge_engine.start_challenge(
            self.challenge_id, time_limit_override=self.time_limit_override,
        )
        if not self._active:
            return
        # Clear output and reset
        output = self.query_one("#cs-output", RichLog)
        output.clear()
        ch = self._active.challenge
        output.write(Text.from_markup(
            f"[grey50]Challenge restarted. Workspace: [cyan]{ch['dataset']}[/] ready.[/]\n"
        ))
        inp = self.query_one("#cs-input", Input)
        inp.disabled = False
        inp.value = ""
        inp.focus()
        self.query_one("#cs-submit", Button).disabled = False
        # Restart timer if applicable
        if self._timer:
            self._timer.stop()
        if self._active.time_limit > 0:
            self._refresh_time_display()
            self._timer = self.set_interval(1.0, self._tick_timer)
        else:
            self.query_one("#cs-timer", Static).update("")

    def action_abandon(self) -> None:
        def handle_confirm(confirmed: bool | None) -> None:
            if confirmed:
                info = self.app.challenge_engine.abandon_challenge()
                if info and info.get("solution"):
                    output = self.query_one("#cs-output", RichLog)
                    output.write(Text.from_markup(
                        f"\n[bold]Solution:[/] {info['solution']}\n"
                    ))
                self.app.pop_screen()

        self.app.push_screen(ConfirmModal("Abandon this challenge? Progress will be lost."), handle_confirm)

    @on(Button.Pressed, "#cs-mainmenu")
    def go_main_menu(self) -> None:
        info = self.app.challenge_engine.abandon_challenge()
        if info and info.get("solution"):
            output = self.query_one("#cs-output", RichLog)
            output.write(Text.from_markup(
                f"\n[bold]Solution:[/] {info['solution']}\n"
            ))
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
                yield Static("[bold gold1]MISSIONS[/]")
                yield ListView(id="ms-list")
                yield Button("Start Mission", id="ms-start", variant="primary")
                yield Rule()
                yield Button("Main Menu", id="back-to-dashboard", variant="default")
                yield Button("Quit", id="quit-app", variant="error")
            yield ScrollableContainer(id="ms-detail")

    DEFAULT_CSS = """
    #ms-sidebar {
        width: 40;
        background: $surface;
        border-right: solid $secondary;
        padding: 1;
    }
    #ms-detail {
        background: $background;
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
            status = "✔ complete" if done else f"{stages}/{total} stages"
            mission_title = m.get("title", m.get("name", "Unknown Mission"))
            label = f"  {mission_title}  [grey50]{status}[/]"
            ms_list.append(ListItem(Label(Text.from_markup(label)), id=f"ms-{m['id']}"))

    @on(ListView.Selected, "#ms-list")
    def mission_selected(self, event: ListView.Selected) -> None:
        mid = event.item.id.replace("ms-", "") if event.item.id else None
        if mid:
            self._show_mission_detail(mid)

    def _show_mission_detail(self, mission_id: str) -> None:
        self._load_mission_detail_async(mission_id)

    @work(exclusive=True)
    async def _load_mission_detail_async(self, mission_id: str) -> None:
        mission = self.app.challenge_engine.get_mission(mission_id)
        if not mission:
            return

        detail = self.query_one("#ms-detail", ScrollableContainer)
        await detail.remove_children()

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
                f"|  [gold1]+{mission_xp} XP total (awarded per stage)[/]  "
                f"|  Badge: {mission_badge}[/]\n"
            ),
            Rule(),
            Static("  [bold]MISSION STAGES:[/]\n"),
        ]

        for stage in stages:
            done = stage.get("stage", 0) <= completed_stages
            icon = "✔" if done else "○"
            stage_title = stage.get("title", f"Stage {stage.get('stage', '?')}")
            stage_xp = stage.get("xp", 0)
            stage_objective = stage.get("objective", "")
            widgets.append(Static(
                f"  {icon} {stage_title}  "
                f"[gold1]+{stage_xp} XP[/]\n"
                f"      [grey50]{stage_objective}[/]\n"
            ))

        await detail.mount(*widgets)
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
        border-bottom: solid $secondary;
    }
    #mission-output {
        height: 1fr;
        min-height: 5;
        background: $surface-darken-1;
        border: solid $secondary;
        margin: 0 1;
    }
    #mission-prompt {
        width: 3;
        padding: 1 0;
        color: $primary;
    }
    #mission-input-row {
        height: 3;
        padding: 0 1;
        border-top: solid $secondary;
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
        self._load_stage_info_async()

    @work(exclusive=True)
    async def _load_stage_info_async(self) -> None:
        info = self.query_one("#mission-info", ScrollableContainer)
        await info.remove_children()
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

        await info.mount(Static(
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
        result = self.app.playground_engine.submit_command(command, context="mission")
        output = self.query_one("#mission-output", RichLog)
        output.write(Text.from_markup(f"[cyan]$ {command}[/]"))
        if result.stdout:
            output.write(result.stdout.rstrip())
        if result.stderr:
            output.write(Text.from_markup(f"[red]{result.stderr.rstrip()}[/]"))

    @on(Button.Pressed, "#m-next")
    def next_stage(self) -> None:
        inp = self.query_one("#mission-input", Input)
        command = inp.value.strip()
        if not command:
            self.app.show_notification("Run a command first", severity="warning")
            return

        stage_result = self.app.challenge_engine.submit_mission_stage(command)
        output = self.query_one("#mission-output", RichLog)

        if not stage_result.get("passed"):
            output.write(Text.from_markup(
                f"[yellow]Not quite.[/] {stage_result.get('message', '')}\n"
                f"[grey50]Press Hint if you are stuck.[/]"
            ))
            return

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
                f"[gold1]Total XP earned this run: +{total_xp}[/]\n"
            ))
            # A mission's xp_reward is the *total* of its stage rewards, which
            # were already granted stage by stage — no extra XP here.
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
        border-top: solid $secondary;
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
        self.run_worker(self._render_achievements(), exclusive=True)

    async def _render_achievements(self) -> None:
        scroll = self.query_one("#ach-scroll", ScrollableContainer)
        await scroll.remove_children()

        stats = self.app.progress_engine.get_achievement_stats()
        all_ach = self.app.progress_engine.get_full_achievements_list()

        widgets = [Static(
            f"\n  [bold gold1]ACHIEVEMENTS[/]  "
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
                # An empty style name produces "[]...[/]", which is invalid
                # markup — always emit a real style.
                body = "bold" if earned else "grey50"
                widgets.append(Static(
                    f"  {'✔' if earned else '○'} "
                    f"[{body}]{ach['icon']} {ach['title']}[/{body}]  "
                    f"[gold1]+{ach.get('xp_reward', 0)} XP[/]  "
                    f"[{color}]{rarity}[/{color}]\n"
                    f"    [grey50]{ach['description']}[/grey50]"
                ))

        await scroll.mount(*widgets)

