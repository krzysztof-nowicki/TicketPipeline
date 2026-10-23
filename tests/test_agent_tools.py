from scripts.back_works.ai_agent.agent_tools import execute_tool


def test_tool_get_customer():
    res = execute_tool("get_customer", {"customer_id": "C-100"})
    assert isinstance(res, dict)
    assert res.get("customer_id") == "C-100"
    assert res.get("name") == "Northwind Bakery"

    # Missing customer
    err = execute_tool("get_customer", {"customer_id": "C-UNKNOWN"})
    assert "error" in err


def test_tool_get_invoices():
    res = execute_tool("get_invoices", {"customer_id": "C-100"})
    assert isinstance(res, list)
    assert len(res) >= 2
    assert all(inv["customer_id"] == "C-100" for inv in res)


def test_tool_search_kb():
    res = execute_tool("search_kb", {"query": "password"})
    assert isinstance(res, list)
    assert len(res) > 0
    assert any("KB-1" == art.get("article_id") for art in res)


def test_unknown_tool():
    res = execute_tool("nonexistent_tool", {})
    assert "error" in res
