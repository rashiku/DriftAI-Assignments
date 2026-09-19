"""
LangGraph two-node chain: Agent A (worker) -> Agent B (reviewer) -> END.

No revision loop by design (per assignment spec): B reviews once and the
chain ends with either an "approved" or "rejected" verdict. 
"""

from __future__ import annotations

import os
from typing import Literal, TypedDict

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from harness import HarnessResult, run_harness
from task_spec import REQUIRED_FUNCTION_NAME, TASK_PROMPT

WORKER_MODEL = os.getenv("GROQ_WORKER_MODEL", "openai/gpt-oss-120b")
REVIEWER_MODEL = os.getenv("GROQ_REVIEWER_MODEL", "openai/gpt-oss-120b")


# ---------------------------------------------------------------------------
# Agent B's structured verdict schema
# ---------------------------------------------------------------------------

class CriterionCheck(BaseModel):
    name: str = Field(description="Short name of the criterion, e.g. 'All test cases pass'")
    passed: bool
    detail: str = Field(description="Concrete, specific explanation referencing actual evidence (test output, code excerpt), not a vague statement")


class ReviewVerdict(BaseModel):
    verdict: Literal["approved", "rejected"]
    criteria: list[CriterionCheck]
    summary: str = Field(description="1-3 sentence overall summary of the decision")


# ---------------------------------------------------------------------------
# Shared graph state
# ---------------------------------------------------------------------------

class UsageRecord(TypedDict):
    node: str
    model: str
    input_tokens: int
    output_tokens: int


class GraphState(TypedDict, total=False):
    task_prompt: str
    agent_a_raw_output: str
    harness_result: HarnessResult
    review_verdict: ReviewVerdict
    usage_log: list[UsageRecord]


# ---------------------------------------------------------------------------
# Agent A: worker node
# ---------------------------------------------------------------------------

def agent_a_worker(state: GraphState) -> GraphState:
    llm = ChatGroq(model=WORKER_MODEL, max_tokens=1500, temperature=0)
    messages = [
        SystemMessage(content=(
            "You are a careful Python developer. Follow the specification "
            "exactly. Output only what is asked for."
        )),
        HumanMessage(content=state["task_prompt"]),
    ]
    response = llm.invoke(messages)

    usage = response.usage_metadata or {}
    usage_log = state.get("usage_log", [])
    usage_log.append({
        "node": "agent_a_worker",
        "model": WORKER_MODEL,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    })

    return {
        "agent_a_raw_output": response.content,
        "usage_log": usage_log,
    }


# ---------------------------------------------------------------------------
# Harness node (deterministic, no LLM call — grounds Agent B's review)
# ---------------------------------------------------------------------------

def run_test_harness(state: GraphState) -> GraphState:
    result = run_harness(state["agent_a_raw_output"])
    return {"harness_result": result}


# ---------------------------------------------------------------------------
# Agent B: reviewer node
# ---------------------------------------------------------------------------

REVIEWER_SYSTEM_PROMPT = f"""\
You are a strict but fair code reviewer. You review exactly ONE submission
from another agent against the following concrete, checkable criteria.
You do not revise the code and you do not give the worker a second attempt.
You must return a verdict of "approved" or "rejected".

Approval requires ALL of the following to be true:
1. Code extracted: a valid Python code block was present in the submission.
2. Function signature: a function named `{REQUIRED_FUNCTION_NAME}` exists.
3. No banned constructs: the code must not use eval() or exec().
4. Docstring present: the function has a docstring.
5. All test cases pass: the deterministic test harness (already run for you)
   reports passed_count == total_count, with total_count > 0.

You are given the actual harness output below — trust it as ground truth
for correctness. Do not re-derive correctness yourself from reading the
code; use the harness results. Your job is to translate that evidence into
a clear, itemized, explainable verdict, and to call out specifically which
test cases failed and why, if any did.

For each of the 5 criteria above, return a CriterionCheck with:
- passed: true/false
- detail: a specific, concrete explanation citing the actual evidence
  (e.g. name the failing test case, the expected vs actual value, or quote
  the missing element). Never write a vague statement like "looks fine" or
  "the code seems okay" — always reference specifics.

If ANY criterion fails, the overall verdict must be "rejected".
If ALL criteria pass, the overall verdict must be "approved".
"""


def agent_b_reviewer(state: GraphState) -> GraphState:
    harness_result: HarnessResult = state["harness_result"]

    llm = ChatGroq(model=REVIEWER_MODEL, max_tokens=1500, temperature=0)
    structured_llm = llm.with_structured_output(ReviewVerdict, include_raw=True)

    review_input = f"""\
ORIGINAL TASK GIVEN TO AGENT A:
{state['task_prompt']}

AGENT A'S SUBMITTED OUTPUT (raw):
{state['agent_a_raw_output']}

DETERMINISTIC TEST HARNESS RESULTS (ground truth for correctness):
{harness_result.to_summary_text()}

Now produce your structured review verdict per the 5 criteria.
"""

    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=review_input),
    ]
    result = structured_llm.invoke(messages)

    parsed: ReviewVerdict = result["parsed"]
    raw_msg = result["raw"]
    usage = getattr(raw_msg, "usage_metadata", None) or {}

    usage_log = state.get("usage_log", [])
    usage_log.append({
        "node": "agent_b_reviewer",
        "model": REVIEWER_MODEL,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    })

    return {
        "review_verdict": parsed,
        "usage_log": usage_log,
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("agent_a_worker", agent_a_worker)
    graph.add_node("run_test_harness", run_test_harness)
    graph.add_node("agent_b_reviewer", agent_b_reviewer)

    graph.set_entry_point("agent_a_worker")
    graph.add_edge("agent_a_worker", "run_test_harness")
    graph.add_edge("run_test_harness", "agent_b_reviewer")
    graph.add_edge("agent_b_reviewer", END)

    return graph.compile()
