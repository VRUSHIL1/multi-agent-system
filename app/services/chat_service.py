from __future__ import annotations

import logging
import os

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.supervisor_agent import SupervisorAgent
from app.database import get_session_local
from app.models.model import ChatMessage, ChatSession, User
from app.services.mem0_service import Mem0Service
from app.services.summary_service import SummaryService
from app.validation.chat_validation import ChatRequest, WhatsAppWebhookRequest

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    async def chat_service(
        request: ChatRequest,
        db: AsyncSession,
        background_tasks: BackgroundTasks,
    ) -> str | None:
        if not request.session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Session ID is required"
            )

        # Verify session exists
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == request.session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        user_message = ChatMessage(
            session_id=session.id, role="user", content=request.message
        )
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
            supervisor = SupervisorAgent()
            await supervisor.initialize()
            response_text = await supervisor.generate_response(
                request.message,
                session_id=session.id,
                summary=summary,
                memory_context=memory_context,
            )
        except Exception as exc:  # pragma: no cover - surface config errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
            ) from exc

        assistant_message = ChatMessage(
            session_id=session.id, role="assistant", content=response_text
        )
        db.add(assistant_message)
        await db.flush()
        await db.commit()
        await db.refresh(assistant_message)

        # Trigger summarization in the background
        async def summarize_task():
            session_local = get_session_local()
            async with session_local() as task_db:
                await SummaryService.update_summary_if_chunk_complete(
                    task_db, session.id
                )

        background_tasks.add_task(summarize_task)

        return response_text

    @staticmethod
    async def whatsapp_webhook_service(
        request: WhatsAppWebhookRequest,
        db: AsyncSession,
        background_tasks: BackgroundTasks,
    ) -> str | None:
        session = await ChatService._get_or_create_whatsapp_session(request, db)
        return await ChatService.chat_service(
            ChatRequest(session_id=session.id, message=request.message),
            db,
            background_tasks,
        )

    @staticmethod
    async def _get_or_create_whatsapp_session(
        request: WhatsAppWebhookRequest, db: AsyncSession
    ) -> ChatSession:
        title = ChatService._whatsapp_session_title(request)

        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.title == title)
            .order_by(ChatSession.id.asc())
        )
        existing_session = result.scalars().first()
        if existing_session:
            return existing_session

        user = await ChatService._get_whatsapp_user(db)
        session = ChatSession(title=title, user_id=user.id)
        db.add(session)
        await db.flush()
        return session

    @staticmethod
    async def _get_whatsapp_user(db: AsyncSession) -> User:
        configured_user_id = os.getenv("WHATSAPP_WEBHOOK_USER_ID")
        if configured_user_id:
            try:
                user_id = int(configured_user_id)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="WHATSAPP_WEBHOOK_USER_ID must be an integer",
                ) from exc

            user = (
                await db.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="WHATSAPP_WEBHOOK_USER_ID does not match an existing user",
                )
            return user

        user = (await db.execute(select(User).order_by(User.id.asc()))).scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Create a user or set WHATSAPP_WEBHOOK_USER_ID before using the WhatsApp webhook",
            )
        return user

    @staticmethod
    def _whatsapp_session_title(request: WhatsAppWebhookRequest) -> str:
        sender = (request.sender_name or "").strip()
        label = sender or request.chat_id
        title = f"WhatsApp: {label} ({request.chat_id})"
        return title[:255]
