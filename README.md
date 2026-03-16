# AI Agent Chatbot - Production Ready

## Overview

A sophisticated AI-powered chatbot built with FastAPI that combines multiple AI capabilities including conversational AI, document processing, web search, and email functionality. The system uses Google's Gemini 2.5 Flash model as the core AI agent with persistent conversation storage and advanced document embedding capabilities.

### Key Features

- **AI Agent Integration**: Powered by Google Gemini 2.5 Flash for intelligent conversations
- **Persistent Storage**: PostgreSQL database for session and message history
- **Document Processing**: PDF upload and embedding with FAISS vector search
- **Web Search**: Integrated search capabilities via Tavily or Serper APIs
- **Email Integration**: SMTP support for sending emails through the agent
- **Session Management**: Multi-session support with conversation history
- **RESTful API**: FastAPI-based backend with automatic OpenAPI documentation
- **MCP Client**: Model Context Protocol integration for extended capabilities

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   PostgreSQL   │
│   Client        │◄──►│   Backend       │◄──►│   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   AI Services   │
                       │                 │
                       │ • Gemini 2.5    │
                       │ • FAISS Vector  │
                       │ • Search APIs   │
                       │ • SMTP Email    │
                       └─────────────────┘
```

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Google Gemini API key
- (Optional) Tavily or Serper API key for web search
- (Optional) Gmail SMTP credentials for email functionality

## Installation & Setup

### 1. Environment Setup

Create and activate a Python virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate
```

### 2. Install Dependencies

Using pip:
```bash
pip install -U pip
pip install .
```

Using uv (recommended for faster installs):
```bash
uv sync
```

### 3. Database Setup

Ensure PostgreSQL is running and create the database:

```bash
# Create database
createdb chat_agent

# Or using psql
psql -U postgres -c "CREATE DATABASE chat_agent;"
```

### 4. Environment Configuration

Create a `.env` file in the project root with the following configuration:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/chat_agent

# AI Model Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Email Configuration (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=your_email@gmail.com

# Security
SECRET_KEY=your_secret_key_here

# Search Provider Configuration (Optional)
SEARCH_PROVIDER=tavily  # or 'serpapi'
TAVILY_API_KEY=your_tavily_api_key
SERPER_API_KEY=your_serper_api_key

# PDF Processing Configuration
PDF_INDEX_DIR=./data/faiss
PDF_CHUNK_SIZE=1000
PDF_CHUNK_OVERLAP=200

# CORS Configuration (Optional)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

#### Configuration Details

**Database URL Format:**
- `postgresql+asyncpg://user:password@host:port/database`
- Use `asyncpg` driver for optimal async performance

**Gemini API Key:**
- Obtain from [Google AI Studio](https://makersuite.google.com/app/apikey)
- Supports Gemini 2.5 Flash model for fast responses

**Email Configuration:**
- For Gmail, use App Passwords instead of regular password
- Enable 2FA and generate App Password in Google Account settings

**Search Providers:**
- **Tavily**: Better for general web search, get key from [Tavily](https://tavily.com)
- **Serper**: Good for Google search results, get key from [Serper](https://serper.dev)

### 5. Database Migration

The application automatically creates tables on startup. For manual migration control:

```bash
# Generate migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

### 6. Start the Application

```bash
# Production mode
python main.py

# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Reference

### Core Endpoints

#### Chat Operations
```http
POST /api/chat/
Content-Type: application/json

{
  "message": "Hello, how can you help me?",
  "session_id": "optional-session-id"
}
```

#### Session Management
```http
# Create new session
POST /api/sessions/
{
  "name": "My Chat Session"
}

# List all sessions
GET /api/sessions/

# Get specific session with messages
GET /api/sessions/{session_id}

# Delete session
DELETE /api/sessions/{session_id}
```

#### Document Operations
```http
# Upload PDF document
POST /api/documents/upload
Content-Type: multipart/form-data

file: [PDF file]
session_id: optional-session-id

# List uploaded documents
GET /api/documents/

# Search documents
POST /api/documents/search
{
  "query": "search terms",
  "limit": 5
}
```

### Response Formats

**Chat Response:**
```json
{
  "response": "AI agent response text",
  "session_id": "session-uuid",
  "message_id": "message-uuid",
  "timestamp": "2024-01-01T12:00:00Z",
  "tools_used": ["search", "email"]
}
```

**Error Response:**
```json
{
  "detail": "Error description",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Agent Capabilities

### 1. Conversational AI
- Natural language understanding and generation
- Context-aware responses based on conversation history
- Multi-turn conversations with memory

### 2. Web Search Integration
- Real-time web search capabilities
- Summarization of search results
- Source attribution and links

### 3. Email Functionality
- Send emails through SMTP
- Support for HTML and plain text emails
- Attachment support

### 4. Document Processing
- PDF upload and text extraction
- Automatic chunking and embedding
- Vector similarity search with FAISS
- Document-based question answering

### 5. Session Management
- Persistent conversation history
- Multiple concurrent sessions
- Session-based context isolation

## Development

### Project Structure
```
chat-agent/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── api/                 # API routes
│   ├── services/            # Business logic
│   └── agents/              # AI agent implementations
├── data/
│   └── faiss/               # FAISS vector indices
├── alembic/                 # Database migrations
├── tests/                   # Test files
├── .env                     # Environment variables
├── pyproject.toml           # Project configuration
└── README.md
```

### Running Tests
```bash
# Install test dependencies
pip install -e ".[test]"

# Run tests
pytest

# Run with coverage
pytest --cov=app
```

### Code Quality
```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## Deployment

### Docker Deployment
```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install .

EXPOSE 8000
CMD ["python", "main.py"]
```

### Environment Variables for Production
```env
# Production database
DATABASE_URL=postgresql+asyncpg://user:pass@prod-db:5432/chat_agent

# Security
SECRET_KEY=production-secret-key
ALLOWED_ORIGINS=https://yourdomain.com

# Logging
LOG_LEVEL=INFO
```

## Troubleshooting

### Common Issues

**Database Connection Errors:**
- Verify PostgreSQL is running
- Check DATABASE_URL format
- Ensure database exists

**Gemini API Errors:**
- Verify API key is valid
- Check API quotas and limits
- Ensure model name is correct

**PDF Processing Issues:**
- Ensure PDF_INDEX_DIR exists and is writable
- Check file permissions
- Verify PDF files are not corrupted

**Email Sending Failures:**
- Use App Passwords for Gmail
- Check SMTP settings
- Verify firewall/network access

### Logging

The application uses structured logging. Check logs for detailed error information:

```bash
# View logs in development
tail -f app.log

# Set log level
export LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review the API documentation at `/docs`