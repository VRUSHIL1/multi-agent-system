from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.chat_controller import ChatController
from app.database import get_db
from app.validation.chat_validation import ChatRequest, WhatsAppWebhookRequest

router = APIRouter(tags=["chat"])

chat_controller = ChatController()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await chat_controller.handle_chat(request, db, background_tasks)


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(
    request: WhatsAppWebhookRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await chat_controller.handle_whatsapp_webhook(request, db, background_tasks)
