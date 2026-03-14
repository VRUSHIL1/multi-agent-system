from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import ChatSession
from app.validation.session_validation import SessionCreate, SessionRead
from app.utils.middleware import CurrentUser
from app.models import ChatMessage

class SessionsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session_service(self, payload: SessionCreate, user: CurrentUser) -> SessionRead | None:
        try:
            session = ChatSession(
                title=payload.title or "New Session",
                user_id=user.id
            )
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
            return session
        except Exception:
            return None

    async def list_sessions_service(self, user: CurrentUser) -> list[SessionRead]:
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.created_at.desc())
        )
        return list(result.scalars())

    async def get_session_service(self, user_id: int, session_id: int) -> dict | None:
        stmt = (
            select(
                ChatSession.id,
                ChatSession.title,
                ChatSession.user_id
            )
            .where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        result = await self.db.execute(stmt)
        
        session = result.mappings().one_or_none()
        if not session:
            return None
            
        return dict(session)

    async def get_all_sessions(self, user: CurrentUser, page: int, limit: int, search: str | None = None, user_id: int | None = None) -> dict:
        where_conditions = [ChatSession.user_id == user.id]
        
        if search:
            where_conditions.append(ChatSession.title.ilike(f"%{search}%"))

        if user_id is not None:
            where_conditions.append(ChatSession.user_id == user_id)
        
        # Get total count
        count_stmt = select(func.count(ChatSession.id)).where(*where_conditions)
        total_results = (await self.db.scalar(count_stmt)) or 0
        
        # Calculate pagination
        skip = (page - 1) * limit
        total_pages = (total_results + limit - 1) // limit
        
        # Get sessions
        stmt = (
            select(ChatSession)
            .where(*where_conditions)
            .order_by(ChatSession.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        
        return {
            "results": sessions,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "totalResults": total_results,
        }

    async def get_session_history(self, user_id: int, session_id: int) -> list[dict] | None:
        stmt = (
            select(
                ChatMessage.role,
                ChatMessage.content,
                ChatMessage.created_at,
            )
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(
                ChatMessage.session_id == session_id,
                ChatSession.user_id == user_id,
            )
            .order_by(ChatMessage.created_at.asc())
        )

        result = await self.db.execute(stmt)
        return [
            {**dict(row), "created_at": row["created_at"].isoformat()}
            for row in result.mappings().all()
        ]