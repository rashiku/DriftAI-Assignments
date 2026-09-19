# Assignment 2 — Multi-Agent Task with Review

A two-agent LangGraph chain: **Agent A (worker)** produces one attempt, a
deterministic harness checks the attempt, and **Agent B (reviewer)** reviews
that single attempt against concrete criteria. There is **no revision loop**.

## Task

Agent A writes this Python function:

```python
def parse_duration(s: str) -> int:
```

The function converts strings such as `"1h30m"`, `"45m"`, and
`"1h 5m 3s"` into total seconds.

The specification requires:

- Supported units: `h`, `m`, `s`.
- If multiple units are present, they must occur in `h -> m -> s` order.
- Whitespace between components is allowed.
- Empty, malformed, negative, unknown-unit, duplicated, or out-of-order input
  must raise `ValueError`.
- The function must contain a docstring.
- `eval()` and `exec()` are prohibited.
- Agent A returns the function in a Python fenced code block.

The complete task specification and 16 deterministic test cases are in
`src/task_spec.py`.

## Agent B approval criteria

Agent B approves only when **all five** criteria pass:

1. **Code extracted** — a Python code block was successfully extracted.
2. **Function present** — `parse_duration` exists.
3. **No banned constructs** — neither `eval(` nor `exec(` appears in the submitted code.
4. **Docstring present** — the function has a docstring.
5. **All tests pass** — the deterministic harness reports 16/16 passing tests.

The reviewer must explain every criterion with concrete evidence. For a
rejection, it names the failing criterion(s) and specific failing test cases
with expected versus observed behavior.

## Architecture

```text
Agent A (Groq LLM)
        |
        v
Deterministic test harness
        |
        v
Agent B (Groq LLM)
        |
        v
       END
```

The graph is a linear `StateGraph`:

```text
agent_a_worker -> run_test_harness -> agent_b_reviewer -> END
```

There is deliberately no edge back to Agent A.

## Groq configuration

This implementation uses LangChain's `ChatGroq` integration and the
environment variable `GROQ_API_KEY`. The default model is
`openai/gpt-oss-120b`. You can override the worker and reviewer models with:

- `GROQ_WORKER_MODEL`
- `GROQ_REVIEWER_MODEL`

Do **not** commit your API key to GitHub.

## Setup

Python 3.10+ is required.

### macOS / Linux

```bash
cd assignment-2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export GROQ_API_KEY="gsk_..."
```

### Windows PowerShell

```powershell
cd assignment-2
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:GROQ_API_KEY="gsk_..."
```

Optional model override:

```bash
export GROQ_WORKER_MODEL="openai/gpt-oss-120b"
export GROQ_REVIEWER_MODEL="openai/gpt-oss-120b"
```

## How to run

From the `assignment-2` directory:

### Approved run

```bash
python src/main.py --save transcripts/transcript_1_approved.md
```

This gives Agent A the complete specification. A compliant output should
normally be approved after the harness verifies it.

### Rejected run

```bash
python src/main.py --weak --save transcripts/transcript_2_rejected.md
```

`--weak` deliberately gives Agent A a weaker brief that tells it not to
implement validation or a docstring. Agent B's criteria do **not** change.
This demonstrates a genuine rejection without weakening the reviewer.

### Run the non-LLM tests

```bash
python -m pytest tests/ -v
```

These tests exercise the deterministic harness and do not require a Groq key.

## LLM calls and token reporting

Each complete run makes exactly **2 LLM calls**:

1. Agent A — one Groq call.
2. Agent B — one Groq call.

The harness is pure Python and makes no LLM call.

The program reads provider-reported `usage_metadata` from each LangChain
response and reports input, output, and total token counts. If a provider or
model does not expose a particular usage field, that field may appear as zero.

## Transcripts

The required transcripts should be generated with the actual Groq runs:

```bash
python src/main.py --save transcripts/transcript_1_approved.md
python src/main.py --weak --save transcripts/transcript_2_rejected.md
```

**Important:** the transcripts that came with the original uploaded archive
were generated for Anthropic/Claude and were not retained as submission
evidence here, because they would not truthfully document Groq runs.

After running the two commands above, commit the resulting Markdown files to
GitHub. Each transcript contains:

- Agent A's prompt
- Agent A's raw output
- deterministic harness results
- Agent B's structured verdict and reasons
- per-agent token usage
- total LLM calls
- total tokens

## Assumptions

1. A small code-generation task was chosen because correctness can be checked
   with deterministic execution rather than subjective judgment.
2. "Review once" is implemented as one Agent B node with no revision edge.
3. The rejection run uses a weaker Agent A prompt while keeping Agent B's
   criteria unchanged.
4. Token counts are reported from LangChain response metadata rather than
   estimated manually.
5. The default Groq model is `openai/gpt-oss-120b`; it can be changed through
   environment variables without modifying the graph.
6. The generated function is executed in a separate subprocess with a
   timeout. This is a lightweight test harness, not a security sandbox for
   arbitrary hostile code.

## Files

```text
assignment-2/
├── README.md
├── requirements.txt
├── src/
│   ├── task_spec.py
│   ├── harness.py
│   ├── graph.py
│   └── main.py
├── tests/
│   └── test_harness.py
└── transcripts/
    ├── transcript_1_approved.md
    └── transcript_2_rejected.md
```
