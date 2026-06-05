# AI Chat Agent Platform

> Production-grade AI agent system with multi-step reasoning, semantic memory, and extensible tool integration

## 🎯 Overview

A sophisticated conversational AI platform built with enterprise-level architecture patterns. This project demonstrates advanced LLM orchestration, agentic workflows, and real-time document intelligence through a modern API-first design.

**Live Demo**: [API Documentation](http://localhost:8000/docs) • **Tech Blog**: [Architecture Deep Dive](#architecture)

## ✨ Key Achievements

- **🤖 Intelligent Agent Pipeline** - Custom LangGraph orchestration with dynamic task planning and multi-step reasoning
- **🧠 Semantic Memory** - Context-aware conversations using Mem0 for long-term memory and automatic summarization
- **📄 Document Intelligence** - Real-time PDF indexing with FAISS vector search and sentence transformers
- **🔧 Extensible Tools** - MCP (Model Context Protocol) integration enabling seamless external tool connectivity
- **🔐 Enterprise Security** - JWT authentication, password reset flows, and prompt injection prevention
- **📱 Multi-Channel Support** - WhatsApp webhook integration for conversational commerce
- **⚡ High Performance** - Async-first architecture with PostgreSQL, connection pooling, and background task processing

## 🏗️ Architecture

### Agent Flow

The system implements a sophisticated routing mechanism that optimizes response generation:

```
┌─────────────────────────────────────────────────────────────┐
│                     User Request                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────┐
          │   Orchestrator Agent     │──┐
          │  • Guard Rails           │  │ Prompt Injection
          │  • Context Building      │  │ Input Validation
          │  • Route Decision        │  │ Token Management
          └────────┬─────────────────┘  │
                   │                    │
        ┌──────────┼────────┬───────────┘
        │          │        │
        ▼          ▼        ▼
    ┏━━━━━━┓  ┏━━━━━━┓  ┏━━━━━━━┓
    ┃Direct┃  ┃ Tool ┃  ┃Planner┃
    ┗━━┬━━━┛  ┗━━┬━━━┛  ┗━━┬━━━━┛
       │         │          │
       └────┬────┴────┬─────┘
            │         │
            │    ┌────▼─────────┐
            │    │   Executor   │──┐ Tool Invocation
            │    │   • Retries  │  │ Timeout Handling
            │    │   • Timeout  │  │ Result Injection
            │    └────┬─────────┘  │
            │         │            │
            │    ┌────▼─────────┐  │
            │    │   Planner    │◄─┘ Dynamic Loop
            │    │ (Next Task)  │    (up to 20 iterations)
            │    └────┬─────────┘
            │         │
            └────┬────┘
                 │
            ┌────▼─────────┐
            │  Supervisor  │
            │  Aggregation │
            └────┬─────────┘
                 │
                 ▼
         ┌───────────────┐
         │ Final Response│
         └───────────────┘
```

**Smart Routing**:
- **Direct**: Simple queries get immediate LLM responses
- **Tool**: Single-tool needs execute without planning overhead  
- **Planner**: Complex multi-step tasks use dynamic planning loop

### Tech Stack

| Component | Technology | Highlights |
|-----------|-----------|-----------|
| **API Framework** | FastAPI + Uvicorn | Async-first, OpenAPI auto-docs, Scalar UI |
| **Agent Framework** | LangGraph + LangChain | State graphs, checkpointing, tool abstractions |
| **LLM Provider** | Google Gemini 2.5 | Structured output, function calling, 1M context |
| **Vector Search** | FAISS + sentence-transformers | Local embeddings, sub-second search |
| **Memory Layer** | Mem0 + PostgreSQL | Semantic memory with rolling summarization |
| **Database** | PostgreSQL + SQLAlchemy 2.0 | Async sessions, cascade relationships |
| **Authentication** | JWT + passlib | Token-based auth, bcrypt hashing |
| **External Tools** | MCP Protocol | Stdio/HTTP adapters for any MCP server |
| **Document Processing** | PyMuPDF + asyncio | Background indexing, chunk optimization |
| **Search Integration** | Tavily / Serper | Configurable web search provider |

## 🚀 Core Features

### 1. Agentic Workflows

Custom agent pipeline with production-grade error handling:

```python
# Orchestrator with structured decision-making
class RoutingDecision(BaseModel):
    decision: Literal["DIRECT", "TOOL", "PLANNER"]
    reasoning: str
    tool: str | None
    args: dict

# Dynamic planner generates ONE task at a time
# Executor handles retries, timeouts, and result injection
# Supervisor aggregates all results into coherent response
```

**Guard Rails**:
- Input validation (8000 char limit)
- Prompt injection detection (regex patterns)
- Timeout protection (20s routing, 30s tools)
- Retry mechanisms with exponential backoff

### 2. Semantic Memory System

**Conversation Summarization**:
- Automatic every 10 user/assistant message pairs
- Rolling summary stored in PostgreSQL
- Injected into agent context for continuity

**Mem0 Integration**:
```python
# Session-scoped semantic memory
memory_context = mem0_service.search_memories(session_id, query)
mem0_service.add_memory([message], session_id)
```

### 3. Document Intelligence

**Upload → Index → Search Pipeline**:
```python
# Background PDF indexing
POST /documents/upload
├─ Save file to data/uploads/
├─ Extract text with PyMuPDF
├─ Chunk with overlap (1000/150)
├─ Embed with all-MiniLM-L6-v2
└─ Store FAISS index + metadata
```

**Semantic Search**:
- Query all indexed documents simultaneously
- L2 distance ranking
- Source attribution with scores

### 4. MCP Tool Integration

Extensible external tool system via Model Context Protocol:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem"],
      "env": { "ALLOWED_DIRS": "/workspace" },
      "is_active": true
    },
    "custom-api": {
      "transport": "http",
      "url": "http://localhost:3000/mcp",
      "is_active": true
    }
  }
}
```

Tools loaded at startup and cached for zero-latency access.

## 📊 Project Statistics

| Metric | Value |
|--------|-------|
| Lines of Code | ~3,500 |
| API Endpoints | 15+ |
| Database Models | 5 |
| Agent Nodes | 4 |
| Built-in Tools | 3 |
| Dependencies | 30+ |
| Test Coverage | Core paths |

## 🛠️ Technical Highlights

### Async Architecture
```python
# Async database sessions with connection pooling
async_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

