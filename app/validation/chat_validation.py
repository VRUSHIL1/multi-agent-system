from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(min_length=1)


class ChatMessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    response: str

class WhatsAppWebhookRequest(BaseModel):
    chat_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    sender_name: str | None = None
    sender_phone: str | None = None
