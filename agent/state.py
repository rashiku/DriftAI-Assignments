from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    messages: list[dict[str, Any]]
    research: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    tool_calls: int
    remaining_calls: int
    pending_action: dict[str, Any] | None
    final_answer: str
