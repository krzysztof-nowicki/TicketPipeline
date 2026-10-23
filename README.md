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

---

## 2. API Endpoints & Example Requests

All three core endpoints can be exercised using the example tickets in `data/example_tickets.json`.

### 1. Ingest Ticket (`POST /tickets`)
Submits a ticket and starts an asynchronous workflow.

```bash
curl -X POST http://localhost:8001/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "T-1",
    "customer_id": "C-200",
    "subject": "Can'\''t log in",
    "body": "I forgot my password and can'\''t get into my account."
  }'
```
**Response (`202 Accepted`):**
```json
{
  "ticket_id": "T-1",
  "workflow_id": "ticket-T-1",
  "status": "started",
  "message": "Workflow initiated successfully."
}
```

### 2. Query Ticket Status (`GET /tickets/{ticket_id}`)
Retrieves the workflow progress, resolved decision, and executed action.

```bash
curl http://localhost:8001/tickets/T-1
```
**Response (`200 OK`):**
```json
{
  "ticket_id": "T-1",
  "workflow_id": "ticket-T-1",
  "current_step": "completed",
  "decision": {
    "category": "account",
    "priority": "normal",
    "action": {
      "type": "reply",
      "message": "Open the sign-in page, choose 'Forgot password' and follow the link we email you.",
      "article_ids": ["KB-1"]
    }
  },
  "result": {
    "status": "success",
    "action": "reply",
    "ticket_id": "T-1"
  },
  "error": null
}
```

### 3. Human Approval for Refunds (`POST /tickets/{ticket_id}/approval`)
For billing refund tickets (e.g. `T-2`), the workflow halts in `waiting_for_approval` until a human reviewer sends an approval signal.

```bash
curl -X POST http://localhost:8001/tickets/T-2/approval \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "reviewer": "Alice",
    "note": "Verified duplicate September charge on INV-1002"
  }'
```
**Response (`200 OK`):**
```json
{
  "ticket_id": "T-2",
  "workflow_id": "ticket-T-2",
  "status": "signal_sent",
  "message": "Approval decision 'approved' was delivered to the workflow."
}
```

---

## 3. Architecture & Ticket Flow

```
[Customer / Client]
         │
         ▼
 ┌───────────────┐      Start Workflow       ┌──────────────────┐
 │  FastAPI App  │ ────────────────────────> │ Temporal Cluster │
 └───────┬───────┘                           └────────┬─────────┘
         │ Query Status / Signals                     │ Tasks
         ▼                                            ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                           Temporal                           │
 │                                                              │
 │   TicketWorkflow.run()                                       │
 │     │                                                        │
 │     ├─> Step 1: decide_ticket_activity                       │
 │     │           ├── Tool Calling: get_customer, search_kb... │
 │     │           └── Model: FakeLLM / OpenAI / LocalLLM       │
 │     │                                                        │
 │     ├─> Step 2: validate_and_sanitize_decision (Pure Logic)  │
 │     │           └── Enforce customer, invoice & amount rules │
 │     │                                                        │
 │     ├─> Step 3: Wait for Signal (Refunds only, up to 24h)    │
 │     │                                                        │
 │     └─> Step 4: execute_action_activity                      │
 │                 └── Idempotent Helpdesk Action Execution     │
 └──────────────────────────────────────────────────────────────┘
```

1. **Ingestion:** FastAPI validates the schema and instructs Temporal to start `TicketWorkflow` with ID `ticket-{ticket_id}`.
2. **Decision (Step 1):** The worker runs `decide_ticket_activity`. The agent calls tools (`get_customer`, `get_invoices`, `search_kb`) and returns a structured `Decision`.
3. **Deterministic Guard (Step 2):** Workflow validates the decision against hard business rules in code. If rules are violated, it overrides the decision to an escalation.
4. **Approval Gate (Step 3):** If the action is `refund`, the workflow suspends execution and waits up to 24 hours for a human signal.
5. **Execution (Step 4):** `execute_action_activity` executes the final action against the helpdesk API with idempotency tracking.

---

## 4. Execution Placement: Workflows vs Activities

| Component | Runs As | Why It Runs There |
| :--- | :--- | :--- |
| **`TicketWorkflow`** | **Workflow** | Orchestrates state transitions, handles timers (24h approval wait), and manages signals. Workflows must be **strictly deterministic** (no network, I/O, or random numbers) so Temporal can safely replay them from event history upon worker restarts. |
| **`decide_ticket_activity`** | **Activity** | Interacts with external services (LLM APIs, database lookup, KB search). Inherently **non-deterministic** and prone to transient network latency or rate limits. Temporal handles retries and backoff automatically. |
| **`execute_action_activity`** | **Activity** | Performs side-effects (issuing refunds, sending customer emails, closing tickets). Must run as an activity to support retry policies, timeout boundaries, and idempotency guarantees. |

