import logging
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.settings import settings
from app.database import get_db

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

security = HTTPBearer()


@dataclass
class CurrentUser:
    id: int
    email: str


def validate_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


async def _fetch_current_user(token: str, db: AsyncSession) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = validate_token(token)
    except JWTError as e:
        logger.error(f"JWT Error: {e}")
        raise credentials_exception

    user_id = payload.get("user_id")
    email = payload.get("email")

    if not user_id or not email:
        raise credentials_exception

    from app.services.user_service import UserService
    user_service = UserService(db)

    user = await user_service.get_user_by_id(user_id)
    if not user:
        logger.error(f"User not found: {user_id}")
        raise credentials_exception

    return CurrentUser(id=user_id, email=email)


async def get_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    token = credentials.credentials
    return await _fetch_current_user(token, db)


def get_current_user(
    current_user: Annotated[CurrentUser, Depends(get_user)],
) -> CurrentUser:
    return current_user
