import ast
import json
import operator
import os
from pathlib import Path
from typing import Any

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


OFFLINE_KB = {
    "faiss": {
        "summary": (
            "FAISS is a library for efficient similarity search and clustering "
            "of dense vectors. It is primarily a vector-search library rather "
            "than a full database service, so application developers commonly "
            "provide their own persistence, metadata/filtering, API layer, and "
            "operational controls."
        ),
        "keywords": ["faiss", "vector", "similarity", "metadata", "filtering"],
    },
    "qdrant": {
        "summary": (
            "Qdrant is a vector database/search engine designed around vectors "
            "and payload metadata. Its database-oriented API supports filtering "
            "alongside vector search and provides persistence and service "
            "features that reduce the amount of infrastructure an application "
            "must build around the vector index."
        ),
        "keywords": ["qdrant", "vector", "payload", "filter", "database"],
    },
    "pgvector": {
        "summary": (
            "pgvector adds vector similarity search to PostgreSQL. It can be "
            "attractive when an application already relies heavily on PostgreSQL "
            "because vectors and relational data can live in the same database, "
            "while PostgreSQL remains responsible for transactions, access "
            "control, backup, and its normal operational model."
        ),
        "keywords": ["pgvector", "postgres", "postgresql", "sql", "filter", "vector"],
    },
}


def web_search(query: str) -> dict[str, Any]:
    """Search public web information; uses Tavily when configured, otherwise an offline KB."""
    if os.getenv("FORCE_SEARCH_FAILURE") == "1":
        os.environ.pop("FORCE_SEARCH_FAILURE", None)
        return {"results": [], "error": None, "status": 200}

    api_key = os.getenv("TAVILY_API_KEY")
    if api_key and TavilyClient is not None:
        client = TavilyClient(api_key=api_key)
        result = client.search(query=query, search_depth="basic", max_results=4)
        return {"provider": "tavily", "results": result.get("results", [])}

    q = query.lower()
    matches = []
    for name, item in OFFLINE_KB.items():
        if any(k in q for k in item["keywords"]):
            matches.append({
                "title": f"Offline knowledge note: {name}",
                "content": item["summary"],
                "url": f"offline://{name}",
            })
    if not matches:
        matches = [{
            "title": "Offline search limitation",
            "content": (
                "No matching offline note was found. Configure TAVILY_API_KEY "
                "for live web research."
            ),
            "url": "offline://none",
        }]
    return {"provider": "offline", "results": matches}


_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError("Only arithmetic expressions are supported.")


def calculator(expression: str) -> dict[str, Any]:
    """Evaluate a simple arithmetic expression safely."""
    tree = ast.parse(expression, mode="eval")
    value = _safe_eval(tree.body)
    return {"expression": expression, "result": value}


def read_notes_file() -> dict[str, Any]:
    """Read the simulated internal team notes."""
    path = Path(__file__).resolve().parent.parent / "data" / "team_notes.md"
    return {"path": str(path), "content": path.read_text(encoding="utf-8")}


TOOLS = {
    "web_search": web_search,
    "calculator": calculator,
    "read_notes_file": read_notes_file,
}


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = TOOLS[name](**args)
        if name == "web_search" and not result.get("results"):
            result["_failure"] = True
            result["_failure_reason"] = "Search returned no usable results."
        return result
    except Exception as exc:
        return {
            "_failure": True,
            "_failure_reason": f"{type(exc).__name__}: {exc}",
        }
