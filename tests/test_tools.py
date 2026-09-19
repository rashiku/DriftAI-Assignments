import os

from agent.tools import calculator, execute_tool


def test_calculator():
    result = calculator("100 * 20 / 4")
    assert result["result"] == 500


def test_failure_injection():
    os.environ["FORCE_SEARCH_FAILURE"] = "1"
    result = execute_tool("web_search", {"query": "FAISS"})
    assert result["_failure"] is True
    assert result["results"] == []
