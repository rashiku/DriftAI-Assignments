"""
CLI entry point for the Groq-backed LangGraph workflow.

Usage:
    python main.py                  # normal run, competent Agent A prompt -> should be approved
    python main.py --weak           # deliberately weakened Agent A prompt -> should be rejected
    python main.py --weak --save transcripts/transcript_2_rejected.md
    python main.py --save transcripts/transcript_1_approved.md

The --weak flag swaps in a deliberately degraded task prompt for Agent A
(instructing it to skip edge cases and the docstring) so that Agent B's
rejection path can be demonstrated. Agent B's criteria remain unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Locates the project root directory (one level up from src/) 
project_root = Path(__file__).resolve().parent.parent
env_path = project_root / ".env"

# Load the .env file explicitly from the calculated path
load_dotenv(dotenv_path=env_path)

# Quick verification check
if not os.getenv("GROQ_API_KEY"):
    raise ValueError(f"GROQ_API_KEY could not be found at: {env_path}")

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from graph import build_graph
from task_spec import TASK_PROMPT

WEAK_TASK_PROMPT = """\
Write a Python function named parse_duration(s: str) -> int that converts a
duration string like "1h30m" into total seconds. Just handle the common
cases quickly, don't worry about validating input or edge cases, a
docstring isn't necessary, keep it short.

Wrap your final answer in a single ```python code block.
"""


def format_report(state: dict) -> str:
    verdict = state["review_verdict"]
    harness = state["harness_result"]
    usage_log = state["usage_log"]

    total_calls = len(usage_log)
    total_input_tokens = sum(u["input_tokens"] for u in usage_log)
    total_output_tokens = sum(u["output_tokens"] for u in usage_log)
    total_tokens = total_input_tokens + total_output_tokens

    lines = []
    lines.append("=" * 72)
    lines.append("FINAL REPORT")
    lines.append("=" * 72)
    lines.append(f"VERDICT: {verdict.verdict.upper()}")
    lines.append("")
    lines.append("Agent B criteria breakdown:")
    for c in verdict.criteria:
        mark = "✅" if c.passed else "❌"
        lines.append(f"  {mark} {c.name}")
        lines.append(f"     {c.detail}")
    lines.append("")
    lines.append(f"Summary: {verdict.summary}")
    lines.append("")
    lines.append("Test harness detail:")
    lines.append(harness.to_summary_text())
    lines.append("")
    lines.append("-" * 72)
    lines.append("USAGE")
    lines.append("-" * 72)
    for u in usage_log:
        lines.append(
            f"  {u['node']:20s} model={u['model']:30s} "
            f"input_tokens={u['input_tokens']:5d} output_tokens={u['output_tokens']:5d}"
        )
    lines.append(f"  TOTAL LLM calls: {total_calls}")
    lines.append(f"  TOTAL input tokens:  {total_input_tokens}")
    lines.append(f"  TOTAL output tokens: {total_output_tokens}")
    lines.append(f"  TOTAL tokens:        {total_tokens}")
    lines.append("=" * 72)
    return "\n".join(lines)


def format_transcript_md(state: dict, prompt_used: str, weak: bool) -> str:
    verdict = state["review_verdict"]
    harness = state["harness_result"]
    usage_log = state["usage_log"]
    total_calls = len(usage_log)
    total_tokens = sum(u["input_tokens"] + u["output_tokens"] for u in usage_log)

    md = []
    md.append(f"# Transcript — Agent A/B run ({'weak prompt, expect rejection' if weak else 'normal prompt, expect approval'})")
    md.append("")
    md.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    md.append("")
    md.append("## 1. Task prompt given to Agent A")
    md.append("```")
    md.append(prompt_used.strip())
    md.append("```")
    md.append("")
    md.append("## 2. Agent A's raw output")
    md.append("```")
    md.append(state["agent_a_raw_output"].strip())
    md.append("```")
    md.append("")
    md.append("## 3. Deterministic test harness results (input to Agent B)")
    md.append("```")
    md.append(harness.to_summary_text())
    md.append("```")
    md.append("")
    md.append("## 4. Agent B's structured verdict")
    md.append(f"**Verdict: `{verdict.verdict}`**")
    md.append("")
    md.append("| Criterion | Passed | Detail |")
    md.append("|---|---|---|")
    for c in verdict.criteria:
        detail_escaped = c.detail.replace("|", "\\|").replace("\n", " ")
        md.append(f"| {c.name} | {'✅ Yes' if c.passed else '❌ No'} | {detail_escaped} |")
    md.append("")
    md.append(f"**Summary:** {verdict.summary}")
    md.append("")
    md.append("## 5. Usage report")
    md.append("| Node | Model | Input tokens | Output tokens |")
    md.append("|---|---|---|---|")
    for u in usage_log:
        md.append(f"| {u['node']} | {u['model']} | {u['input_tokens']} | {u['output_tokens']} |")
    md.append("")
    md.append(f"- **Total LLM calls:** {total_calls}")
    md.append(f"- **Total tokens:** {total_tokens}")
    md.append("")
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Run the Agent A / Agent B review chain.")
    parser.add_argument("--weak", action="store_true", help="Use a deliberately weakened prompt for Agent A to force a rejection.")
    parser.add_argument("--save", type=str, default=None, help="Path to save the Markdown transcript.")
    args = parser.parse_args()

    prompt_used = WEAK_TASK_PROMPT if args.weak else TASK_PROMPT

    app = build_graph()
    final_state = app.invoke({"task_prompt": prompt_used, "usage_log": []})

    print(format_report(final_state))

    if args.save:
        out_path = Path(args.save)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        out_path.write_text(
            format_transcript_md(final_state, prompt_used, args.weak),
            encoding="utf-8"
        )
        print(f"\nTranscript saved to {out_path}")

    return final_state


if __name__ == "__main__":
    main()
