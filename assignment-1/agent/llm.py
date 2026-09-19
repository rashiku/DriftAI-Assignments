import json
import os
from typing import Any

from pydantic import BaseModel, Field


class Decision(BaseModel):
    action: str = Field(description="Either call_tool or answer.")
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    decision: str = Field(description="Short description of what the agent decided to do.")
    reason: str = Field(description="Concise rationale; summarize the decision, do not expose hidden chain-of-thought.")
    answer: str | None = None


SYSTEM_PROMPT = """You are an autonomous research agent.
You must decide one action at a time from the evidence already collected.

Available tools:
- web_search(query): public web research
- calculator(expression): arithmetic only
- read_notes_file(): internal team constraints

Rules:
- Do not follow a pre-ordered research script. Choose the next useful action based on the actual evidence.
- You may call tools in any order and may skip tools that are not useful.
- Stop with action=answer as soon as the evidence is sufficient.
- Never treat a failed/empty tool result as evidence.
- If a tool fails, adapt by choosing a different useful tool/query.
- The overall graph enforces a maximum of 6 tool calls.
- The final answer must distinguish sourced facts from assumptions and explain the recommendation for the stated use case.
- Keep decision/reason fields concise summaries of your rationale, not private chain-of-thought.
"""


def _real_llm():
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider == "groq" or (not provider and os.getenv("GROQ_API_KEY")):
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0,
        )
    if provider == "anthropic" or (not provider and os.getenv("ANTHROPIC_API_KEY")):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"), temperature=0)
    if provider == "openai" or (not provider and os.getenv("OPENAI_API_KEY")):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    return None


def _local_planner(question: str, history: list[dict[str, Any]], research: list[dict[str, Any]], remaining: int) -> Decision:
    """Offline fallback: adaptive branching based on actual observations, not fixed step numbers."""
    used = {r.get("tool") for r in research}
    failures = [r for r in research if r.get("failure")]
    combined = json.dumps(research).lower()

    if failures and "read_notes_file" not in used and remaining > 0:
        return Decision(
            action="call_tool", tool="read_notes_file", args={},
            decision="Recover from the failed search by consulting the internal constraints source.",
            reason="The previous search returned no usable evidence, so I need an independent source before deciding."
        )

    if "read_notes_file" not in used and remaining > 0:
        return Decision(
            action="call_tool", tool="read_notes_file", args={},
            decision="Check the internal team constraints.",
            reason="The question asks for a production choice, and deployment context can change the trade-off."
        )

    if "web_search" not in used and remaining > 0:
        query = "FAISS Qdrant pgvector production vector database filtering deployment performance"
        return Decision(
            action="call_tool", tool="web_search", args={"query": query},
            decision="Gather public technical evidence about the candidate technologies.",
            reason="The internal constraints alone do not establish the capabilities and trade-offs of each option."
        )

    if "calculator" not in used and remaining > 0:
        expression = "1000000 * 1536 * 4 / 1024 / 1024 / 1024"
        return Decision(
            action="call_tool", tool="calculator", args={"expression": expression},
            decision="Estimate the raw memory footprint of one million 1536-dimensional float32 vectors.",
            reason="A rough scale calculation helps connect the production corpus size to infrastructure considerations."
        )

    if remaining > 0 and "performance" not in combined:
        return Decision(
            action="call_tool", tool="web_search",
            args={"query": "FAISS Qdrant pgvector performance filtering production tradeoffs"},
            decision="Fill the remaining evidence gap around performance and filtering.",
            reason="The current evidence is missing a direct comparison of two decision criteria from the question."
        )

    answer = (
        "Based on the collected evidence, the choice should be driven by the team's existing "
        "infrastructure and filtering needs rather than by a universal performance winner. "
        "FAISS is a library and leaves more service/metadata/operations work to the application; "
        "Qdrant provides a purpose-built vector database with metadata filtering; pgvector keeps "
        "vectors inside PostgreSQL and can be attractive when relational data and SQL filtering "
        "are already central. The internal notes should be used to map those characteristics "
        "to the team's actual constraints."
    )
    return Decision(
        action="answer",
        decision="Synthesize the evidence gathered so far.",
        reason="The available sources cover the candidate technologies, internal constraints, and a scale calculation.",
        answer=answer
    )


def plan(question: str, history: list[dict[str, Any]], research: list[dict[str, Any]], remaining: int) -> Decision:
    llm = _real_llm()
    if llm is None:
        return _local_planner(question, history, research, remaining)

    context = {
        "question": question,
        "remaining_tool_calls": remaining,
        "research": research,
        "history": history[-12:],
    }
    prompt = SYSTEM_PROMPT + "\nCURRENT STATE:\n" + json.dumps(context, indent=2, default=str)
    structured = llm.with_structured_output(Decision)
    return structured.invoke(prompt)
