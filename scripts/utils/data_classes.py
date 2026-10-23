from enum import Enum
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field


class Category(str, Enum):
    ACCOUNT = "account"
    BILLING = "billing"
    TECHNICAL = "technical"
    OTHER = "other"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ActionType(str, Enum):
    REPLY = "reply"
    REFUND = "refund"
    ESCALATE = "escalate"
    CLOSE = "close"


class WorkflowStep(str, Enum):
    PENDING = "pending"
    DECIDING = "deciding"
    CHECKING_DECISION = "checking_decision"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    ACTING = "acting"
    COMPLETED = "completed"
    FAILED = "failed"


# Domain Entities
class Customer(BaseModel):
    customer_id: str
    name: str
    plan: str
    status: str


class Invoice(BaseModel):
    invoice_id: str
    customer_id: str
    month: str
    amount_eur: float
    status: str


class KBArticle(BaseModel):
    article_id: str
    title: str
    text: str


class Ticket(BaseModel):
    ticket_id: str
    customer_id: str
    subject: str
    body: str


# Action Details
class ReplyAction(BaseModel):
    type: Literal[ActionType.REPLY] = ActionType.REPLY
    message: str
    article_ids: list[str] = Field(default_factory=list)


class RefundAction(BaseModel):
    type: Literal[ActionType.REFUND] = ActionType.REFUND
    invoice_id: str
    amount_eur: float


class EscalateAction(BaseModel):
    type: Literal[ActionType.ESCALATE] = ActionType.ESCALATE
    reason: str


class CloseAction(BaseModel):
    type: Literal[ActionType.CLOSE] = ActionType.CLOSE
    reason: str


TicketAction = Annotated[
    Union[ReplyAction, RefundAction, EscalateAction, CloseAction],
    Field(discriminator="type"),
]


class Decision(BaseModel):
    category: Category
    priority: Priority
    action: TicketAction


class WorkflowStatus(BaseModel):
    ticket_id: str
    workflow_id: str
    current_step: WorkflowStep
    decision: Optional[Decision] = None
    result: Optional[dict] = None
    error: Optional[str] = None
