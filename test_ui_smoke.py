"""Headless UI smoke tests.

Every screen is mounted through Textual's test pilot and the app is checked
for worker exceptions afterwards. Compile-only CI cannot catch a NameError in
a screen body or a method that shadows a Textual internal, which is exactly
how the 4.3.0 analytics and challenge-screen crashes shipped.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

SCREEN_ACTIONS = [
    "go_dashboard", "go_lessons", "go_playground", "go_challenges",
    "go_missions", "go_achievements", "go_notes", "go_analytics",
    "go_settings", "go_github_space",
]


def _make_app(tmp_path: Path):
    import data_manager
    from main import ShellMentorApp

    db_path = tmp_path / "smoke.db"
    app = ShellMentorApp.__new__(ShellMentorApp)
    ShellMentorApp.__init__(app, db_path=db_path)
    assert isinstance(app.db, data_manager.DataManager)
    return app


def _run(coro):
    return asyncio.run(coro)


def test_every_screen_mounts_without_error(tmp_path: Path):
    app = _make_app(tmp_path)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for action in SCREEN_ACTIONS:
                getattr(app, f"action_{action}")()
                await pilot.pause()
                await asyncio.sleep(0.3)
                assert app._exception is None, f"{action}: {app._exception!r}"

    _run(scenario())


def test_analytics_renders_content_for_a_new_user(tmp_path: Path):
    """Regression: the analytics worker died and mounted nothing at all."""
    app = _make_app(tmp_path)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_go_analytics()
            await pilot.pause()
            await asyncio.sleep(0.5)
            assert app._exception is None, repr(app._exception)
            scroll = app.screen.query_one("#analytics-scroll")
            assert len(scroll.children) > 0, "analytics rendered no widgets"

    _run(scenario())


def test_challenge_screen_opens_and_scores_a_solution(tmp_path: Path):
    """Regression: _update_timer shadowed Textual's Screen._update_timer."""
    from ui_activities import ChallengeScreen

    app = _make_app(tmp_path)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            challenge = app.challenge_engine._challenges_data[0]
            app.push_screen(ChallengeScreen(challenge["id"]))
            await pilot.pause()
            await asyncio.sleep(0.3)
            assert app._exception is None, repr(app._exception)

            app.screen.query_one("#cs-input").value = challenge["solution"]
            app.screen._do_submit()
            await pilot.pause()
            await asyncio.sleep(0.3)
            assert app._exception is None, repr(app._exception)
            assert challenge["id"] in app.db.get_solved_challenges()
            row = app.db.conn.execute(
                "SELECT last_command FROM challenge_history WHERE challenge_id=?",
                (challenge["id"],),
            ).fetchone()
            assert row["last_command"] == challenge["solution"]

    _run(scenario())


def test_mission_counts_one_completion_and_rejects_junk(tmp_path: Path):
    """Regression: every stage bumped missions_completed, and any text passed."""
    from textual.screen import ModalScreen
    from ui_activities import MissionScreen

    app = _make_app(tmp_path)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            mission = app.challenge_engine._missions_data[0]
            app.push_screen(MissionScreen(mission["id"]))
            await pilot.pause()
            await asyncio.sleep(0.3)
            screen = app.screen

            # Junk must not advance the mission.
            screen.query_one("#mission-input").value = "not a real answer"
            screen.next_stage()
            await pilot.pause()
            assert app._exception is None, repr(app._exception)
            assert app.db.get_mission_progress(mission["id"]) == 0

            for stage in mission["stages"]:
                if app.screen is not screen:
                    break
                screen.query_one("#mission-input").value = stage["solution"]
                screen.next_stage()
                await pilot.pause()
                await asyncio.sleep(0.2)
                # A stage can earn an achievement, which pushes a modal (e.g.
                # AchievementModal) on top of the mission screen — dismiss it
                # like a user pressing Enter, rather than mistaking it for
                # the mission itself having ended.
                while app.screen is not screen and isinstance(app.screen, ModalScreen):
                    await pilot.press("enter")
                    await pilot.pause()
                    await asyncio.sleep(0.1)

            assert app._exception is None, repr(app._exception)
            assert app.db.get_progress()["missions_completed"] == 1

    _run(scenario())


def test_timed_mode_toggle_starts_challenge_with_countdown(tmp_path: Path):
    """The Challenges browser's Timed Mode switch should force a countdown
    even though none of the shipped challenges carry their own time_limit."""
    from textual.widgets import Select, Switch
    from ui_activities import ChallengesScreen, ChallengeScreen

    app = _make_app(tmp_path)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.push_screen(ChallengesScreen())
            await pilot.pause()
            await asyncio.sleep(0.2)
            assert app._exception is None, repr(app._exception)

            challenge = app.challenge_engine._challenges_data[0]
            app._selected_challenge = challenge["id"]
            screen = app.screen
            screen.query_one("#ch-timed-switch", Switch).value = True
            screen.query_one("#ch-timed-duration", Select).value = 120
            screen.start_challenge()
            await pilot.pause()
            await asyncio.sleep(0.2)
            assert app._exception is None, repr(app._exception)

            assert isinstance(app.screen, ChallengeScreen)
            assert app.challenge_engine.active_challenge.time_limit == 120

    _run(scenario())


def test_dashboard_reset_button_clears_progress(tmp_path: Path):
    """The dashboard's own Reset Progress button (next to the stats grid)
    should work exactly like the one in Settings, behind the same confirm."""
    from ui_core import ConfirmModal

    app = _make_app(tmp_path)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.db.add_xp(500)
            assert app.db.get_user()["xp"] == 500

            app.action_go_dashboard()
            await pilot.pause()
            await asyncio.sleep(0.2)
            assert app._exception is None, repr(app._exception)

            screen = app.screen
            screen.query_one("#dash-reset-progress")  # button must exist
            screen.reset_progress_from_dashboard()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmModal)
            app.screen.dismiss(True)
            await pilot.pause()
            await asyncio.sleep(0.2)
            assert app._exception is None, repr(app._exception)
            assert app.db.get_user()["xp"] == 0

    _run(scenario())


def test_achievements_screen_renders_earned_rows(tmp_path: Path):
    """Regression: earned rows produced invalid '[]...[/]' markup."""
    app = _make_app(tmp_path)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.db.award_achievement("first_lesson", 50)
            app.action_go_achievements()
            await pilot.pause()
            await asyncio.sleep(0.4)
            assert app._exception is None, repr(app._exception)
            scroll = app.screen.query_one("#ach-scroll")
            assert len(scroll.children) > 0

    _run(scenario())
