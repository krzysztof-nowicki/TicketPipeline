# Northdesk Agentic Ticket Workflow Service

An autonomous customer support ticket processing pipeline built with **FastAPI**, **Temporal**, and an **LLM Agent** architecture with human-in-the-loop approvals, business rule sanitization, and offline execution capabilities.

---

## 1. Quickstart & Testing

### Running with Docker Compose
The system runs completely offline in `fake` LLM mode with no external API keys or network dependencies required.

```bash
# Start Temporal server, Temporal Web UI, API service, and Worker
docker compose up --build
```

* **Frontend API:** [http://localhost:8001/docs](http://localhost:8001/docs) (OpenAPI Swagger UI)
* **Temporal Web UI:** [http://localhost:8080](http://localhost:8080)
* **Temporal Server:** `localhost:7233`

To stop all services:
```bash
docker compose down
```

### Running Tests
Use `pytest` to run mock examples in tests/:

```bash
pytest -v
```
