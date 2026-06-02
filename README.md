# Chat Agent

FastAPI backend for an AI chat agent with authenticated users, chat sessions, document upload and search, web search, email sending, WhatsApp webhook support, and MCP-based external tools.

The application stores users, sessions, messages, uploaded documents, and rolling chat summaries in PostgreSQL. Each chat request is handled by a LangGraph agent pipeline backed by Google Gemini, local LangChain tools, optional MCP tools, Mem0 memory, and background conversation summarization.

## Features

- User registration, login, JWT authentication, password reset codes, and current-user lookup.
- Per-user chat sessions with message persistence and history retrieval.
- Agent routing through orchestrator, planner, executor, and supervisor nodes.
- Direct answers, single-tool execution, and dynamic multi-step plans.
- Built-in tools for web search, SMTP email, and PDF semantic search.
- PDF uploads saved under `data/uploads` and indexed in the background with FAISS.
- Session summaries generated after every 10 unsummarized user/assistant messages.
- Mem0 semantic memory scoped by session id.
- MCP tool loading from `app/mcp/mcp_server.json` at application startup.
- WhatsApp webhook endpoint that maps external chats to internal chat sessions.
- Scalar API reference at `/docs` and OpenAPI schema at `/openapi.json`.

## Architecture

```text
Client
  |
  v
FastAPI routers
  |
  v
Controllers
  |
  v
Services
  |
  +-- PostgreSQL via SQLAlchemy async sessions
  +-- BackgroundTasks for PDF indexing and summarization
  +-- Mem0 for semantic memories
  |
  v
SupervisorAgent
  |
  v
LangGraph
  |
  +-- OrchestratorAgent: chooses direct, tool, or planner route
  +-- PlannerAgent: creates one next task at a time
  +-- ExecutorAgent: invokes a LangChain or MCP tool
  +-- Supervisor aggregation: turns task results into the final reply
```

The planner does not create a full plan up front. It reads the accumulated tool results and decides only the next task. The executor can inject previous results into later tool arguments with placeholders such as `{step_1.result}`.

## Tech Stack

| Area | Libraries |
| --- | --- |
| API | FastAPI, Uvicorn, Scalar |
| Database | PostgreSQL, SQLAlchemy async, asyncpg, psycopg2 for Alembic |
| Migrations | Alembic |
| LLM and agents | Google Gemini, LangChain, LangGraph |
| Tools | LangChain tools, MCP adapters |
| Search | Tavily or Serper-compatible search service |
| PDF processing | PyMuPDF, sentence-transformers, FAISS |
| Memory | Mem0 |
| Auth | python-jose, passlib |
| HTTP and resilience | httpx, tenacity |

## Project Layout

```text
chat-agent/
  app/
    agents/          LangGraph state, graph builder, orchestrator, planner, executor, supervisor
    common/          Settings, standard responses, password-reset email helper
    controllers/     HTTP request handlers
    mcp/             MCP client and server configuration
    models/          SQLAlchemy models
    prompts/         LLM system prompts
    routers/         FastAPI route definitions
    services/        Business logic for chat, users, sessions, documents, search, PDF, memory
    tools/           Built-in LangChain tools and MCP tool loader
    utils/           JWT, password hashing, auth middleware helpers
    validation/      Pydantic request and response schemas
    database.py      Async engine/session setup and FastAPI lifespan startup/shutdown
    main.py          FastAPI app entry point
  alembic/           Database migrations
  pyproject.toml     Python package metadata and dependencies
  uv.lock            Locked dependency versions
```

## Requirements

- Python 3.13 or newer.
- PostgreSQL.
- Google Gemini API key.
- Mem0 API key for chat memory.
- A cached or downloadable `sentence-transformers/all-MiniLM-L6-v2` model for PDF indexing.
- `SEARCH_PROVIDER` set to `tavily` or `serper`.
- SMTP credentials for password reset and the `send_email` tool.
- Optional MCP servers configured in `app/mcp/mcp_server.json`.

## Environment Variables

Create a `.env` file in the project root. These names match `app/common/settings.py`.

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/chat_agent

SECRET_KEY=change-this-secret

GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

MEM0_API_KEY=your-mem0-api-key

SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your-tavily-api-key
SERPER_API_KEY=your-serper-api-key

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@example.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=you@example.com

PDF_INDEX_DIR=data/indexes
PDF_CHUNK_SIZE=1000
PDF_CHUNK_OVERLAP=150

# Optional. Used by POST /whatsapp/webhook.
WHATSAPP_WEBHOOK_USER_ID=1
```

`TAVILY_API_KEY` and `SERPER_API_KEY` are optional at settings load time, but the selected `SEARCH_PROVIDER` must have a working key when `web_search` is called. The SMTP variables are loaded when the built-in email tool is created, so keep them configured for normal chat-agent startup.

## Installation

This repository includes `uv.lock`, so `uv` is the recommended installer.

```bash
uv sync
```

Equivalent pip workflow:

```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -e .
```

## Database

Create the PostgreSQL database, then run migrations.

```bash
createdb chat_agent
uv run alembic upgrade head
```

If you are not using `uv`, run:

```bash
alembic upgrade head
```

Alembic reads `DATABASE_URL` from `.env` and converts the async PostgreSQL URL to a psycopg2 URL for migrations.

## Run

```bash
uv run uvicorn app.main:app --reload
```

Without `uv`:

```bash
uvicorn app.main:app --reload
```

Useful URLs:

- API health: `http://localhost:8000/health`
- Scalar API reference: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

