"""Core regression tests for ShellMentor's non-executing learning flow."""
import sys
from pathlib import Path


def test_command_lab_never_executes_user_input(tmp_path: Path):
    from data_manager import DataManager
    from playground import PlaygroundEngine

    db = DataManager(tmp_path / "shellmentor.db")
    result = PlaygroundEngine(db).submit_command("awk 'BEGIN { system(\"id\") }'")
    db.close()

    assert result.executed is False
    assert result.exit_code == 0
    assert "never executes" in result.stdout


def test_command_lab_records_submission(tmp_path: Path):
    from data_manager import DataManager
    from playground import PlaygroundEngine

    db = DataManager(tmp_path / "shellmentor.db")
    PlaygroundEngine(db).submit_command("grep ERROR server.log")
    history = db.get_command_history(context="playground")
    db.close()

    assert history[0]["command"] == "grep ERROR server.log"


def test_validate_output_line_count():
    from utils import validate_challenge_output
    ok, _ = validate_challenge_output("a\nb\nc", "", "line_count", 3)
    assert ok, "3 lines should match expected 3"
    ok2, msg = validate_challenge_output("a\nb", "", "line_count", 3)
    assert not ok2, "2 lines should not match expected 3"


def test_validate_output_empty():
    from utils import validate_challenge_output
    ok, _ = validate_challenge_output("", "", "pattern_match")
    assert not ok, "Empty output should fail"


def test_challenge_command_validation_does_not_execute():
    from challenge import ChallengeEngine

    challenge = {"solution": "grep -c ERROR server.log"}
    assert ChallengeEngine._validate_command_answer("grep -c ERROR server.log", challenge)[0]
    assert not ChallengeEngine._validate_command_answer("awk 'BEGIN {system(\"id\")}'", challenge)[0]


def test_level_computation():
    from data_manager import DataManager
    dm = DataManager.__new__(DataManager)
    level, title = dm._compute_level(0)
    assert level == 1
    level, title = dm._compute_level(600)
    assert level == 2
    level, title = dm._compute_level(50000)
    assert level == 12


def test_xp_format():
    from utils import format_xp
    assert format_xp(1000) == "1,000 XP"
    assert format_xp(0) == "0 XP"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