---

## 5. Retries, Timeouts, and Duplicate Handling

* **Duplicate Prevention:**
  * **API Level:** Starting a workflow uses deterministic ID `ticket-{ticket_id}`. If a request is resent, Temporal raises `WorkflowAlreadyStartedError`, which FastAPI catches and returns `status: "already_running"`.
  * **Activity Level:** `execute_action_activity` creates an `idempotency_key = f"{ticket_id}:{action_type}"`. If retried due to network drops, `FakeActivityToolsAPI` returns the cached response without re-issuing refunds or duplicate emails.
* **Retries:**
  * Activities configure exponential backoff (`initial_interval=1s`, `backoff_coefficient=2.0`, `maximum_attempts=5`). Transient 503 errors from helpdesk APIs are retried automatically.
* **Timeouts:**
  * Activities define `start_to_close_timeout` (2 minutes for decision, 1 minute for action execution) to prevent stuck workers.
  * The refund approval step uses `workflow.wait_condition(..., timeout=timedelta(hours=24))`. If no reviewer responds within 24 hours, it times out and automatically escalates to human support.

---

## 6. Rule Protection from Ticket Content (Prompt Injection Defense)

Customer-submitted text is treated as **untrusted data**. Rules are protected using a dual-layer strategy:

1. **Pre-LLM Guard & System Prompting:**
   * Incoming tickets are screened for common injection phrases (`"ignore all previous instructions"`, `"system override"`, `"developer mode"`). When detected, execution immediately short-circuits to an escalation.
   * The system prompt instructs the model that customer text cannot grant permissions or bypass policies.
2. **Code-Level Validation Boundary (`validate_and_sanitize_decision`):**
   * Even if a model is tricked by prompt injection into outputting an invalid refund (e.g. ticket `T-6` requesting 5,000 EUR), **the LLM does not execute actions directly**.
   * The deterministic workflow passes the proposed decision into `validate_and_sanitize_decision`:
     * Customer must exist in database.
     * Invoice must belong to the customer.
     * Refund amount must be $> 0$ and $\le$ invoice total.
   * If any check fails, the decision is sanitized to an escalation before any activity can execute it.

---

## 7. Production Deployment to Azure

* Unfortunately i do not have much experience with Azure, but based on Azure documentation, both API and workers would be deployed to Azure Container Apps.
Temporal server could be self-hosted on Azure Kubernetes Service (AKS) or managed via Temporal Cloud.
The LLM service would be accessed via Azure OpenAI Service with private endpoints for security.
Local models could be run in either GPU-enabled containers or Azure Machine Learning compute instances, depending on the security and latency requirements.

* Sensitive data and secrets would be stored in Azure Key Vault, and the application would use Managed Identities to access them securely without hardcoding secrets.

---

## 8. AI Coding Assistants: Usage & Error Resolution

AI coding assistants were used to scaffold bare bones of the project, setup Temporal workflow and FastAPI frontend, and write mock test fixtures.

### Example where assistant output required correction:
* **Issue (FakeLLMAgent):**
  When creating the bare fake LLM agent, the assistant generated `FakeLLMAgent` that was hard coded to fix every problem in example tickets instead of returning a base.
* **How it was caught:**
  When actually implementing FakeLLMAgent, the code was clearly hard coded based on examples.
* **Resolution:**
  Used base that AI assistant generated, and rewrote the code inside to a generic algorithm that returns a structured decision based on ticket content, customer data, and KB search results.
---

## 9. Assumptions, Limitations & Next Steps

### Assumptions
* Tickets and KB articles are in English. 
* Database is small enough to fit in memory for this demonstration using BM25 search.
* A single 24-hour approval SLA is sufficient for all refund decisions.
* Escalation to human support is acceptable for any rule violation, unknown decisions for fake LLM or prompt injection attempt.

### Limitations
* `FakeActivityToolsAPI` uses in-memory dictionaries for idempotency; restarts clear the deduplication cache.
* Knowledge base search uses BM25 keyword search rather than semantic vector embeddings. Works well for small KBs but may miss semantically relevant articles in larger data.

### Next Steps
1. **Persistent Data Layer:** Replace JSON files with SQL database.
2. **Semantic search:** Add semantic embeddings alongside BM25 for hybrid search.
3. **Idempotency:** Idempotency cache should be persisted to a database to survive restarts.
