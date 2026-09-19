"""
Task specification for Assignment 2.

The task given to Agent A (worker) is fixed and concrete so that Agent B
(reviewer) can check the output against objective, checkable criteria
instead of subjective "looks fine" judgments.

Task given to Agent A:
    Write a Python function `parse_duration(s: str) -> int` that parses a
    human-readable duration string (e.g. "1h30m", "45m", "2h", "90s",
    "1h 5m 3s") and returns the total number of seconds as an integer.

    Rules:
      - Supported units: h (hours), m (minutes), s (seconds)
      - Units may appear in any subset, but if present must appear in the
        order h, then m, then s
      - Whitespace between components is optional
      - Invalid input (empty string, unknown unit, malformed number,
        negative numbers) must raise a `ValueError`
      - Must include a docstring
      - Must NOT use `eval` or `exec`

This module defines:
  - TASK_PROMPT: the instruction given to Agent A
  - TEST_CASES: (input, expected_output_or_exception) pairs used by the
    deterministic test harness that Agent B's review is partly grounded in
  - BANNED_SUBSTRINGS: constructs that automatically fail review
  - REQUIRED_FUNCTION_NAME: the function name the harness looks for
"""

REQUIRED_FUNCTION_NAME = "parse_duration"

TASK_PROMPT = """\
Write a single Python function with this exact signature:

    def parse_duration(s: str) -> int:

It parses a human-readable duration string and returns the total number of
seconds as an integer.

Rules:
- Supported unit suffixes: h (hours), m (minutes), s (seconds).
- A string may contain any subset of these units, but if more than one is
  present they must appear in the order h, then m, then s
  (e.g. "1h30m" is valid, "30m1h" is not).
- Whitespace between components is optional and should be tolerated
  (e.g. "1h 30m" and "1h30m" are both valid).
- If the string is empty, contains an unknown unit, has a malformed number,
  a negative number, or otherwise cannot be parsed, the function must raise
  a ValueError (not return None, not silently default to 0).
- Include a docstring describing behavior, parameters, return value, and
  the ValueError case.
- Do not use eval() or exec() anywhere in your solution.
- Return ONLY the function definition (plus any needed imports like `re`).
  Do not include example usage, tests, or explanation text outside the code.
- Wrap your final answer in a single ```python code block.
"""

# (input_string, expected_result)
# expected_result is either an int (expected return value) or the string
# "ValueError" (meaning the call must raise ValueError).
TEST_CASES: list[tuple[str, int | str]] = [
    ("1h", 3600),
    ("45m", 2700),
    ("90s", 90),
    ("1h30m", 5400),
    ("1h 5m 3s", 3903),
    ("2h0m0s", 7200),
    ("0s", 0),
    ("1h 30m", 5400),
    ("", "ValueError"),
    ("30m1h", "ValueError"),          # wrong order
    ("1x", "ValueError"),             # unknown unit
    ("h", "ValueError"),              # missing number
    ("-5m", "ValueError"),            # negative
    ("1h1h", "ValueError"),           # duplicate unit
    ("1.5h", "ValueError"),           # non-integer number (spec says integer components)
    ("abc", "ValueError"),            # garbage
]

BANNED_SUBSTRINGS = ["eval(", "exec("]
