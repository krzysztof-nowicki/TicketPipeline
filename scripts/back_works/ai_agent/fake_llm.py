from scripts.utils.data_classes import (
    Category,
    CloseAction,
    Decision,
    EscalateAction,
    Priority,
    RefundAction,
    ReplyAction,
    Ticket,
)
from scripts.logging import get_logger
from scripts.back_works.ai_agent.base import LLMService
from scripts.back_works.ai_agent.agent_tools import execute_tool

logger = get_logger(__name__)


class FakeLLMService(LLMService):
    """
    FakeLLM Service to perform basic decision-making.
    """

    async def decide(self, ticket: Ticket) -> Decision:
        logger.info(f"[FakeLLM] Generating decision for ticket {ticket.ticket_id}")
        content = f"{ticket.subject} {ticket.body}".lower()

        # 1. Billing / Refund requests (T-2, T-5 prompt injection)
        if "refund" in content or "charged twice" in content:
            invoices = execute_tool("get_invoices", {"customer_id": ticket.customer_id})
            if invoices and isinstance(invoices, list):
                inv = invoices[-1]
                return Decision(
                    category=Category.BILLING,
                    priority=Priority.HIGH if "urgent" in content else Priority.NORMAL,
                    action=RefundAction(
                        invoice_id=inv["invoice_id"],
                        amount_eur=float(inv["amount_eur"]),
                    ),
                )

        # 2. Suspended / Locked account (T-4)
        if "locked" in content or "suspended" in content:
            kb_res = execute_tool("search_kb", {"query": "suspended"})
            article_ids = [a["article_id"] for a in kb_res] if kb_res and isinstance(kb_res, list) else ["KB-4"]
            return Decision(
                category=Category.OTHER,
                priority=Priority.NORMAL,
                action=ReplyAction(
                    message="Your account is suspended due to an overdue invoice. Pay the invoice to unlock your account.",
                    article_ids=article_ids,
                ),
            )

        # 3. Password / Login issues (T-1)
        if "password" in content or "log in" in content or "login" in content:
            kb_res = execute_tool("search_kb", {"query": "password"})
            article_ids = [a["article_id"] for a in kb_res] if kb_res and isinstance(kb_res, list) else ["KB-1"]
            return Decision(
                category=Category.OTHER,
                priority=Priority.NORMAL,
                action=ReplyAction(
                    message="Please use the 'Forgot password' link on the sign-in page to reset your password.",
                    article_ids=article_ids,
                ),
            )

        # 4. Outage without enough DB info, or generic fallback (T-3, T-6)
        return Decision(
            category=Category.OTHER,
            priority=Priority.HIGH,
            action=EscalateAction(
                reason="Automatic resolution could not be determined. Escalated to support team."
            ),
        )
