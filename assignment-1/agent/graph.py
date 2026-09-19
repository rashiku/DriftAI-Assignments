from langgraph.graph import END, START, StateGraph

from .llm import plan
from .state import AgentState
from .tools import execute_tool


def _append_trace(state: AgentState, entry: dict) -> list[dict]:
    return state.get("trace", []) + [entry]


def reason_and_act(state: AgentState) -> AgentState:
    remaining = 6 - state.get("tool_calls", 0)
    if remaining <= 0:
        decision = {
            "action": "answer",
            "decision": "Stop because the six-call budget is exhausted.",
            "reason": "The agent must not exceed the configured tool-call limit.",
        }
        trace = _append_trace(state, {"step": len(state.get("trace", [])) + 1, **decision})
        answer = (
            "The six-tool-call limit was reached. I synthesized the best answer "
            "possible from the evidence collected before the limit."
        )
        return {**state, "pending_action": None, "final_answer": answer, "trace": trace}

    decision = plan(
        state["question"],
        state.get("messages", []),
        state.get("research", []),
        remaining,
    )
    trace = _append_trace(state, {
        "step": len(state.get("trace", [])) + 1,
        "type": "decision",
        "decision": decision.decision,
        "reason": decision.reason,
        "action": decision.action,
        "tool": decision.tool,
        "args": decision.args,
    })

    if decision.action == "answer":
        return {
            **state,
            "pending_action": None,
            "final_answer": decision.answer or "No final answer was produced.",
            "trace": trace,
        }

    return {
        **state,
        "pending_action": {
            "tool": decision.tool,
            "args": decision.args,
        },
        "trace": trace,
    }


def route_after_reason(state: AgentState):
    return "tool" if state.get("pending_action") else "end"


def run_tool(state: AgentState) -> AgentState:
    action = state["pending_action"]
    name = action["tool"]
    args = action.get("args", {})
    result = execute_tool(name, args)
    call_number = state.get("tool_calls", 0) + 1
    failure = bool(result.get("_failure"))

    observation = {
        "step": len(state.get("trace", [])) + 1,
        "type": "tool_result",
        "tool": name,
        "call_number": call_number,
        "result": result,
        "failure": failure,
        "failure_reason": result.get("_failure_reason"),
    }
    trace = _append_trace(state, observation)
    research = state.get("research", []) + [{
        "tool": name,
        "args": args,
        "result": result,
        "failure": failure,
    }]
    messages = state.get("messages", []) + [{
        "role": "tool",
        "tool": name,
        "content": result,
    }]
    return {
        **state,
        "messages": messages,
        "research": research,
        "trace": trace,
        "tool_calls": call_number,
        "remaining_calls": 6 - call_number,
        "pending_action": None,
    }


builder = StateGraph(AgentState)
builder.add_node("reason_and_act", reason_and_act)
builder.add_node("execute_tool", run_tool)
builder.add_edge(START, "reason_and_act")
builder.add_conditional_edges(
    "reason_and_act",
    route_after_reason,
    {"tool": "execute_tool", "end": END},
)
builder.add_edge("execute_tool", "reason_and_act")
graph = builder.compile()
