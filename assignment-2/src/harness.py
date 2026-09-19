"""
Deterministic test harness.

Extracts the Python code Agent A produced, runs it in a fresh subprocess
(so a crashing/hanging solution can't take down the review process), and
executes it against the fixed TEST_CASES from task_spec.py.

This harness output (pass/fail per case, tracebacks, banned-construct hits)
is handed to Agent B so its review is grounded in objective execution
results rather than the reviewer's own guess about whether the code works.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from task_spec import BANNED_SUBSTRINGS, REQUIRED_FUNCTION_NAME, TEST_CASES

CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

RUNNER_TEMPLATE = '''
import json
import sys

{code}

_cases = {cases!r}
_results = []
for _inp, _expected in _cases:
    try:
        _got = {fn_name}(_inp)
        if _expected == "ValueError":
            _results.append({{"input": _inp, "expected": _expected, "outcome": "returned", "value": _got, "pass": False}})
        else:
            _results.append({{"input": _inp, "expected": _expected, "outcome": "returned", "value": _got, "pass": _got == _expected}})
    except ValueError as e:
        if _expected == "ValueError":
            _results.append({{"input": _inp, "expected": _expected, "outcome": "ValueError", "message": str(e), "pass": True}})
        else:
            _results.append({{"input": _inp, "expected": _expected, "outcome": "ValueError", "message": str(e), "pass": False}})
    except Exception as e:
        _results.append({{"input": _inp, "expected": _expected, "outcome": type(e).__name__, "message": str(e), "pass": False}})

print(json.dumps(_results))
'''


@dataclass
class HarnessResult:
    extracted_code: str | None
    code_extracted: bool
    has_docstring: bool
    banned_hits: list[str] = field(default_factory=list)
    function_found: bool = False
    ran_successfully: bool = False
    test_results: list[dict] = field(default_factory=list)
    passed_count: int = 0
    total_count: int = 0
    run_error: str | None = None

    @property
    def all_passed(self) -> bool:
        return (
            self.code_extracted
            and self.function_found
            and not self.banned_hits
            and self.has_docstring
            and self.ran_successfully
            and self.total_count > 0
            and self.passed_count == self.total_count
        )

    def to_summary_text(self) -> str:
        lines = []
        lines.append(f"Code extracted: {self.code_extracted}")
        lines.append(f"Function `{REQUIRED_FUNCTION_NAME}` found: {self.function_found}")
        lines.append(f"Has docstring: {self.has_docstring}")
        lines.append(f"Banned constructs found: {self.banned_hits or 'none'}")
        lines.append(f"Ran without harness error: {self.ran_successfully}")
        if self.run_error:
            lines.append(f"Run error: {self.run_error}")
        lines.append(f"Test cases passed: {self.passed_count}/{self.total_count}")
        if self.test_results:
            lines.append("Per-case results:")
            for r in self.test_results:
                status = "PASS" if r.get("pass") else "FAIL"
                lines.append(
                    f"  [{status}] input={r['input']!r} expected={r['expected']!r} "
                    f"outcome={r.get('outcome')} value/message={r.get('value', r.get('message'))!r}"
                )
        return "\n".join(lines)


def extract_code(raw_text: str) -> str | None:
    match = CODE_BLOCK_RE.search(raw_text)
    if match:
        return match.group(1).strip()
    # Fallback: if no fenced block, but text looks like it contains a def, use as-is
    if f"def {REQUIRED_FUNCTION_NAME}" in raw_text:
        return raw_text.strip()
    return None


def run_harness(raw_agent_output: str, timeout_s: int = 10) -> HarnessResult:
    code = extract_code(raw_agent_output)
    result = HarnessResult(
        extracted_code=code,
        code_extracted=code is not None,
        has_docstring=False,
    )
    if code is None:
        result.run_error = "No Python code block could be extracted from Agent A's output."
        return result

    result.function_found = f"def {REQUIRED_FUNCTION_NAME}" in code
    result.has_docstring = bool(
        re.search(rf'def\s+{REQUIRED_FUNCTION_NAME}\s*\([^)]*\)\s*(->\s*[^:]+)?:\s*\n\s*(\'\'\'|""")', code)
    )
    result.banned_hits = [b for b in BANNED_SUBSTRINGS if b in code]

    if not result.function_found or result.banned_hits:
        result.run_error = "Skipped execution due to missing function or banned constructs."
        return result

    script = RUNNER_TEMPLATE.format(code=code, cases=TEST_CASES, fn_name=REQUIRED_FUNCTION_NAME)

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "runner.py"
        script_path.write_text(script, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            result.run_error = f"Execution timed out after {timeout_s}s (possible infinite loop)."
            return result

        if proc.returncode != 0:
            result.run_error = f"Subprocess exited with error:\n{proc.stderr.strip()[-2000:]}"
            return result

        try:
            test_results = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as e:
            result.run_error = f"Could not parse harness output: {e}\nstdout={proc.stdout!r}"
            return result

        result.test_results = test_results
        result.total_count = len(test_results)
        result.passed_count = sum(1 for r in test_results if r.get("pass"))
        result.ran_successfully = True

    return result
