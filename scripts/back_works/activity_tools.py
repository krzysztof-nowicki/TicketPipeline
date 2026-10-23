import random
from typing import Any, Optional
from scripts.config import get_settings
from scripts.logging import get_logger

logger = get_logger(__name__)


class ActivityToolsTransientError(Exception):
    """Temporary error indicating ActivityTools service is briefly unavailable."""
    pass


class FakeActivityToolsAPI:
    """
    Fake ActivityTools API for carrying out ticket actions.
    """

    def __init__(self, failure_rate: Optional[float] = None):
        settings = get_settings()
        self.failure_rate = (
            failure_rate if failure_rate is not None else settings.ACTIVITYTOOLS_FAILURE_RATE
        )
        self._processed_actions: dict[str, dict[str, Any]] = {}

    def _simulate_transient_failure(self) -> None:
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            logger.warning("[ActivityToolsAPI] Simulated transient network/server failure!")
            raise ActivityToolsTransientError("ActivityTools service temporarily unavailable (HTTP 503)")

    def send_reply(
        self,
        ticket_id: str,
        message: str,
        article_ids: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._simulate_transient_failure()

        if idempotency_key in self._processed_actions:
            logger.info(
                f"[ActivityToolsAPI] Idempotency hit for reply on ticket {ticket_id} (key={idempotency_key})"
            )
            return self._processed_actions[idempotency_key]

        logger.info(
            f"[ActivityToolsAPI] Sending reply to ticket {ticket_id}. Cited KB articles: {article_ids}"
        )
        result = {
            "status": "success",
            "action": "reply",
            "ticket_id": ticket_id,
            "message": message,
            "article_ids": article_ids,
            "idempotency_key": idempotency_key,
        }
        self._processed_actions[idempotency_key] = result
        return result

    def issue_refund(
        self,
        ticket_id: str,
        invoice_id: str,
        amount_eur: float,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._simulate_transient_failure()

        if idempotency_key in self._processed_actions:
            logger.info(
                f"[ActivityToolsAPI] Idempotency hit for refund on ticket {ticket_id} (key={idempotency_key}). Refund NOT re-issued."
            )
            return self._processed_actions[idempotency_key]

        logger.info(
            f"[ActivityToolsAPI] Issuing refund of {amount_eur} EUR on invoice {invoice_id} for ticket {ticket_id}"
        )
        result = {
            "status": "success",
            "action": "refund",
            "ticket_id": ticket_id,
            "invoice_id": invoice_id,
            "amount_eur": amount_eur,
            "idempotency_key": idempotency_key,
        }
        self._processed_actions[idempotency_key] = result
        return result

    def escalate(
        self,
        ticket_id: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._simulate_transient_failure()

        if idempotency_key in self._processed_actions:
            logger.info(
                f"[ActivityToolsAPI] Idempotency hit for escalate on ticket {ticket_id} (key={idempotency_key})"
            )
            return self._processed_actions[idempotency_key]

        logger.info(f"[ActivityToolsAPI] Escalating ticket {ticket_id}. Reason: {reason}")
        result = {
            "status": "success",
            "action": "escalate",
            "ticket_id": ticket_id,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        self._processed_actions[idempotency_key] = result
        return result

    def close(
        self,
        ticket_id: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._simulate_transient_failure()

        if idempotency_key in self._processed_actions:
            logger.info(
                f"[ActivityToolsAPI] Idempotency hit for close on ticket {ticket_id} (key={idempotency_key})"
            )
            return self._processed_actions[idempotency_key]

        logger.info(f"[ActivityToolsAPI] Closing ticket {ticket_id}. Reason: {reason}")
        result = {
            "status": "success",
            "action": "close",
            "ticket_id": ticket_id,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        self._processed_actions[idempotency_key] = result
        return result


_global_activitytools_api: Optional[FakeActivityToolsAPI] = None


def get_activitytools_api() -> FakeActivityToolsAPI:
    global _global_activitytools_api
    if _global_activitytools_api is None:
        _global_activitytools_api = FakeActivityToolsAPI()
    return _global_activitytools_api
