import argparse
import os
from pathlib import Path

from agent.graph import graph


DEFAULT_QUESTION = (
    "For a production RAG application, how should we choose between FAISS, "
    "Qdrant, and pgvector based on scale, filtering, deployment complexity, and performance?"
)


def format_trace(trace):
    lines = []
    for item in trace:
        lines.append(f"\n[STEP {item['step']}]")
        if item["type"] == "decision":
            lines.append(f"Decision: {item['decision']}")
            lines.append(f"Why: {item['reason']}")
            if item.get("tool"):
                lines.append(f"Action: {item['tool']}({item.get('args', {})})")
        else:
            lines.append(f"Tool result: {item['tool']} (call {item['call_number']})")
            if item["failure"]:
                lines.append(f"⚠ FAILURE DETECTED: {item['failure_reason']}")
            lines.append(f"Result: {item['result']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--inject-failure", action="store_true")
    args = parser.parse_args()

    if args.inject_failure:
        os.environ["FORCE_SEARCH_FAILURE"] = "1"

    initial = {
        "question": args.question,
        "messages": [],
        "research": [],
        "trace": [],
        "tool_calls": 0,
        "remaining_calls": 6,
        "pending_action": None,
        "final_answer": "",
    }

    result = graph.invoke(initial)

    print("=" * 80)
    print("ASSIGNMENT 1 — TOOL-USING RESEARCH AGENT")
    print("=" * 80)
    print(f"\nQUESTION:\n{args.question}")
    print(f"\nTOOL CALLS USED: {result.get('tool_calls', 0)}/6")
    print("\nREASONING / DECISION TRACE")
    print(format_trace(result["trace"]))
    print("\n" + "=" * 80)
    print("FINAL ANSWER")
    print("=" * 80)
    print(result.get("final_answer", ""))


if __name__ == "__main__":
    main()
