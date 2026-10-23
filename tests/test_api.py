from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from scripts.front_api.main import create_app
from scripts.utils.data_classes import (
    Category,
    Decision,
    Priority,
    ReplyAction,
    WorkflowStatus,
    WorkflowStep,
)


@pytest.fixture
def mock_temporal_client():
    client = MagicMock()
    client.start_workflow = AsyncMock()
    client.get_workflow_handle = MagicMock()
    return client


@pytest.fixture
def app_with_mock_temporal(mock_temporal_client):
    app = create_app()
    app.state.temporal_client = mock_temporal_client
    return app


@pytest.mark.asyncio
async def test_create_ticket_endpoint_success(app_with_mock_temporal, mock_temporal_client):
    transport = ASGITransport(app=app_with_mock_temporal)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "ticket_id": "T-1085",
            "customer_id": "C-155",
            "subject": "Need help with password",
            "body": "Can't sign in",
        }
        resp = await ac.post("/tickets", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["ticket_id"] == "T-1085"
        assert data["workflow_id"] == "ticket-T-1085"
        assert data["status"] == "started"
        mock_temporal_client.start_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_ticket_endpoint_duplicate_returns_existing(
    app_with_mock_temporal, mock_temporal_client
):
    mock_temporal_client.start_workflow.side_effect = WorkflowAlreadyStartedError(
        workflow_id="ticket-T-1085",
        workflow_type="TicketWorkflow",
        run_id="run-123",
    )
    transport = ASGITransport(app=app_with_mock_temporal)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "ticket_id": "T-1085",
            "customer_id": "C-155",
            "subject": "Need help with password",
            "body": "Can't sign in",
        }
        resp = await ac.post("/tickets", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "already_running"
        assert data["workflow_id"] == "ticket-T-1085"


@pytest.mark.asyncio
async def test_get_ticket_status_success(app_with_mock_temporal, mock_temporal_client):
    mock_handle = MagicMock()
    mock_status = WorkflowStatus(
        ticket_id="T-1085",
        workflow_id="ticket-T-1085",
        current_step=WorkflowStep.COMPLETED,
        decision=Decision(
            category=Category.ACCOUNT,
            priority=Priority.NORMAL,
            action=ReplyAction(message="Use reset link", article_ids=["KB-1"]),
        ),
        result={"status": "success", "action": "reply"},
    )
    mock_handle.query = AsyncMock(return_value=mock_status)
    mock_temporal_client.get_workflow_handle.return_value = mock_handle

    transport = ASGITransport(app=app_with_mock_temporal)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/tickets/T-1085")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticket_id"] == "T-1085"
        assert data["current_step"] == "completed"
        assert data["decision"]["action"]["type"] == "reply"
        assert data["result"]["status"] == "success"


@pytest.mark.asyncio
async def test_get_ticket_status_not_found(app_with_mock_temporal, mock_temporal_client):
    mock_handle = MagicMock()
    mock_handle.query = AsyncMock(
        side_effect=RPCError("Workflow execution not found", RPCStatusCode.NOT_FOUND, b"")
    )
    mock_temporal_client.get_workflow_handle.return_value = mock_handle

    transport = ASGITransport(app=app_with_mock_temporal)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/tickets/T-NONEXISTENT")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submit_approval_success(app_with_mock_temporal, mock_temporal_client):
    mock_handle = MagicMock()
    mock_handle.signal = AsyncMock()
    mock_temporal_client.get_workflow_handle.return_value = mock_handle

    transport = ASGITransport(app=app_with_mock_temporal)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"approved": True, "reviewer": "Alice", "note": "Verified duplicate charge"}
        resp = await ac.post("/tickets/T-1085/approval", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "signal_sent"
        mock_handle.signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_check(app_with_mock_temporal):
    transport = ASGITransport(app=app_with_mock_temporal)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
