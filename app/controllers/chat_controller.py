from __future__ import annotations

from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.services.chat_service import ChatService
from app.validation.chat_validation import ChatRequest


class ChatController:
    @staticmethod
    async def handle_chat(
        request: ChatRequest,
        db: AsyncSession,
        background_tasks: BackgroundTasks,
    ) -> JSONResponse:
        response = await ChatService.chat_service(request, db, background_tasks)

        if not response:
            raise ErrorResponse(500, "Failed to generate response")

        return success_response(
            data={"response": response},
            message="Chat response generated successfully",
            status_code=200,
        )