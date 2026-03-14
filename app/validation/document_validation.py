from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    id: int
    filename: str
    content_type: str | None
    storage_path: str
    uploaded_at: datetime
    session_id: int | None

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
