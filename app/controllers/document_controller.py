from __future__ import annotations

from uuid import UUID

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.services import DocumentService
from app.validation import DocumentUploadResponse

class DocumentController:
    @staticmethod
    async def upload_document_controller(
    file: UploadFile,
    session_id: UUID | None,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    ) -> DocumentUploadResponse:
        return await DocumentService.upload_document(file, session_id, db, background_tasks=background_tasks)