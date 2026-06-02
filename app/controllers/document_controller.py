from __future__ import annotations

from uuid import UUID

from fastapi import BackgroundTasks, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
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
        return await DocumentService.upload_document(
            file, session_id, db, background_tasks=background_tasks
        )

    @staticmethod
    async def list_documents_controller(
        db: AsyncSession,
    ):
        documents = await DocumentService.list_documents(db)
        return success_response(
            data=documents,
            message="Documents retrieved successfully",
            status_code=200,
        )

    @staticmethod
    async def delete_document_controller(
        document_id: int,
        db: AsyncSession,
    ) -> JSONResponse:
        deleted = await DocumentService.delete_document(document_id, db)
        if not deleted:
            raise ErrorResponse(404, "Document not found")
        return success_response(
            data=None,
            message="Document deleted successfully",
            status_code=200,
        )
