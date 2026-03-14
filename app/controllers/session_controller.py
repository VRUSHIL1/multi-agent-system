from __future__ import annotations

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import SessionsService,UserService
from app.validation import SessionCreate
from app.utils import CurrentUser
from app.common import ErrorResponse, success_response


class SessionController:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sessions_service = SessionsService(db)
        self.user_service = UserService(db)

    async def create_session(self, payload: SessionCreate, user: CurrentUser) -> JSONResponse:
        session = await self.sessions_service.create_session_service(payload, user)

        return success_response(
            data={
                "id": session.id,
                "title": session.title,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat() if session.created_at else None
            },
            message="Session created successfully",
            status_code=201
        )

    async def list_sessions(self, user: CurrentUser) -> JSONResponse:
        sessions = await self.sessions_service.list_sessions_service(user)

        return success_response(
            data=[
                {
                    "id": session.id,
                    "title": session.title,
                    "user_id": session.user_id,
                    "created_at": session.created_at.isoformat() if session.created_at else None
                }
                for session in sessions
            ],
            message="Sessions retrieved successfully",
            status_code=200
        )

    async def get_session(self, session_id: int, user: CurrentUser) -> JSONResponse:
        session = await self.sessions_service.get_session_service(user.id, session_id)

        if not session:
            raise ErrorResponse(404, "Session not found")

        return success_response(
            data=session,
            message="Session retrieved successfully",
            status_code=200
        )
    
    async def get_all_sessions(self, user: CurrentUser, page: int, limit: int, search: str | None = None, user_id: int | None = None) -> JSONResponse:

        user_exists = await self.user_service.get_user_by_id(user.id)
        if not user_exists:
            raise ErrorResponse(404, "User not found")
            
        result = await self.sessions_service.get_all_sessions(user, page, limit, search, user_id)
        
        # Convert sessions to dictionaries
        sessions_data = [
            {
                "id": session.id,
                "title": session.title,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat() if session.created_at else None
            }
            for session in result["results"]
        ]
        
        return success_response(
            data={
                "results": sessions_data,
                "page": result["page"],
                "limit": result["limit"],
                "totalPages": result["totalPages"],
                "totalResults": result["totalResults"]
            },
            message="Sessions retrieved successfully",
            status_code=200 
        )
    
    async def get_session_history(self, user_id: int, session_id: int,db: AsyncSession) -> JSONResponse:

        session = await self.sessions_service.get_session_service(session_id, user_id)
        if not session:
            raise ErrorResponse(404, "Session not found")

        history = await self.sessions_service.get_session_history(user_id, session_id)
        return success_response(
            data=history,
            message="Session history retrieved successfully",
            status_code=200
        )
