from scripts.back_works.data_manager import  get_data_manager


def test_data_manager_loads_customers():
    dm = get_data_manager()
    customer = dm.get_customer("C-100")
    assert customer is not None
    assert customer.customer_id == "C-100"
    assert customer.name == "Northwind Bakery"
    assert customer.plan == "business"

    # Non-existent customer
    assert dm.get_customer("C-NONEXISTENT") is None


def test_data_manager_loads_invoices():
    dm = get_data_manager()
    invoices = dm.get_invoices("C-100")
    assert len(invoices) >= 2
    for inv in invoices:
        assert inv.customer_id == "C-100"
        assert inv.amount_eur > 0


def test_data_manager_search_kb():
    dm = get_data_manager()
    results = dm.search_kb("password")
    assert len(results) > 0
    assert any("password" in r.title.lower() or "password" in r.text.lower() for r in results)


def test_data_manager_example_tickets():
    dm = get_data_manager()
    tickets = dm.get_all_example_tickets()
    assert len(tickets) >= 7
    ticket_ids = {t.ticket_id for t in tickets}
    assert "T-1" in ticket_ids
    assert "T-2" in ticket_ids
