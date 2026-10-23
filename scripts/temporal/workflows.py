import asyncio
from datetime import timedelta
from typing import Optional
from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from scripts.utils.data_classes import (
        ActionType,
        Decision,
        EscalateAction,
        Ticket,
        WorkflowStep,
        WorkflowStatus,
    )
    from scripts.utils.rules import validate_and_sanitize_decision
    from scripts.temporal.activities import (
        DecideActivityResult,
        ExecuteActionInput,
        decide_ticket_activity,
        execute_action_activity,
)


class ApprovalSignal(BaseModel):
    approved: bool
    reviewer: Optional[str] = None
    note: Optional[str] = None


@workflow.defn
class TicketWorkflow:
    def __init__(self) -> None:
        self.ticket_id: str = ""
        self.current_step: WorkflowStep = WorkflowStep.PENDING
        self.decision: Optional[Decision] = None
        self.result: Optional[dict] = None
        self.error: Optional[str] = None

        # Approval state
        self._approval_received: bool = False
        self._approval_data: Optional[ApprovalSignal] = None

    @workflow.query
    def get_status(self) -> WorkflowStatus:
        """Returns the current step, decision, and result of the ticket."""
        return WorkflowStatus(
            ticket_id=self.ticket_id,
            workflow_id=workflow.info().workflow_id,
            current_step=self.current_step,
            decision=self.decision,
            result=self.result,
            error=self.error,
        )

    @workflow.signal
    def submit_approval(self, signal: ApprovalSignal) -> None:
        """Receives human approval or rejection for waiting refund actions."""
        self._approval_data = signal
        self._approval_received = True
        workflow.logger.info(
            f"Approval signal received for ticket {self.ticket_id}: approved={signal.approved}"
        )

    @workflow.run
    async def run(self, ticket: Ticket) -> dict:
        self.ticket_id = ticket.ticket_id
        wf_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting TicketWorkflow for ticket {self.ticket_id} (workflow_id={wf_id})"
        )

        try:
            # Step 1: Decide
            self.current_step = WorkflowStep.DECIDING
            workflow.logger.info(f"Step 1: Invoking decide_ticket_activity for {self.ticket_id}")

            decide_result: DecideActivityResult = await workflow.execute_activity(
                decide_ticket_activity,
                ticket,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    maximum_attempts=3,
                    non_retryable_error_types=["ValueError", "TypeError"],
                ),
            )
            self.decision = decide_result.decision

            # Step 2: Check decision in code
            self.current_step = WorkflowStep.CHECKING_DECISION
            workflow.logger.info(f"Step 2: Checking decision in code for {self.ticket_id}")

            validated_decision = validate_and_sanitize_decision(
                decision=self.decision,
                ticket=ticket,
                customer=decide_result.customer,
                invoices=decide_result.invoices,
            )
            self.decision = validated_decision

            # Step 3: Wait for approval (for refunds only)
            if self.decision.action.type == ActionType.REFUND:
                self.current_step = WorkflowStep.WAITING_FOR_APPROVAL
                workflow.logger.info(
                    f"Step 3: Waiting up to 24h for human approval of refund for {self.ticket_id}"
                )

                try:
                    await workflow.wait_condition(
                        lambda: self._approval_received,
                        timeout=timedelta(hours=24),
                    )

                    if self._approval_data and not self._approval_data.approved:
                        workflow.logger.info(f"Refund was rejected for ticket {self.ticket_id}")
                        self.decision.action = EscalateAction(
                            reason=f"Refund rejected by reviewer: {self._approval_data.note or 'No reason provided'}"
                        )
                    else:
                        workflow.logger.info(f"Refund was approved for ticket {self.ticket_id}")

                except asyncio.TimeoutError:
                    workflow.logger.warning(
                        f"Refund approval timed out after 24 hours for {self.ticket_id}. Escalating to human."
                    )
                    self.decision.action = EscalateAction(
                        reason="Refund approval timed out after 24 hours without human response."
                    )

            # Step 4: Act
            self.current_step = WorkflowStep.ACTING
            workflow.logger.info(
                f"Step 4: Executing helpdesk action '{self.decision.action.type}' for {self.ticket_id}"
            )

            action_result = await workflow.execute_activity(
                execute_action_activity,
                ExecuteActionInput(ticket=ticket, decision=self.decision),
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=5,
                ),
            )

            self.result = action_result
            self.current_step = WorkflowStep.COMPLETED
            workflow.logger.info(f"Workflow successfully completed for ticket {self.ticket_id}")
            return self.result

        except ActivityError as err:
            self.current_step = WorkflowStep.FAILED
            self.error = f"Workflow failed during activity execution: {str(err)}"
            workflow.logger.error(
                f"Workflow failed for ticket {self.ticket_id}: {self.error}"
            )
            raise
        except Exception as err:
            self.current_step = WorkflowStep.FAILED
            self.error = f"Workflow encountered an unexpected error: {str(err)}"
            workflow.logger.error(
                f"Unexpected failure for ticket {self.ticket_id}: {self.error}"
            )
            raise
