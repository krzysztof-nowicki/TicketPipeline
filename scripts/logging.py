import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

# Context variables to track ticket_id and workflow_id across async contexts
ticket_id_ctx: ContextVar[Optional[str]] = ContextVar("ticket_id_ctx", default=None)
workflow_id_ctx: ContextVar[Optional[str]] = ContextVar("workflow_id_ctx", default=None)


class JSONFormatter(logging.Formatter):
    """
    Outputs log records as structured JSON lines.
    Automatically includes ticket_id and workflow_id from context variables or record attributes.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Ticket and workflow tracking
        ticket_id = getattr(record, "ticket_id", None) or ticket_id_ctx.get()
        workflow_id = getattr(record, "workflow_id", None) or workflow_id_ctx.get()

        if ticket_id:
            log_payload["ticket_id"] = ticket_id
        if workflow_id:
            log_payload["workflow_id"] = workflow_id

        # Extra data passed in record
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload.update(record.extra_data)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Avoid duplicate handlers
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(JSONFormatter())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
