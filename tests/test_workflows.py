import pytest
from temporalio import activity
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

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
    WorkflowStep,
)
from scripts.back_works.activity_tools import ActivityToolsTransientError
from scripts.temporal.activities import (
    DecideActivityResult,
    ExecuteActionInput,
)
from scripts.temporal.workflows import ApprovalSignal, TicketWorkflow


@pytest.fixture
def sample_customer_c100() -> Customer:
    return Customer(
        customer_id="C-100",
        name="Northwind Bakery",
        plan="business",
        status="active",
    )


@pytest.fixture
def sample_invoice_inv1002() -> Invoice:
    return Invoice(
        invoice_id="INV-1002",
        customer_id="C-100",
        month="2026-09",
        amount_eur=49.0,
        status="paid",
    )


@pytest.mark.asyncio
async def test_workflow_ticket_answered():
    """Case 1: Normal support ticket answered with a KB article."""
    ticket = Ticket(
        ticket_id="T-1",
        customer_id="C-200",
        subject="Can't log in",
        body="I forgot my password and can't get into my account.",
    )

    @activity.defn(name="decide_ticket_activity")
    async def mock_decide(t: Ticket) -> DecideActivityResult:
        return DecideActivityResult(
            decision=Decision(
                category=Category.ACCOUNT,
                priority=Priority.NORMAL,
                action=ReplyAction(
                    message="Use the 'Forgot password' link on the sign-in page.",
                    article_ids=["KB-1"],
                ),
            ),
            customer=Customer(
                customer_id="C-200",
                name="Contoso Labs",
                plan="free",
                status="active",
            ),
            invoices=[],
        )

    @activity.defn(name="execute_action_activity")
    async def mock_act(input_data: ExecuteActionInput) -> dict:
        return {
            "status": "success",
            "action": "reply",
            "ticket_id": input_data.ticket.ticket_id,
            "message": input_data.decision.action.message,
        }

    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[TicketWorkflow],
            activities=[mock_decide, mock_act],
        ):
            result = await env.client.execute_workflow(
                TicketWorkflow.run,
                ticket,
                id=f"test-workflow-{ticket.ticket_id}",
                task_queue="test-queue",
            )

            assert result["status"] == "success"
            assert result["action"] == "reply"

            handle = env.client.get_workflow_handle(f"test-workflow-{ticket.ticket_id}")
            status = await handle.query(TicketWorkflow.get_status)
            assert status.current_step == WorkflowStep.COMPLETED
            assert status.decision.action.type == ActionType.REPLY


@pytest.mark.asyncio
async def test_workflow_refund_approved(sample_customer_c100, sample_invoice_inv1002):
    """Case 2: Refund ticket that receives human approval."""
    ticket = Ticket(
        ticket_id="T-2",
        customer_id="C-100",
        subject="Charged twice",
        body="Please refund the duplicate invoice.",
    )

    @activity.defn(name="decide_ticket_activity")
    async def mock_decide(t: Ticket) -> DecideActivityResult:
        return DecideActivityResult(
            decision=Decision(
                category=Category.BILLING,
                priority=Priority.NORMAL,
                action=RefundAction(
                    invoice_id=sample_invoice_inv1002.invoice_id,
                    amount_eur=sample_invoice_inv1002.amount_eur,
                ),
            ),
            customer=sample_customer_c100,
            invoices=[sample_invoice_inv1002],
        )

    @activity.defn(name="execute_action_activity")
    async def mock_act(input_data: ExecuteActionInput) -> dict:
        return {
            "status": "success",
            "action": "refund",
            "ticket_id": input_data.ticket.ticket_id,
            "invoice_id": input_data.decision.action.invoice_id,
            "amount_eur": input_data.decision.action.amount_eur,
        }

    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[TicketWorkflow],
            activities=[mock_decide, mock_act],
        ):
            handle = await env.client.start_workflow(
                TicketWorkflow.run,
                ticket,
                id=f"test-workflow-{ticket.ticket_id}",
                task_queue="test-queue",
            )

            # Signal human approval
            await handle.signal(
                TicketWorkflow.submit_approval,
                ApprovalSignal(approved=True, reviewer="FinanceManager", note="Verified double charge"),
            )

            result = await handle.result()
            assert result["status"] == "success"
            assert result["action"] == "refund"
            assert result["amount_eur"] == 49.0

            status = await handle.query(TicketWorkflow.get_status)
            assert status.current_step == WorkflowStep.COMPLETED
            assert status.decision.action.type == ActionType.REFUND


