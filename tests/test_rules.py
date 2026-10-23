import pytest
from scripts.utils.data_classes import (
    ActionType,
    Category,
    Customer,
    Decision,
    Invoice,
    Priority,
    RefundAction,
    ReplyAction,
    Ticket,
)
from scripts.utils.rules import validate_and_sanitize_decision


@pytest.fixture
def sample_customer() -> Customer:
    return Customer(
        customer_id="C-100",
        name="Northwind Bakery",
        plan="business",
        status="active",
    )


@pytest.fixture
def sample_invoices() -> list[Invoice]:
    return [
        Invoice(
            invoice_id="INV-1001",
            customer_id="C-100",
            month="2026-09",
            amount_eur=49.0,
            status="paid",
        ),
        Invoice(
            invoice_id="INV-1002",
            customer_id="C-100",
            month="2026-09",
            amount_eur=49.0,
            status="paid",
        ),
    ]


@pytest.fixture
def sample_ticket() -> Ticket:
    return Ticket(
        ticket_id="T-100",
        customer_id="C-100",
        subject="Billing inquiry",
        body="Please check my invoice",
    )


def test_valid_reply_decision_passes(sample_customer, sample_invoices, sample_ticket):
    decision = Decision(
        category=Category.ACCOUNT,
        priority=Priority.NORMAL,
        action=ReplyAction(message="Here is your answer", article_ids=["KB-1"]),
    )
    result = validate_and_sanitize_decision(decision, sample_ticket, sample_customer, sample_invoices)
    assert result.action.type == ActionType.REPLY
    assert result.action.message == "Here is your answer"


def test_unknown_customer_escalates(sample_invoices, sample_ticket):
    decision = Decision(
        category=Category.ACCOUNT,
        priority=Priority.NORMAL,
        action=ReplyAction(message="Hello", article_ids=[]),
    )
    result = validate_and_sanitize_decision(decision, sample_ticket, None, sample_invoices)
    assert result.action.type == ActionType.REPLY
    assert "not found in customer database" in result.action.message


def test_valid_refund_decision_passes(sample_customer, sample_invoices, sample_ticket):
    decision = Decision(
        category=Category.BILLING,
        priority=Priority.NORMAL,
        action=RefundAction(invoice_id="INV-1001", amount_eur=49.0),
    )
    result = validate_and_sanitize_decision(decision, sample_ticket, sample_customer, sample_invoices)
    assert result.action.type == ActionType.REFUND
    assert result.action.invoice_id == "INV-1001"
    assert result.action.amount_eur == 49.0


def test_refund_with_nonexistent_invoice_escalates(sample_customer, sample_invoices, sample_ticket):
    decision = Decision(
        category=Category.BILLING,
        priority=Priority.NORMAL,
        action=RefundAction(invoice_id="INV-9999", amount_eur=49.0),
    )
    result = validate_and_sanitize_decision(decision, sample_ticket, sample_customer, sample_invoices)
    assert result.action.type == ActionType.ESCALATE
    assert "does not exist" in result.action.reason


def test_refund_for_another_customer_invoice_escalates(sample_customer, sample_ticket):
    other_customer_invoices = [
        Invoice(
            invoice_id="INV-3001",
            customer_id="C-300",
            month="2026-09",
            amount_eur=990.0,
            status="paid",
        )
    ]
    decision = Decision(
        category=Category.BILLING,
        priority=Priority.NORMAL,
        action=RefundAction(invoice_id="INV-3001", amount_eur=100.0),
    )
    result = validate_and_sanitize_decision(decision, sample_ticket, sample_customer, other_customer_invoices)
    assert result.action.type == ActionType.ESCALATE
    assert "belongs to customer 'C-300', not 'C-100'" in result.action.reason


def test_prompt_injection_excessive_refund_escalates(sample_customer, sample_invoices, sample_ticket):
    # Prompt injection attempts to issue a 5000 EUR refund against a 49 EUR invoice
    decision = Decision(
        category=Category.BILLING,
        priority=Priority.HIGH,
        action=RefundAction(invoice_id="INV-1001", amount_eur=5000.0),
    )
    result = validate_and_sanitize_decision(decision, sample_ticket, sample_customer, sample_invoices)
    assert result.action.type == ActionType.ESCALATE
    assert "exceeds invoice total of 49.0 EUR" in result.action.reason


def test_zero_or_negative_refund_escalates(sample_customer, sample_invoices, sample_ticket):
    decision = Decision(
        category=Category.BILLING,
        priority=Priority.NORMAL,
        action=RefundAction(invoice_id="INV-1001", amount_eur=-10.0),
    )
    result = validate_and_sanitize_decision(decision, sample_ticket, sample_customer, sample_invoices)
    assert result.action.type == ActionType.ESCALATE
    assert "must be strictly greater than 0" in result.action.reason
