# Changelog

All notable changes are documented here.

## 4.4.0

Bug-fix and correctness release. Every item below was reproduced before it was
changed; see issues.txt for the full report.

### Fixed — crashes
- Challenge screen crashed on open: `ChallengeScreen._update_timer` shadowed
  Textual's internal `Screen._update_timer` timer. Renamed to
  `_refresh_time_display`.
- Analytics screen rendered nothing: an undefined `user` in the level-progress
  card killed the render worker before any widget was mounted.
- Analytics crashed for new users: `AVG()`/`MIN()` return NULL with no solved
  challenges, and NULL cannot be formatted as a float.
- Mission runner raised `KeyError: 'xp_earned'` when advancing a mission that
  was already complete; stage results are now checked before use.

### Fixed — progression and data integrity
- Three achievement triggers were hardcoded true, so the first XP award granted
  ~1000 XP and three badges. They now evaluate real conditions (fastest solve,
  longest pipeline, portfolio generated).
- `award_achievement()` reported success for duplicate inserts because it read
  the connection-wide `total_changes`; it now uses `cursor.rowcount`.
- `missions_completed` counted every stage plus the completion, so a four-stage
  mission scored five. Stage rows and completion rows are now distinguished by
  a new `is_final` column, and completed missions are detected from it.
- Mission stages accepted any non-empty text. They are now validated against
  the stage's own reference solution.
- Lesson scores were always 100% because the code searched rendered text for
  "CORRECT", which also matches "INCORRECT" — including for the completion
  certificate. Exercise correctness is now tracked in state.
- Repeat lesson completions and challenge re-solves no longer inflate counters.
- The first-attempt XP bonus could never apply (attempts were counted after the
  XP calculation).
- The solved command was never stored; `challenge_history.last_command` now
  records the submitted command.
- Failed challenge attempts are recorded, so attempt counts, the analytics
  cards and difficulty suggestions reflect reality.
- Achievement XP is awarded through the normal XP path, so a level-up it
  triggers fires its event and modal.
- Unreachable achievements fixed: `commands_1000` and `perfect_score` had no
  backing stat, `all_tracks` used a lesson-count trigger, and 8 of 14 tracks had
  no trigger mapping.
- `note_taker`, `speed_demon`, `mission_complete` and `portfolio_published` were
  hand-awarded, bypassing their declared triggers.
- Lesson resume never worked: the position was written with an UPDATE against a
  row that only exists after completion. It now upserts.
- Quiz XP follows each question's own reward instead of a flat 10, and lesson
  exercise XP is actually granted (once per exercise).
- Reset All Progress now clears the challenge streak, hint-free count and the
  portfolio flag. Personal notes are deliberately preserved.
- Challenge and mission submissions no longer record the command twice.

### Fixed — interface
- Status markers (`[X]`, `[SOLVED]`, `[COMPLETED]`, `[LOCKED]`) were parsed as
  markup tags by Textual and vanished; they are plain glyphs now.
- Earned achievement rows produced invalid markup (`[]` ... `[/]`).
- Dashboard printed "1,000 XP XP".
- The difficulty suggestion was never shown and would have crashed if it were.
- Playground command history (Up/Down) and autocomplete (Tab) are wired up —
  previously the banner advertised them but nothing was bound.
- Notes warn before discarding unsaved edits, and note export sanitises the
  filename instead of trusting the title as a path.
- Settings moved from Ctrl+S to Ctrl+T: many terminals swallow Ctrl+S as flow
  control, and the challenge screen binds it to Submit. The shortcut list in
  Settings now matches the real bindings.
- The dashboard no longer re-renders its full ASCII block every second.

### Fixed — packaging and project
- `pyproject.toml` had no wheel file selection, so `uv run`, `uv sync` and
  `pip install .` all failed on this flat layout.
- Dependencies now carry upper bounds; the two crashes above came from Textual
  major-version drift under `textual>=0.80.0`.
- `workspace/` datasets are tracked in git — a fresh clone had no data files.
- Challenges referencing `data/` and `vlsi_report.txt` now point at files that
  exist, and the workspace catalogue matches the shipped fixtures.
- Added `test_ui_smoke.py`: every screen is mounted through Textual's headless
  pilot in CI, which is what compile-only CI could never catch.
- Log file rotates and logging is configured in `main()`, not at import time.
- Removed unused imports, three unused widgets, and the trigger-bypassing
  `_try_award()` helper. SQL column names are whitelisted.

### Migration
- On first launch, 4.4.0 recomputes `lessons_completed`, `challenges_solved`,
  `challenges_nohint`, `missions_completed` and `commands_executed` from the
  history tables, correcting counters inflated by earlier versions.

## 4.3.0

- Replaced all learner command execution with non-executing command recording and structural assessment.
- Converted Git actions to command guides that never invoke Git.
- Added CI for Python 3.10–3.12 and tag-driven release verification.
- Unified project, launcher, runtime, and documentation versions.
