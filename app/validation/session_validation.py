from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.validation.chat_validation import ChatMessageRead


class SessionCreate(BaseModel):
    title: str | None = None


class SessionRead(BaseModel):
    id: int
    title: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionDetail(SessionRead):
    messages: list[ChatMessageRead] = []
