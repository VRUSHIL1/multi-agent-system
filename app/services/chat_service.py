from __future__ import annotations

import logging
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gemini_agent import GeminiAgent
from app.database import get_session_local
from app.models.model import ChatMessage, ChatSession
from app.services.summary_service import SummaryService
from app.services.mem0_service import Mem0Service
from app.validation.chat_validation import ChatRequest

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    async def chat_service(
        request: ChatRequest,
        db: AsyncSession,
        background_tasks: BackgroundTasks,
    ) -> str | None:
        if not request.session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session ID is required")

        # Verify session exists
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == request.session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        user_message = ChatMessage(session_id=session.id, role="user", content=request.message)
        db.add(user_message)
        await db.flush()

        # Get existing summary for context
        summary = await SummaryService.get_summary(db, session.id)
        
        # Initialize Mem0 service and get relevant memories
        mem0_service = Mem0Service()
        
        # Search for relevant memories
        memory_context = mem0_service.search_memories(session.id, request.message)
        
        # Add current message to memory
        mem0_service.add_memory([request.message], session.id)

        try:
            agent = GeminiAgent()
            response_text = await agent.generate_response(
                request.message, 
                session_id=session.id, 
                summary=summary,
                memory_context=memory_context
            )
        except Exception as exc:  # pragma: no cover - surface config errors
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

        assistant_message = ChatMessage(session_id=session.id, role="assistant", content=response_text)
        db.add(assistant_message)
        await db.flush()
        await db.commit()
        await db.refresh(assistant_message)

        # Trigger summarization in the background
        async def summarize_task():
            session_local = get_session_local()
            async with session_local() as task_db:
                await SummaryService.update_summary_if_chunk_complete(task_db, session.id)
        
        background_tasks.add_task(summarize_task)

        return response_text
