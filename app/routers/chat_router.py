from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.chat_controller import ChatController
from app.database import get_db
from app.validation.chat_validation import ChatRequest
from app.utils.middleware import get_current_user, CurrentUser

router = APIRouter(prefix="/chat", tags=["chat"])

chat_controller = ChatController()


@router.post("/")
async def chat(
    request: ChatRequest, 
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> JSONResponse:
    return await chat_controller.handle_chat(request, db, user)