# FastAPI lifespan for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_services()
    yield
    await cleanup_resources()
```

### Error Handling
- Custom `ErrorResponse` exception with status codes
- Structured logging with trace IDs
- JSON trace emissions for log aggregation
- Graceful degradation on tool failures

### Performance Optimizations
- LangGraph checkpointing with `MemorySaver`
- PDF service lazy initialization
- Background task queue for heavy operations
- Context window trimming (last 10 messages)

## 📡 API Endpoints

### Authentication
```http
POST /users/register    # Create account
POST /users/login       # JWT token
POST /users/forgot-password  # Email reset code
POST /users/reset-password   # Verify + update
GET  /users/get         # Current user info
```

### Chat Sessions
```http
POST   /sessions/              # Create session
GET    /sessions/              # List all
GET    /sessions/{id}          # Get details
DELETE /sessions/{id}          # Delete (cascade)
GET    /sessions/history/{id}  # Message history
```

### Conversations
```http
POST /chat              # Send message
# Body: { "session_id": 1, "message": "..." }

POST /whatsapp/webhook  # WhatsApp integration
# Body: { "chat_id": "...", "message": "...", "sender_name": "..." }
```

### Documents
```http
POST   /documents/upload       # Upload PDF
GET    /documents/             # List uploads
DELETE /documents/{id}         # Remove document
```

## 🎬 Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL 14+
- Google Gemini API key
- Mem0 API key

### Installation
```bash
# Clone and install
git clone <repository>
cd chat-agent
uv sync

# Database setup
createdb chat_agent
uv run alembic upgrade head

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration
```env
# Core
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/chat_agent
SECRET_KEY=your-secret-key-here

# AI Services
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-2.5-flash
MEM0_API_KEY=your-mem0-key

# Search (choose one)
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your-tavily-key

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@example.com
SMTP_PASSWORD=your-app-password
```

### Run
```bash
uv run uvicorn app.main:app --reload

# Access API
# Docs:   http://localhost:8000/docs
# Health: http://localhost:8000/health
```

## 🔧 Development

### Project Structure
```
chat-agent/
├── app/
│   ├── agents/          # LangGraph pipeline
│   │   ├── orchestrator_agent.py  # Routing + guard rails
│   │   ├── planner_agent.py       # Dynamic task generation
│   │   ├── executor_agent.py      # Tool invocation
│   │   └── supervisor_agent.py    # Response aggregation
│   ├── services/        # Business logic
│   │   ├── chat_service.py        # Main chat flow
│   │   ├── mem0_service.py        # Semantic memory
│   │   ├── pdf_service.py         # Vector indexing
│   │   └── summary_service.py     # Conversation summarization
│   ├── tools/           # LangChain + MCP tools
│   ├── models/          # SQLAlchemy ORM
│   ├── routers/         # FastAPI routes
│   └── prompts/         # LLM system prompts
└── alembic/             # Database migrations
```

### Database Schema
```sql
users
├── id, email, name
├── hashed_password
└── reset_code, reset_expiry

chat_sessions
├── id, user_id
└── title, created_at

chat_messages
├── id, session_id
├── role, content
└── is_summarized, timestamp

documents
├── id, user_id, session_id
└── filename, path, upload_date

chat_summaries
└── session_id, summary, last_message_id
```

## 🎓 Learning Outcomes

This project demonstrates:

1. **LLM Engineering**: Prompt engineering, structured output, context management
2. **System Design**: Agent orchestration, async patterns, background tasks
3. **API Development**: RESTful design, authentication, documentation
4. **Database Design**: Relational modeling, migrations, async ORM
5. **Production Practices**: Error handling, logging, observability, security

## 🚧 Roadmap

- [ ] Streaming responses with SSE
- [ ] Multi-user conversations
- [ ] Tool usage analytics dashboard
- [ ] Custom agent templates
- [ ] Langfuse observability integration
- [ ] Docker deployment configuration
- [ ] Comprehensive test suite

## 📄 License

MIT License - See LICENSE file for details

## 👤 Author

**Your Name**
- Portfolio: [your-portfolio.com](https://your-portfolio.com)
- GitHub: [@yourusername](https://github.com/yourusername)
- LinkedIn: [Your Name](https://linkedin.com/in/yourprofile)

---

**Note**: This is a portfolio project demonstrating advanced AI engineering capabilities. Built with ❤️ using Python, FastAPI, and LangGraph.