@pytest.mark.asyncio
async def test_workflow_refund_timeout_escalated(sample_customer_c100, sample_invoice_inv1002):
    """Case 3: Refund ticket that waits > 24 hours without approval and is escalated."""
    ticket = Ticket(
        ticket_id="T-2-timeout",
        customer_id="C-100",
        subject="Charged twice",
        body="Refund extra",
    )

    @activity.defn(name="decide_ticket_activity")
    async def mock_decide(t: Ticket) -> DecideActivityResult:
        return DecideActivityResult(
            decision=Decision(
                category=Category.BILLING,
                priority=Priority.NORMAL,
                action=RefundAction(
                    invoice_id=sample_invoice_inv1002.invoice_id,
                    amount_eur=sample_invoice_inv1002.amount_eur,
                ),
            ),
            customer=sample_customer_c100,
            invoices=[sample_invoice_inv1002],
        )

    @activity.defn(name="execute_action_activity")
    async def mock_act(input_data: ExecuteActionInput) -> dict:
        return {
            "status": "success",
            "action": input_data.decision.action.type,
            "reason": getattr(input_data.decision.action, "reason", ""),
        }

    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[TicketWorkflow],
            activities=[mock_decide, mock_act],
        ):
            # In time-skipping test environment, waiting for 24h timer skips time automatically
            result = await env.client.execute_workflow(
                TicketWorkflow.run,
                ticket,
                id=f"test-workflow-{ticket.ticket_id}",
                task_queue="test-queue",
            )

            # Verification: should be escalated because approval was never sent
            assert result["status"] == "success"
            assert result["action"] == "escalate"
            assert "timed out after 24 hours" in result["reason"]

            handle = env.client.get_workflow_handle(f"test-workflow-{ticket.ticket_id}")
            status = await handle.query(TicketWorkflow.get_status)
            assert status.current_step == WorkflowStep.COMPLETED
            assert status.decision.action.type == ActionType.ESCALATE


@pytest.mark.asyncio
async def test_workflow_activity_retry_success():
    """Case 4: Activity that fails transiently and succeeds after a retry."""
    ticket = Ticket(
        ticket_id="T-retry",
        customer_id="C-200",
        subject="Quick question",
        body="Hello",
    )

    @activity.defn(name="decide_ticket_activity")
    async def mock_decide(t: Ticket) -> DecideActivityResult:
        return DecideActivityResult(
            decision=Decision(
                category=Category.OTHER,
                priority=Priority.NORMAL,
                action=ReplyAction(message="Hello there!", article_ids=[]),
            ),
            customer=Customer(
                customer_id="C-200",
                name="Contoso Labs",
                plan="free",
                status="active",
            ),
            invoices=[],
        )

    attempts = 0

    @activity.defn(name="execute_action_activity")
    async def failing_then_succeeding_act(input_data: ExecuteActionInput) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ActivityToolsTransientError("Simulated temporary network glitch (HTTP 503)")
        return {
            "status": "success",
            "action": "reply",
            "attempts": attempts,
        }

    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[TicketWorkflow],
            activities=[mock_decide, failing_then_succeeding_act],
        ):
            result = await env.client.execute_workflow(
                TicketWorkflow.run,
                ticket,
                id=f"test-workflow-{ticket.ticket_id}",
                task_queue="test-queue",
            )

            assert result["status"] == "success"
            assert result["attempts"] == 2
            assert attempts == 2
