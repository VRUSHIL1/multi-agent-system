# AI Agent Chatbot - Production Build

## Overview
This project provides a production-ready FastAPI backend for an AI Agent chatbot with:
- PostgreSQL persistence
- Gemini 2.5 Flash agent integration
- Email + search tools
- PDF embedding with FAISS
- MCP client integration

## Setup Walkthrough
1. Create and activate a virtual environment.
2. Install dependencies.
3. Configure `.env`.
4. Start PostgreSQL and create the database.
5. Run the API server.

### 1) Environment
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2) Install
```bash
pip install -U pip
pip install .
```
If you are using `uv`, run:
```bash
uv sync
```

### 3) Configure
Edit `.env` and set:
- `DATABASE_URL`
- `GEMINI_API_KEY`
- Email + search provider keys (optional)

### 4) Database
Ensure PostgreSQL is running and the database exists:
```bash
createdb chat_agent
```

### 5) Run
```bash
python main.py
```
Then open:
- `http://localhost:8000/docs`

## API Endpoints
- `POST /api/chat/` - Send a chat message
- `POST /api/sessions/` - Create a new session
- `GET /api/sessions/` - List sessions
- `GET /api/sessions/{session_id}` - Get session with messages
- `POST /api/documents/upload` - Upload a document

## Notes
- On startup, the service will create tables if they do not exist.
- Configure CORS via `ALLOWED_ORIGINS` in `.env`.
- Update `SEARCH_PROVIDER` to `tavily` or `serpapi`.
