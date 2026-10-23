import asyncio
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from scripts.config import get_settings
from scripts.logging import get_logger, setup_logging
from scripts.temporal.activities import (
    decide_ticket_activity,
    execute_action_activity
)
from scripts.temporal.workflows import TicketWorkflow

logger = get_logger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    logger.info(
        f"Connecting worker to Temporal server at {settings.TEMPORAL_HOST} (namespace: {settings.TEMPORAL_NAMESPACE})"
    )

    client = await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
        data_converter=pydantic_data_converter,
    )

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[TicketWorkflow],
        activities=[
            decide_ticket_activity,
            execute_action_activity,
        ],
    )

    logger.info(
        f"Temporal worker started listening on task queue '{settings.TEMPORAL_TASK_QUEUE}'"
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
