# AI Chat Agent — Dynamic Multi-Agent System

A production-grade AI chatbot built with **FastAPI** and **LangGraph** that uses a dynamic multi-agent loop to plan and execute complex tasks step by step. Powered by **Google Gemini 2.5 Flash**, it supports document Q&A, web search, email dispatch, WhatsApp, YouTube, and any external tool via the **Model Context Protocol (MCP)**.

---

## Architecture

The system routes every incoming message through a four-node LangGraph pipeline:

```
User Message
     |
     v
SUPERVISOR AGENT
  - Validates session
  - Fetches conversation summary
  - Retrieves relevant Mem0 memories
  - Invokes LangGraph
     |
     v
ORCHESTRATOR AGENT
  - Decides route: DIRECT / TOOL / PLANNER
     |
     +---> DIRECT (simple Q&A, no tools needed)
     |          |
     |          v
     |        END
     |
     +---> TOOL (single, known tool call)
     |          |
     |          v
     |       EXECUTOR --> END
     |
     +---> PLANNER (complex multi-step task)
                |
                v
           PLANNER AGENT
             - Sees accumulated results so far
             - Generates ONE task at a time
                |
                v
           EXECUTOR AGENT
             - Runs the tool
             - Injects placeholders (e.g. {step_1.result})
             - Appends result to state
                |
                +---> loop back to PLANNER (if more steps needed)
                |
                +---> END (when Planner responds DONE)
     |
     v
SUPERVISOR AGGREGATION
  - Synthesizes all results into a final response
```

The key design choice is that the **Planner never pre-plans the full sequence**. It sees what has been done so far and decides the single next action, making the loop adaptive to real tool outputs.

---

## Features

### Dynamic Task Planning
- Generates one task per iteration based on accumulated results
- Supports placeholder injection — `{step_1.result}` in tool args is automatically replaced with the actual output from step 1
- Detects completion and exits the loop cleanly
- Hard cap of 20 iterations to prevent runaway loops

### Dual Memory System
**Conversation Summarization**
- Every 10 messages, the last unsummarized chunk is sent to Gemini 2.0 Flash Lite to produce an updated rolling summary
- Runs in a FastAPI `BackgroundTask` so it never blocks the response
- Summary is injected into the next request as context

**Semantic Memory (Mem0)**
- Stores user messages as vector memories scoped to each session
- Before each request, retrieves the most relevant past memories and injects them into the prompt
- Keeps long-term context alive across many sessions without a growing message list

### Document Q&A
- Upload PDF files via the `/documents/upload` endpoint
- Text is extracted with PyMuPDF, chunked, and embedded using Google Generative AI embeddings
- Embeddings are stored in per-file FAISS indexes
- The `search_pdf` tool searches across all uploaded documents at query time and returns ranked chunks

### MCP Tool Integration
- Connects to any MCP-compatible server at startup via `mcp_server.json`
- Currently configured servers: **WhatsApp**, **YouTube**, **Database**
- Tools are loaded once and cached — no subprocess spawned per request
- Add new external capabilities by editing `mcp_server.json`, no code changes needed

### Built-in LangChain Tools
| Tool | Description |
|------|-------------|
| `web_search` | Real-time web search via Tavily or Serper |
| `send_email` | Send plain-text or HTML email via SMTP |
| `search_pdf` | Semantic search across all uploaded PDFs |

### Orchestrator Guard Rails
- Blocks empty messages and inputs over 8,000 characters
- Detects and rejects prompt injection attempts (regex-based)
- Structured output routing — no brittle JSON regex parsing
- Retry with exponential backoff on all LLM calls (tenacity)
- Per-call timeouts (20s routing, 30s aggregation, 30s tool execution)
- Structured JSON trace logged per request for observability

### Session & User Management
- JWT-based authentication with password reset flow
- Multiple chat sessions per user, each with independent context
- All messages stored in PostgreSQL with `is_summarized` flag for efficient chunking
- Session-scoped documents and summaries with cascade delete

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Uvicorn |
| LLM | Google Gemini 2.5 Flash (`langchain-google-genai`) |
| Agent orchestration | LangGraph, LangChain |
| Long-term memory | Mem0 |
| Vector search | FAISS (`faiss-cpu`) |
| Embeddings | Google Generative AI / sentence-transformers |
| PDF parsing | PyMuPDF |
| External tools | MCP (`langchain-mcp-adapters`) |
| Database | PostgreSQL, SQLAlchemy (async), asyncpg |
| Migrations | Alembic |
| Auth | python-jose (JWT), passlib |
| Retry / resilience | tenacity |

---

## Project Structure

