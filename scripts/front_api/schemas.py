from typing import Optional
from pydantic import BaseModel, Field
from scripts.utils.data_classes import Decision, WorkflowStep


class CreateTicketRequest(BaseModel):
    ticket_id: str = Field(..., description="Unique ticket identifier (e.g. T-1)")
    customer_id: str = Field(..., description="Customer identifier (e.g. C-100)")
    subject: str = Field(..., description="Subject of the support ticket")
    body: str = Field(..., description="Detailed message body of the ticket")


class CreateTicketResponse(BaseModel):
    ticket_id: str
    workflow_id: str
    status: str
    message: str


class ApprovalRequest(BaseModel):
    approved: bool = Field(..., description="True to approve refund, False to reject")
    reviewer: Optional[str] = Field(None, description="Reviewer name or identifier")
    note: Optional[str] = Field(None, description="Optional note or explanation")


class ApprovalResponse(BaseModel):
    ticket_id: str
    workflow_id: str
    status: str
    message: str


class TicketStatusResponse(BaseModel):
    ticket_id: str
    workflow_id: str
    current_step: WorkflowStep
    decision: Optional[Decision] = None
    result: Optional[dict] = None
    error: Optional[str] = None
