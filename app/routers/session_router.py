from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import SessionController
from app.database import get_db
from app.utils import CurrentUser, get_current_user
from app.validation import SessionCreate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_session_controller(
    payload: SessionCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await SessionController(db).create_session(payload, user)


@router.get("/")
async def list_sessions(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await SessionController(db).list_sessions(user)


@router.get("/{session_id}")
async def get_session(
    session_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await SessionController(db).get_session(session_id, user)


@router.delete("/{session_id}")
async def delete_session(
    session_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await SessionController(db).delete_session(session_id, user)


@router.get("/history/{session_id}")
async def get_session_history(
    session_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await SessionController(db).get_session_history(user.id, session_id, db)


@router.get("/user/{user_id}")
async def get_all_sessions(
    user_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await SessionController(db).get_all_sessions(
        user, page, limit, search, user_id
    )