```
chat-agent/
├── app/
│   ├── agents/
│   │   ├── graph.py               # LangGraph definition and routing logic
│   │   ├── orchestrator_agent.py  # Entry point — routes DIRECT / TOOL / PLANNER
│   │   ├── planner_agent.py       # Generates one task per iteration
│   │   ├── executor_agent.py      # Executes tools with retry + placeholder injection
│   │   ├── supervisor_agent.py    # Initializes graph, aggregates final response
│   │   └── state.py               # Shared AgentState TypedDict
│   ├── services/
│   │   ├── chat_service.py        # Orchestrates memory, agent, and DB writes
│   │   ├── summary_service.py     # Rolling summarization every 10 messages
│   │   ├── mem0_service.py        # Mem0 add / search wrappers
│   │   ├── pdf_embedding_service.py  # PDF chunking, embedding, FAISS indexing
│   │   └── email_service.py       # SMTP email dispatch
│   ├── tools/
│   │   ├── langchain_tools.py     # EmailTool, SearchTool, PDFSearchTool
│   │   └── mcp_tools.py           # Loads MCP tools as LangChain BaseTool instances
│   ├── mcp/
│   │   ├── client.py              # MCPClient — connects, caches, and calls MCP servers
│   │   └── mcp_server.json        # MCP server config (WhatsApp, YouTube, Database)
│   ├── models/
│   │   └── model.py               # SQLAlchemy models: User, ChatSession, ChatMessage,
│   │                              #   Document, ChatSummary
│   ├── routers/                   # FastAPI route definitions
│   ├── controllers/               # Request handlers
│   ├── validation/                # Pydantic request/response schemas
│   ├── prompts/                   # All LLM system prompts
│   ├── database.py                # Async engine, session factory, lifespan hook
│   ├── main.py                    # FastAPI app setup
│   └── common/                   # Settings, shared utilities
├── alembic/                       # Database migrations
├── pyproject.toml
└── .env
```

---

## Setup

### Prerequisites
- Python 3.13+
- PostgreSQL 12+
- Google Gemini API key
- (Optional) Tavily or Serper API key for web search
- (Optional) Gmail SMTP credentials for the email tool
- (Optional) Mem0 API key for semantic memory

### Install

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e .
```

### Environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/chat_agent

GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash

MEM0_API_KEY=your_mem0_key

SECRET_KEY=your_jwt_secret

# Optional
TAVILY_API_KEY=your_tavily_key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password
```

### Database

```bash
# Create the database
createdb chat_agent

# Run migrations
alembic upgrade head
```

### Run

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

---

## API Reference

### Authentication

```http
POST /users/register
POST /users/login
POST /users/forgot-password
POST /users/reset-password
```

### Sessions

```http
POST   /sessions/          # Create a new chat session
GET    /sessions/          # List all sessions for the current user
GET    /sessions/{id}      # Get session with full message history
DELETE /sessions/{id}      # Delete session and all associated data
```

### Chat

```http
POST /chat/
Content-Type: application/json

{
  "message": "Search for the latest AI news and email me a summary",
  "session_id": 1
}
```

Response:
```json
{
  "response": "I searched for the latest AI news and sent a summary to your inbox.",
  "session_id": 1
}
```

### Documents

```http
POST /documents/upload
Content-Type: multipart/form-data

file: <PDF file>
session_id: 1       (optional)
```

---

## MCP Server Configuration

Add or remove external tool servers in `app/mcp/mcp_server.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {
        "API_KEY": "MY_API_KEY_ENV_VAR"
      },
      "is_active": true
    },
    "http-server": {
      "transport": "http",
      "url": "http://localhost:3000/mcp",
      "is_active": true
    }
  }
}
```

Set `"is_active": false` to disable a server without removing it. The `env` values are resolved from environment variables at startup.

---

## Agent State

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    # Full conversation history (summary + memories + current message)

    route: str
    # Orchestrator decision: "direct", "tool", or "planner"

    current_task: dict | None
    # Active task from Planner: {"tool": "...", "args": {...}, "description": "..."}
    # Set to None when the loop ends

    results: list[str]
    # Accumulated tool outputs — results[0] = first task, results[1] = second, etc.

    response: str
    # Final synthesized response from the Supervisor
```

---

## Logs

Key log markers to follow a request end-to-end:

```
🧭  Orchestrator | decision=PLANNER
🗂️  Planner | iteration 0
⚙️  Executor | executing task | tool=web_search
📦  Executor | result [web_search]: ...
✅  Planner | user request complete — ending loop
🧠  Supervisor | aggregating 2 result(s)
✅  Supervisor | aggregation complete
```

Set `LOG_LEVEL=DEBUG` in `.env` for verbose LLM call tracing.
