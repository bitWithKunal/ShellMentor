"""Basic smoke tests for ShellMentor core engines."""
import sys
from pathlib import Path

# Ensure shellmentor package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "shellmentor"))


def test_sandbox_blocks_dangerous_commands():
    from utils import SandboxEngine, WORKSPACE_DIR
    sandbox = SandboxEngine(WORKSPACE_DIR)
    result = sandbox.run("rm -rf /")
    assert result.blocked, "Sandbox must block rm -rf /"
    result2 = sandbox.run("sudo apt install malware")
    assert result2.blocked, "Sandbox must block sudo"


def test_sandbox_allows_safe_commands():
    from utils import SandboxEngine, WORKSPACE_DIR
    sandbox = SandboxEngine(WORKSPACE_DIR)
    result = sandbox.run("echo hello")
    assert not result.blocked, "echo should not be blocked"
    assert "hello" in result.stdout


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
