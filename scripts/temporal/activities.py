from typing import Any, Optional
from pydantic import BaseModel, Field
from temporalio import activity

from scripts.utils.data_classes import (
    ActionType,
    Customer,
    Decision,
    EscalateAction,
    Invoice,
    RefundAction,
    ReplyAction,
    Ticket,
)
from scripts.logging import get_logger, ticket_id_ctx, workflow_id_ctx
from scripts.back_works.data_manager import get_data_manager
from scripts.back_works.activity_tools import get_activitytools_api
from scripts.back_works.ai_agent.factory import get_llm_service

logger = get_logger(__name__)


class DecideActivityResult(BaseModel):
    decision: Decision
    customer: Optional[Customer] = None
    invoices: list[Invoice] = Field(default_factory=list)


class ExecuteActionInput(BaseModel):
    ticket: Ticket
    decision: Decision


@activity.defn
async def decide_ticket_activity(ticket: Ticket) -> DecideActivityResult:
    info = activity.info()
    ticket_id_ctx.set(ticket.ticket_id)
    workflow_id_ctx.set(info.workflow_id)

    logger.info(
        f"Activity decide_ticket_activity started (attempt {info.attempt}) for ticket {ticket.ticket_id}",
        extra={"ticket_id": ticket.ticket_id, "workflow_id": info.workflow_id},
    )


    data_store = get_data_manager()

    llm_service = get_llm_service() # Fake LLM inside
    decision = await llm_service.decide(ticket)

    # Fetch reference records for code-level rule checking
    customer = data_store.get_customer(ticket.customer_id)
    invoices = data_store.get_invoices(ticket.customer_id)

    logger.info(
        f"Activity decide_ticket_activity completed with proposed action '{decision.action.type}'",
        extra={"ticket_id": ticket.ticket_id, "workflow_id": info.workflow_id},
    )

    return DecideActivityResult(
        decision=decision,
        customer=customer,
        invoices=invoices,
    )


@activity.defn
async def execute_action_activity(input_data: ExecuteActionInput) -> dict[str, Any]:
    """
    Step 4: Activity that performs the resolved action via the ActivityTools API.
    Enforces idempotency and retries on transient errors.
    """
    info = activity.info()
    ticket = input_data.ticket
    decision = input_data.decision
    ticket_id_ctx.set(ticket.ticket_id)
    workflow_id_ctx.set(info.workflow_id)

    activity_tools = get_activitytools_api()
    idempotency_key = f"{ticket.ticket_id}:{decision.action.type}"

    logger.info(
        f"Activity execute_action_activity started (attempt {info.attempt}) for {decision.action.type}",
        extra={"ticket_id": ticket.ticket_id, "workflow_id": info.workflow_id},
    )

    action = decision.action
    if action.type == ActionType.REPLY:
        reply_action: ReplyAction = action
        result = activity_tools.send_reply(
            ticket_id=ticket.ticket_id,
            message=reply_action.message,
            article_ids=reply_action.article_ids,
            idempotency_key=idempotency_key,
        )
    elif action.type == ActionType.REFUND:
        refund_action: RefundAction = action
        result = activity_tools.issue_refund(
            ticket_id=ticket.ticket_id,
            invoice_id=refund_action.invoice_id,
            amount_eur=refund_action.amount_eur,
            idempotency_key=idempotency_key,
        )
    elif action.type == ActionType.ESCALATE:
        escalate_action: EscalateAction = action
        result = activity_tools.escalate(
            ticket_id=ticket.ticket_id,
            reason=escalate_action.reason,
            idempotency_key=idempotency_key,
        )
    elif action.type == ActionType.CLOSE:
        close_action = action
        result = activity_tools.close(
            ticket_id=ticket.ticket_id,
            reason=close_action.reason,
            idempotency_key=idempotency_key,
        )
    else:
        raise ValueError(f"Unknown action type: {action.type}")

    logger.info(
        f"Activity execute_action_activity successfully executed {action.type}",
        extra={"ticket_id": ticket.ticket_id, "workflow_id": info.workflow_id},
    )
    return result
