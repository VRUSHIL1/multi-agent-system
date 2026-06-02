from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import DocumentController
from app.database import get_db
from app.validation import DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])

document_controller = DocumentController()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: int | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    return await document_controller.upload_document_controller(
        file=file,
        session_id=session_id,
        db=db,
        background_tasks=background_tasks,
    )


@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await document_controller.list_documents_controller(db)


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await document_controller.delete_document_controller(document_id, db)
