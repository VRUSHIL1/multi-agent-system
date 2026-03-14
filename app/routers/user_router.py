from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import (
    forgot_password_controller,
    get_user_controller,
    login_user_controller,
    register_user_controller,
    reset_password_controller,
)
from app.database import get_db
from app.utils import CurrentUser, get_current_user
from app.validation import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserLogin,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post("/register")
async def register_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await register_user_controller(data, db)


@router.post("/login")
async def login_user(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await login_user_controller(data, db)


@router.get("/get")
async def get_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await get_user_controller(current_user.id, db)


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await forgot_password_controller(data, db, background_tasks)


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    return await reset_password_controller(data, db)
