from typing import Optional
from scripts.utils.data_classes import (
    ActionType,
    Category,
    Customer,
    Decision,
    EscalateAction,
    Invoice,
    Priority,
    RefundAction,
    Ticket, ReplyAction,
)


def validate_and_sanitize_decision(
    decision: Decision,
    ticket: Ticket,
    customer: Optional[Customer],
    invoices: list[Invoice],
) -> Decision:
    """
    Validates the LLM's proposed decision against business rules.
    If any business rule is violated, the decision is sanitized to an escalation to a person.
    """
    # Rule 1: Customer existence
    if customer is None:
        return Decision(
            category=Category.ACCOUNT,
            priority=Priority.NORMAL,
            action=ReplyAction(
                message=f"Customer '{ticket.customer_id}' not found in customer database"
            ),
        )

    # Rule 2: Category and Priority check (Pydantic validates enums, but double check in pure domain)
    if decision.category not in Category:
        return Decision(
            category=Category.OTHER,
            priority=Priority.HIGH,
            action=EscalateAction(
                reason=f"Invalid category '{decision.category}' proposed by LLM"
            ),
        )

    if decision.priority not in Priority:
        return Decision(
            category=decision.category,
            priority=Priority.HIGH,
            action=EscalateAction(
                reason=f"Invalid priority '{decision.priority}' proposed by LLM"
            ),
        )

    # Rule 3: Action-specific validation
    if decision.action.type == ActionType.REFUND:
        refund_action: RefundAction = decision.action

        # Look up matching invoice
        matched_invoice = next(
            (inv for inv in invoices if inv.invoice_id == refund_action.invoice_id),
            None,
        )

        if not matched_invoice:
            return Decision(
                category=decision.category,
                priority=Priority.HIGH,
                action=EscalateAction(
                    reason=f"Invoice '{refund_action.invoice_id}' does not exist"
                ),
            )

        if matched_invoice.customer_id != ticket.customer_id:
            return Decision(
                category=decision.category,
                priority=Priority.HIGH,
                action=EscalateAction(
                    reason=(
                        f"Invoice '{refund_action.invoice_id}' belongs to "
                        f"customer '{matched_invoice.customer_id}', not '{ticket.customer_id}'"
                    )
                ),
            )

        if refund_action.amount_eur <= 0:
            return Decision(
                category=decision.category,
                priority=Priority.HIGH,
                action=EscalateAction(
                    reason=f"Refund amount {refund_action.amount_eur} EUR must be strictly greater than 0"
                ),
            )

        if refund_action.amount_eur > matched_invoice.amount_eur:
            return Decision(
                category=decision.category,
                priority=Priority.HIGH,
                action=EscalateAction(
                    reason=(
                        f"Refund amount {refund_action.amount_eur} EUR exceeds invoice "
                        f"total of {matched_invoice.amount_eur} EUR for {matched_invoice.invoice_id}"
                    )
                ),
            )

    return decision
