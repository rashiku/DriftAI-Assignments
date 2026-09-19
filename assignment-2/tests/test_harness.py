"""
Unit tests for the deterministic test harness (src/harness.py).

These tests do NOT require an ANTHROPIC_API_KEY — they only exercise the
non-LLM part of the pipeline (code extraction + sandboxed execution against
TEST_CASES), which is what Agent B's review is grounded in.

Run with:
    cd assignment-2
    python -m pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from harness import extract_code, run_harness  # noqa: E402

GOOD_SOLUTION = '''
```python
import re

_PATTERN = re.compile(r'^\\s*(?:(\\d+)h)?\\s*(?:(\\d+)m)?\\s*(?:(\\d+)s)?\\s*$')


def parse_duration(s: str) -> int:
    """Parse a duration string into total seconds.

    Raises:
        ValueError: on empty, malformed, or out-of-order input.
    """
    if not isinstance(s, str) or not s.strip():
        raise ValueError("empty input")
    match = _PATTERN.match(s)
    if not match or not any(match.groups()):
        raise ValueError(f"bad input: {s!r}")
    h, m, sec = (int(g) if g else 0 for g in match.groups())
    return h * 3600 + m * 60 + sec
```
'''

NO_DOCSTRING_SOLUTION = '''
```python
def parse_duration(s):
    total = 0
    num = ""
    for ch in s:
        if ch.isdigit():
            num += ch
        elif ch in "hms":
            total += int(num) * {"h": 3600, "m": 60, "s": 1}[ch]
            num = ""
    return total
```
'''

BANNED_CONSTRUCT_SOLUTION = '''
```python
def parse_duration(s: str) -> int:
    """Uses eval, which is banned."""
    return eval(s.replace("h", "*3600+").replace("m", "*60+").replace("s", "+0"))
```
'''

NO_CODE_BLOCK = "I think the answer is roughly 3600 seconds for one hour."


def test_extract_code_from_fenced_block():
    code = extract_code(GOOD_SOLUTION)
    assert code is not None
    assert "def parse_duration" in code


def test_extract_code_returns_none_when_absent():
    assert extract_code(NO_CODE_BLOCK) is None


def test_good_solution_passes_all_cases():
    result = run_harness(GOOD_SOLUTION)
    assert result.code_extracted
    assert result.function_found
    assert result.has_docstring
    assert not result.banned_hits
    assert result.ran_successfully
    assert result.all_passed
    assert result.passed_count == result.total_count
    assert result.total_count == 16


def test_missing_docstring_is_detected():
    result = run_harness(NO_DOCSTRING_SOLUTION)
    assert result.function_found
    assert result.has_docstring is False
    assert not result.all_passed  # fails overall due to missing docstring criterion


def test_weak_solution_fails_edge_cases_but_not_happy_path():
    result = run_harness(NO_DOCSTRING_SOLUTION)
    happy_path_inputs = {"1h", "45m", "90s", "1h30m"}
    failing_inputs = {r["input"] for r in result.test_results if not r["pass"]}
    # Happy path cases should still pass
    assert happy_path_inputs.isdisjoint(failing_inputs)
    # But invalid-input cases should fail since there's no validation
    assert "" in failing_inputs
    assert "30m1h" in failing_inputs
    assert not result.all_passed


def test_banned_construct_is_flagged_and_execution_skipped():
    result = run_harness(BANNED_CONSTRUCT_SOLUTION)
    assert result.function_found
    assert "eval(" in result.banned_hits
    assert result.ran_successfully is False  # execution is skipped when banned construct found
    assert not result.all_passed


def test_no_code_block_extracted():
    result = run_harness(NO_CODE_BLOCK)
    assert result.code_extracted is False
    assert result.all_passed is False
    assert result.run_error is not None


def test_infinite_loop_times_out_gracefully():
    infinite_loop_code = '''
```python
def parse_duration(s: str) -> int:
    """Never terminates."""
    while True:
        pass
```
'''
    result = run_harness(infinite_loop_code, timeout_s=2)
    assert result.function_found
    assert result.ran_successfully is False
    assert "timed out" in (result.run_error or "").lower()
    assert not result.all_passed
