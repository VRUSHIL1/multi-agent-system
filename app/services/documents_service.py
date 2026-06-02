from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Document
from app.services import get_pdf_service
from app.validation import DocumentUploadResponse

logger = logging.getLogger(__name__)


def _process_pdf_background(storage_path: str, document_id: str) -> None:
    """Run PDF embedding in a background thread (called by BackgroundTasks)."""
    try:
        pdf_service = get_pdf_service()
        asyncio.run(pdf_service.embed_pdf(storage_path, index_name=document_id))
        logger.info("✅ PDF embedded successfully | document_id=%s", document_id)
    except Exception as exc:
        logger.error(
            "❌ PDF embedding failed | document_id=%s | error=%s", document_id, exc
        )


class DocumentService:
    @staticmethod
    async def upload_document(
        file: UploadFile,
        session_id: UUID | None,
        db: AsyncSession,
        *,
        background_tasks: BackgroundTasks,
    ) -> DocumentUploadResponse:
        upload_dir = Path("./data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_suffix = Path(file.filename).suffix
        storage_name = f"{uuid.uuid4().hex}{file_suffix}"
        storage_path = upload_dir / storage_name
        content = await file.read()
        storage_path.write_bytes(content)
        await file.close()

        document = Document(
            session_id=session_id,
            filename=file.filename,
            content_type=file.content_type,
            storage_path=str(storage_path),
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        # Schedule PDF embedding as a background task
        if file_suffix.lower() == ".pdf":
            background_tasks.add_task(
                _process_pdf_background,
                str(storage_path),
                str(document.id),
            )

        return DocumentUploadResponse(document=document)

    @staticmethod
    async def list_documents(db: AsyncSession) -> list[dict]:
        result = await db.execute(select(Document))
        documents = result.scalars().all()

        return [
            {
                "id": document.id,
                "session_id": document.session_id,
                "filename": document.filename,
                "content_type": document.content_type,
                "storage_path": document.storage_path,
                "uploaded_at": document.uploaded_at.isoformat()
                if document.uploaded_at
                else None,
                "title": document.filename,
                "file_name": document.filename,
                "file_size": Path(document.storage_path).stat().st_size
                if Path(document.storage_path).exists()
                else 0,
            }
            for document in documents
        ]

    @staticmethod
    async def delete_document(document_id: int, db: AsyncSession) -> bool:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            return False

        await db.delete(document)
        await db.commit()
        return True
