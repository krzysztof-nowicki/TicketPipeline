from typing import Any
from scripts.back_works.data_manager import get_data_manager

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_customer",
            "description": "Look up a customer's account status, name, and subscription plan by customer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer identifier (e.g. C-100, C-200).",
                    }
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoices",
            "description": "Retrieve all invoices for a given customer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer identifier (e.g. C-100).",
                    }
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "Search the knowledge base articles by query terms to find answers to customer questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords or question to search within articles (e.g. password, invoices, outage).",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Executes the specified tool against the DataManager."""
    manager = get_data_manager()
    if name == "get_customer":
        customer_id = arguments.get("customer_id", "")
        customer = manager.get_customer(customer_id)
        return customer.model_dump() if customer else {"error": f"Customer '{customer_id}' not found"}

    elif name == "get_invoices":
        customer_id = arguments.get("customer_id", "")
        invoices = manager.get_invoices(customer_id)
        return [inv.model_dump() for inv in invoices]

    elif name == "search_kb":
        query = arguments.get("query", "")
        articles = manager.search_kb(query)
        return [art.model_dump() for art in articles]

    else:
        return {"error": f"Unknown tool: '{name}'"}
