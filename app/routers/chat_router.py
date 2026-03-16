from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.chat_controller import ChatController
from app.database import get_db
from app.validation.chat_validation import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])

chat_controller = ChatController()


@router.post("/")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await chat_controller.handle_chat(request, db, background_tasks)