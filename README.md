# Assignment 1: Tool-Using Research Agent

A LangGraph research agent that answers an open-ended infrastructure question by choosing its own research actions at runtime.

## Question

> For a production RAG application, how should we choose between FAISS, Qdrant, and pgvector based on scale, filtering, deployment complexity, and performance?

The question requires combining public technical information with fictional internal team constraints in `data/team_notes.md`.

## Requirements covered

- **LangGraph:** the agent uses a two-node reasoning/tool loop.
- **Autonomous planning:** the planner chooses the next action from the current evidence; there is no `step 1 → step 2 → step 3` pipeline.
- **At least 2 distinct tools:** `web_search`, `calculator`, and `read_notes_file`.
- **Dynamic stopping:** the planner can return `answer` whenever it considers the evidence sufficient.
- **Maximum 6 tool calls:** tracked in graph state; the graph forces a best-effort answer at the limit.
- **Decision trace:** each decision records what was chosen, why, and the resulting tool observation. The trace contains concise decision summaries, not hidden chain-of-thought.
- **Failure handling:** `--inject-failure` makes the next web search return an empty HTTP-200-like payload. The agent marks it as a failure and adapts.
- **Transcripts:** both requested runs are included under `transcripts/`.

## Tools

| Tool | Purpose |
|---|---|
| `web_search(query)` | Tavily live search when `TAVILY_API_KEY` is configured; otherwise a small offline knowledge base |
| `calculator(expression)` | Safe arithmetic only |
| `read_notes_file()` | Reads the internal team constraints |

## Setup

```bash
cd assignment-1
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Recommended:** use Groq for the real LLM planner. The repository also contains a local fallback planner so it can run without an LLM key.

For the real LLM planning path, configure Groq:

```bash
export GROQ_API_KEY="..."
export LLM_PROVIDER="groq"
```

The default Groq model is `llama-3.3-70b-versatile`. You can change it with `GROQ_MODEL`.

OpenAI and Anthropic are also supported as alternatives.

For live Tavily search:

```bash
export TAVILY_API_KEY="..."
```

These can be mixed independently.

## Run

Clean run:

```bash
python main.py
```

Failure-injection run:

```bash
python main.py --inject-failure
```

Custom question:

```bash
python main.py --question "Your open-ended research question"
```

Run tests:

```bash
pytest -q
```

## Assumptions

1. **Plans its own steps:** interpreted as runtime re-planning from accumulated observations rather than requiring a complete multi-step plan to be generated upfront.
2. **No API key:** the repository must still run from a clean clone, so an offline adaptive fallback is included. For grading the strongest agent behavior, use a real LLM API key.
3. **Mocked failure:** implemented as an empty/malformed search payload rather than a Python exception, so the agent must detect unusable evidence.
4. **Calculator:** restricted to arithmetic rather than arbitrary code execution.

## Repository contents

```text
assignment-1/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── main.py
├── agent/
│   ├── graph.py
│   ├── llm.py
│   ├── state.py
│   └── tools.py
├── data/
│   └── team_notes.md
├── transcripts/
│   ├── transcript_1_clean_run.txt
│   └── transcript_2_failure_run.txt
└── tests/
    └── test_tools.py
```