## API Overview

Most session endpoints require a bearer token returned by `/users/login`.

### Users

```http
POST /users/register
POST /users/login
GET  /users/get
POST /users/forgot-password
POST /users/reset-password
```

Register:

```json
{
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "password": "password123"
}
```

Login:

```json
{
  "email": "ada@example.com",
  "password": "password123"
}
```

### Sessions

```http
POST   /sessions/
GET    /sessions/
GET    /sessions/{session_id}
DELETE /sessions/{session_id}
GET    /sessions/history/{session_id}
GET    /sessions/user/{user_id}?page=1&limit=10&search=term
```

Create a session:

```json
{
  "title": "Research notes"
}
```

### Chat

```http
POST /chat
```

```json
{
  "session_id": 1,
  "message": "Search my uploaded PDFs for warranty terms."
}
```

The chat service:

1. Verifies the session exists.
2. Stores the user message.
3. Loads the current rolling summary.
4. Searches Mem0 for relevant session memories.
5. Runs the Supervisor/LangGraph agent pipeline.
6. Stores the assistant response.
7. Schedules summary refresh in the background.

### WhatsApp Webhook

```http
POST /whatsapp/webhook
```

```json
{
  "chat_id": "919999999999",
  "message_id": "wamid.example",
  "message": "Summarize the latest message",
  "sender_name": "Ada"
}
```

The webhook finds or creates a session titled `WhatsApp: <sender or chat_id> (<chat_id>)`. If `WHATSAPP_WEBHOOK_USER_ID` is set, that user owns the session. Otherwise the first user in the database is used.

### Documents

```http
POST   /documents/upload
GET    /documents/
DELETE /documents/{document_id}
```

Upload expects multipart form data:

- `file`: required uploaded file.
- `session_id`: optional session id.

PDF files are indexed in a FastAPI background task. The index file is written to `PDF_INDEX_DIR` as `<document_id>.faiss` with matching JSON metadata. The `search_pdf` tool searches all available FAISS indexes.

## Built-In Tools

| Tool | Purpose | Important args |
| --- | --- | --- |
| `web_search` | Search the web with the configured provider. | `query`, `max_results` |
| `send_email` | Send plain text or HTML email over SMTP. | `to_address`, `subject`, `body`, `is_html` |
| `search_pdf` | Search indexed uploaded PDFs. | `query`, `top_k` |

MCP tools are appended to this list at startup after `mcp_client.connect_all()` succeeds.

## MCP Configuration

External MCP servers are configured in `app/mcp/mcp_server.json`.

```json
{
  "mcpServers": {
    "example-stdio": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {
        "API_KEY": "API_KEY_ENV_VAR_NAME"
      },
      "is_active": true
    },
    "example-http": {
      "transport": "http",
      "url": "http://localhost:3000/mcp",
      "is_active": true
    }
  }
}
```

Notes:

- Set `is_active` to `false` to skip a server without deleting it.
- For `env`, values are treated as environment variable names when matching variables exist.
- Stdio servers are launched by `MultiServerMCPClient`.
- Tools are loaded once and cached during the FastAPI lifespan startup.

## Agent Flow

The shared LangGraph state is defined in `app/agents/state.py`:

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    route: str
    current_task: dict | None
    results: list[str]
    response: str
```

Routing behavior:

- `direct`: the orchestrator calls Gemini for a normal answer and ends the graph.
- `tool`: the orchestrator selects a single known tool and sends it to the executor.
- `planner`: the planner creates one task, the executor runs it, and the graph loops until the planner returns `DONE` or reaches 20 iterations.

Guardrails in the orchestrator reject empty messages, messages over 8,000 characters, and common prompt-injection patterns. LLM routing uses structured output, retries, and a 20-second timeout. Tool execution retries twice with a 30-second timeout per attempt.

## Data Model

Core tables:

- `users`: account data, hashed password, password reset code, reset expiry.
- `chat_sessions`: user-owned session records.
- `chat_messages`: user and assistant messages, including `is_summarized`.
- `documents`: uploaded file metadata and optional session link.
- `chat_summaries`: rolling summary per session.

Session deletion cascades to messages, documents, and summaries through SQLAlchemy relationships.

## Development Notes

- The app performs a database connectivity check during lifespan startup.
- PDF embedding service is initialized at startup and again lazily if needed.
- MCP startup failures are logged as warnings so the API can still run without MCP tools.
- Password reset email uses `app/common/user_email.py`.
- The general `send_email` tool uses `app/services/email_service.py`.
- Standard successful JSON responses use `{ "status_code": ..., "message": ..., "data": ... }`.
- Custom `ErrorResponse` exceptions are converted to `{ "status_code": ..., "message": ... }`.

## Troubleshooting

`DATABASE_URL environment variable is not set`

Set `DATABASE_URL` in `.env`. The app requires an async URL such as `postgresql+asyncpg://...`.

`GEMINI_API_KEY environment variable is not set`

Set `GEMINI_API_KEY` before starting the app or running chat requests.

`Tavily API key not configured` or `Serper API key not configured`

Set `SEARCH_PROVIDER` to the provider you want and provide its matching API key.

`No documents have been uploaded yet`

Upload a PDF through `/documents/upload`, then wait for the background indexing task to finish.

MCP tools are missing

Check `app/mcp/mcp_server.json`, make sure the server has `is_active: true`, and verify the configured command or URL can be reached from the machine running FastAPI.
