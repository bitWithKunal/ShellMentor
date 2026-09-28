# Changelog

All notable changes are documented here.

## 4.5.0

Feature release: opt-in timed challenges, backup/restore, solution explanations, and a
theme system that actually re-skins the whole app — plus two more crash-on-launch bugs
of the same shape as 4.4.0's.

### Added
- **Timed Mode** for challenges: an opt-in countdown you choose per attempt from the
  Challenges browser, with a default duration set in Settings → Challenge Preferences.
  Previously a challenge could only be timed if the content author had set a
  `time_limit` in `challenges.json`, and none of the 50 shipped challenges do.
- **"Why this works"** — after solving a challenge (or on abandon/timeout), the
  reference solution is broken into pipeline stages with a plain-language description
  of each tool, built from the Command Lab's own help data. Purely textual; nothing is
  executed to produce it.
- **Backup and restore**: Settings → Export Backup (JSON) dumps every progress table to
  one file under `~/ShellMentor_Exports/`; Import Backup restores from it after a
  confirmation. Column names from the file are checked against the live schema before
  use, so a hand-edited backup can't inject SQL through a crafted key.
- Lesson certificates can be saved to a text file from the certificate modal, not just
  viewed once and dismissed.
- A **Reset Progress** shortcut on the Dashboard itself, next to the stats it affects,
  in addition to the one in Settings.

### Changed — theming
- The theme system now actually reaches the whole app. Previously, `main.py`'s app-wide
  CSS and every screen's `DEFAULT_CSS` used fixed hex colors, so switching themes in
  Settings only changed a handful of widgets that happened to already reference
  Textual's own default variables. All ~160 hardcoded colors across `main.py`,
  `ui_core.py`, `ui_screens.py` and `ui_activities.py` now read theme variables
  (`$primary`, `$surface`, `$border`, `$text-muted`, ...), so all 7 themes are now
  visually distinct end to end.
- Removed the `css:` block from every theme in `themes/themes.yaml` — confirmed dead in
  the 4.4.0 review (`build_themes()` never read it) and now genuinely superseded by the
  variable-driven CSS above.
- New default theme: **Cyber** (neon magenta/cyan/yellow), replacing Professional Dark
  for fresh installs. Existing users keep whatever theme they already chose.
- Section and screen headers (Settings' six sections, Challenges, Missions, Lessons,
  Notes, Achievements, Analytics, Git Space) now use distinct accent colors instead of
  every header being the same cyan.
- Sidebars, the header/footer bar, and panel borders now carry a tinted background and
  a heavier colored edge instead of a flat neutral fill.

### Fixed
- **App failed to launch**: `margin: auto` is not valid Textual CSS (it wants an
  explicit `1`/`2`/`4`-value margin) but was present in all five modals
  (`LevelUpModal`, `AchievementModal`, `HintModal`, `ConfirmModal`, `CertificateModal`).
  Textual validates a class's `DEFAULT_CSS` the first time that class is instantiated,
  and apparently also during startup in a real terminal run, so this could crash the
  app before the dashboard ever appeared. Centering already came from the app-wide
  `ModalScreen { align: center middle; }` rule, so the invalid declarations were both
  wrong and redundant — removed.
- **Achievement and certificate popups silently failed**: `color: grey50;` is valid in
  Rich's text markup but not in Textual's CSS color grammar (Textual suggested `grey`).
  This was in `AchievementModal`/`CertificateModal`'s `DEFAULT_CSS`, so earning an
  achievement or hitting a note that would print that footer text raised a
  `StylesheetErrors` that the achievement callback's `except Exception` swallowed —
  the modal just never appeared, with no visible error. Confirmed via a regression
  in the mission-completion test, which had been silently relying on this modal
  never actually rendering.
- **Invisible button/nav text under Professional Light**: `Button.-primary` and the
  active sidebar item used `$primary-background` as a background with `$primary` as
  the text color. Under Professional Light those two resolve to the *same* hex value —
  text identical to its own background. Every variant button now uses `$panel` (proven
  distinct from every accent in all 7 themes) at rest, and `color: auto` on hover so
  hover text stays readable against Cyber/Matrix's very light, saturated accents too.
- The Command Lab's `get_command_help()` table only covered 5 commands; expanded to
  ~28, since the new "why this works" breakdown depends on it for lesser-used tools.

### Tests
- `test_core.py`: `safe_export_filename`, `split_pipeline`, `explain_pipeline`, the
  Timed Mode override, and a full backup/export/import round trip.
- `test_ui_smoke.py`: the Timed Mode toggle end to end (switch → duration → active
  challenge's `time_limit`), and the Dashboard's own Reset Progress button. The mission
  regression test now dismisses an achievement modal instead of mistaking it for the
  mission screen having ended — which is what silently masked the `grey50` bug above.

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
