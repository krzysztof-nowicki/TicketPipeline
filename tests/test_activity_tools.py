from scripts.back_works.activity_tools import FakeActivityToolsAPI


def test_activity_tools_send_reply():
    api = FakeActivityToolsAPI(failure_rate=0.0)
    res = api.send_reply(
        ticket_id="T-1",
        message="Please reset password",
        article_ids=["KB-1"],
        idempotency_key="key-reply-1",
    )
    assert res["status"] == "success"
    assert res["action"] == "reply"
    assert res["ticket_id"] == "T-1"

    # Idempotent replay returns same result
    replay = api.send_reply(
        ticket_id="T-1",
        message="Different message",
        article_ids=[],
        idempotency_key="key-reply-1",
    )
    assert replay["message"] == "Please reset password"


def test_activity_tools_issue_refund():
    api = FakeActivityToolsAPI(failure_rate=0.0)
    res = api.issue_refund(
        ticket_id="T-2",
        invoice_id="INV-1001",
        amount_eur=49.0,
        idempotency_key="key-refund-1",
    )
    assert res["status"] == "success"
    assert res["action"] == "refund"
    assert res["amount_eur"] == 49.0

    # Idempotency prevents duplicate refund
    replay = api.issue_refund(
        ticket_id="T-2",
        invoice_id="INV-1001",
        amount_eur=999.0,
        idempotency_key="key-refund-1",
    )
    assert replay["amount_eur"] == 49.0


def test_activity_tools_escalate():
    api = FakeActivityToolsAPI(failure_rate=0.0)
    res = api.escalate(
        ticket_id="T-3",
        reason="Requires manual intervention",
        idempotency_key="key-esc-1",
    )
    assert res["status"] == "success"
    assert res["action"] == "escalate"


def test_activity_tools_close():
    api = FakeActivityToolsAPI(failure_rate=0.0)
    res = api.close(
        ticket_id="T-5",
        reason="Out of scope",
        idempotency_key="key-close-1",
    )
    assert res["status"] == "success"
    assert res["action"] == "close"
