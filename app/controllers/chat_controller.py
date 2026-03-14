from __future__ import annotations

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.services.chat_service import ChatService
from app.validation.chat_validation import ChatRequest
from app.utils.middleware import CurrentUser


class ChatController:
    @staticmethod
    async def handle_chat(request: ChatRequest, db: AsyncSession, user: CurrentUser) -> JSONResponse:
        response = await ChatService.chat_service(request, db, user)
        
        if not response:
            raise ErrorResponse(500, "Failed to generate response")
        
        return success_response(
            data={"response": response},
            message="Chat response generated successfully",
            status_code=200,
        )