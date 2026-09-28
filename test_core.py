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


def test_safe_export_filename_blocks_path_traversal():
    from utils import safe_export_filename
    traversal = safe_export_filename("../.bashrc")
    assert "/" not in traversal and not traversal.startswith(".")
    assert "/" not in safe_export_filename("a/b/c")
    assert safe_export_filename("   ") == "export"
    assert safe_export_filename("x", default="fallback") != ""


def test_split_pipeline_respects_quotes():
    from utils import split_pipeline
    assert split_pipeline("grep ERROR f | sort | uniq -c") == [
        "grep ERROR f", "sort", "uniq -c",
    ]
    # A '|' inside quotes is not a pipeline boundary.
    piped_inside_quotes = "awk '{print $1\"|\"$2}'"
    assert split_pipeline(piped_inside_quotes) == [piped_inside_quotes]


def test_explain_pipeline_describes_each_stage():
    from playground import PlaygroundEngine

    # explain_pipeline is pure text processing — it does not touch self.db.
    engine = PlaygroundEngine.__new__(PlaygroundEngine)
    stages = engine.explain_pipeline("grep 'ERROR' server.log | awk '{print $NF}' | sort | uniq -c")

    assert [s["tool"] for s in stages] == ["grep", "awk", "sort", "uniq"]
    assert all(s["description"] for s in stages)


def test_timed_mode_override_replaces_challenge_time_limit(tmp_path: Path):
    from data_manager import DataManager
    from challenge import ChallengeEngine

    db = DataManager(tmp_path / "shellmentor.db")
    engine = ChallengeEngine(db)
    challenge_id = engine._challenges_data[0]["id"]

    # None of the shipped challenges carry their own time_limit.
    active = engine.start_challenge(challenge_id)
    assert active.time_limit == 0

    timed = engine.start_challenge(challenge_id, time_limit_override=300)
    assert timed.time_limit == 300

    untimed_again = engine.start_challenge(challenge_id, time_limit_override=0)
    assert untimed_again.time_limit == 0
    db.close()


def test_backup_export_import_roundtrip(tmp_path: Path):
    from data_manager import DataManager

    src = DataManager(tmp_path / "source.db")
    src.update_user(username="Ada")
    src.add_xp(500)
    src.create_note("My Note", "Some content")
    backup_path = src.export_backup(tmp_path / "backup.json")
    src.close()

    dst = DataManager(tmp_path / "dest.db")
    dst.update_user(username="Someone Else")
    restored = dst.import_backup(backup_path)
    assert restored["user"] == 1
    assert restored["notes"] == 1

    user = dst.get_user()
    assert user["username"] == "Ada"
    assert user["xp"] == 500
    assert len(dst.get_notes()) == 1
    dst.close()


def test_import_backup_rejects_unrecognised_file(tmp_path: Path):
    from data_manager import DataManager

    bogus = tmp_path / "not_a_backup.json"
    bogus.write_text('{"hello": "world"}')

    db = DataManager(tmp_path / "shellmentor.db")
    try:
        db.import_backup(bogus)
        assert False, "expected ValueError for an unrecognised backup file"
    except ValueError:
        pass
    db.close()


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
