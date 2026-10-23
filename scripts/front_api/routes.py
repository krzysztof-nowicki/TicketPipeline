from fastapi import APIRouter, HTTPException, Request, status
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from scripts.front_api.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    CreateTicketRequest,
    CreateTicketResponse,
    TicketStatusResponse,
)
from scripts.config import get_settings
from scripts.utils.data_classes import Ticket
from scripts.logging import get_logger, ticket_id_ctx, workflow_id_ctx
from scripts.temporal.workflows import ApprovalSignal, TicketWorkflow

router = APIRouter()
logger = get_logger(__name__)


def get_workflow_id(ticket_id: str) -> str:
    return f"ticket-{ticket_id}"


@router.post(
    "/tickets",
    response_model=CreateTicketResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start workflow for a support ticket",
)
async def create_ticket(request: Request, body: CreateTicketRequest) -> CreateTicketResponse:
    settings = get_settings()
    client: Client = request.app.state.temporal_client
    wf_id = get_workflow_id(body.ticket_id)

    ticket_id_ctx.set(body.ticket_id)
    workflow_id_ctx.set(wf_id)

    ticket = Ticket(
        ticket_id=body.ticket_id,
        customer_id=body.customer_id,
        subject=body.subject,
        body=body.body,
    )

    try:
        await client.start_workflow(
            TicketWorkflow.run,
            ticket,
            id=wf_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
        logger.info(
            f"Successfully started new workflow for ticket {body.ticket_id}",
            extra={"ticket_id": body.ticket_id, "workflow_id": wf_id},
        )
        return CreateTicketResponse(
            ticket_id=body.ticket_id,
            workflow_id=wf_id,
            status="started",
            message="Workflow initiated successfully.",
        )
    except WorkflowAlreadyStartedError:
        logger.warning(
            f"Workflow for ticket {body.ticket_id} already exists. Returning existing workflow reference.",
            extra={"ticket_id": body.ticket_id, "workflow_id": wf_id},
        )
        return CreateTicketResponse(
            ticket_id=body.ticket_id,
            workflow_id=wf_id,
            status="already_running",
            message="Ticket is already being processed by an existing workflow.",
        )
    except Exception as err:
        logger.error(
            f"Failed to start workflow for ticket {body.ticket_id}: {str(err)}",
            extra={"ticket_id": body.ticket_id, "workflow_id": wf_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit ticket workflow: {str(err)}",
        )


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketStatusResponse,
    summary="Get current ticket processing status, decision, and result",
)
async def get_ticket_status(request: Request, ticket_id: str) -> TicketStatusResponse:
    client: Client = request.app.state.temporal_client
    wf_id = get_workflow_id(ticket_id)

    ticket_id_ctx.set(ticket_id)
    workflow_id_ctx.set(wf_id)

    try:
        handle = client.get_workflow_handle(wf_id)
        status_info = await handle.query(TicketWorkflow.get_status)
        return TicketStatusResponse(
            ticket_id=status_info.ticket_id or ticket_id,
            workflow_id=status_info.workflow_id or wf_id,
            current_step=status_info.current_step,
            decision=status_info.decision,
            result=status_info.result,
            error=status_info.error,
        )
    except RPCError as rpc_err:
        logger.warning(
            f"Ticket {ticket_id} not found in Temporal: {str(rpc_err)}",
            extra={"ticket_id": ticket_id, "workflow_id": wf_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' workflow was not found.",
        )
    except Exception as err:
        logger.error(
            f"Failed to query workflow status for ticket {ticket_id}: {str(err)}",
            extra={"ticket_id": ticket_id, "workflow_id": wf_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying ticket status: {str(err)}",
        )


@router.post(
    "/tickets/{ticket_id}/approval",
    response_model=ApprovalResponse,
    summary="Approve or reject a waiting refund action",
)
async def submit_ticket_approval(
    request: Request, ticket_id: str, body: ApprovalRequest
) -> ApprovalResponse:
    client: Client = request.app.state.temporal_client
    wf_id = get_workflow_id(ticket_id)

    ticket_id_ctx.set(ticket_id)
    workflow_id_ctx.set(wf_id)

    try:
        handle = client.get_workflow_handle(wf_id)
        signal = ApprovalSignal(
            approved=body.approved,
            reviewer=body.reviewer,
            note=body.note,
        )
        await handle.signal(TicketWorkflow.submit_approval, signal)

        action_desc = "approved" if body.approved else "rejected"
        logger.info(
            f"Signal {action_desc} submitted successfully for ticket {ticket_id}",
            extra={"ticket_id": ticket_id, "workflow_id": wf_id},
        )

        return ApprovalResponse(
            ticket_id=ticket_id,
            workflow_id=wf_id,
            status="signal_sent",
            message=f"Approval decision '{action_desc}' was delivered to the workflow.",
        )
    except RPCError:
        logger.warning(
            f"Failed to send approval signal for {ticket_id}: workflow not found",
            extra={"ticket_id": ticket_id, "workflow_id": wf_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' workflow was not found.",
        )
    except Exception as err:
        logger.error(
            f"Failed to signal ticket approval for {ticket_id}: {str(err)}",
            extra={"ticket_id": ticket_id, "workflow_id": wf_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit approval: {str(err)}",
        )
