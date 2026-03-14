from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import GeminiAgent
from app.models.model import ChatMessage, ChatSession
from app.validation.chat_validation import ChatRequest
from app.utils.middleware import CurrentUser


class ChatService:
    @staticmethod
    async def chat_service(request: ChatRequest, db: AsyncSession, user: CurrentUser) -> str | None:
        if not request.session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session ID is required")
        
        # Verify session belongs to user
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user.id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        user_message = ChatMessage(session_id=session.id, role="user", content=request.message)
        db.add(user_message)
        await db.flush()

        try:
            agent = GeminiAgent()
            response_text = await agent.generate_response(request.message, session_id=session.id)
        except Exception as exc:  # pragma: no cover - surface config errors
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

        assistant_message = ChatMessage(session_id=session.id, role="assistant", content=response_text)
        db.add(assistant_message)
        await db.flush()
        await db.commit()
        await db.refresh(assistant_message)

        return response_text