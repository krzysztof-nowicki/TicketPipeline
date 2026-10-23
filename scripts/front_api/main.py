from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from scripts.front_api.routes import router as tickets_router
from scripts.config import get_settings
from scripts.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    # Initialize Temporal Client connection if not already configured (e.g. by tests)
    if getattr(app.state, "temporal_client", None) is None:
        logger.info(
            f"FastAPI application starting up. Connecting to Temporal at {settings.TEMPORAL_HOST}..."
        )
        try:
            temporal_client = await Client.connect(
                settings.TEMPORAL_HOST,
                namespace=settings.TEMPORAL_NAMESPACE,
                data_converter=pydantic_data_converter,
            )
            app.state.temporal_client = temporal_client
            logger.info("Connected to Temporal server successfully.")
        except Exception as err:
            logger.warning(
                f"Could not connect to Temporal during startup: {err}. Endpoints requiring Temporal may fail until connected."
            )
            app.state.temporal_client = None

    yield

    logger.info("FastAPI application shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Northdesk Agentic Ticket Workflow API",
        description="Autonomous Ticket Resolution Workflow backed by Temporal and FastAPI",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(tickets_router)

    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "ok", "temporal_connected": getattr(app.state, "temporal_client", None) is not None}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("scripts.front_api.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)