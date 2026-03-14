from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils import create_access_token
from app.utils import generate_email_code, hash_password, verify_password
from app.validation import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserCreate, 
    UserLogin,
)


class UserService:
    def __init__(self, db: AsyncSession):
        self.model = User
        self.db = db

    async def create_user(self, user: UserCreate) -> dict | None:
        try:
            # Check existing email
            stmt = select(self.model).where(self.model.email == user.email)
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                return None

            # Insert with RETURNING
            stmt = (
                insert(self.model)
                .values(
                    name=user.name,
                    email=user.email,
                    password=hash_password(user.password),
                    created_at=datetime.now(),
                )
                .returning(
                    self.model.id,
                    self.model.name,
                    self.model.email,
                )
            )

            result = await self.db.execute(stmt)
            await self.db.commit()

            return dict(result.mappings().one())
        except Exception:
            await self.db.rollback()
            return None

    async def login_user(self, data: UserLogin) -> dict | None:
        stmt = select(
            self.model.id, self.model.name, self.model.email, self.model.password
        ).where(self.model.email == data.email)
        result = await self.db.execute(stmt)
        user = result.mappings().one_or_none()

        if not user or not verify_password(data.password, user["password"]):
            return None

        token = create_access_token({"user_id": user["id"], "email": user["email"]})
        user_dict = dict(user)
        del user_dict["password"]
        user_dict["token"] = token

        return user_dict

    async def get_user_by_id(self, user_id: int) -> dict | None:
        stmt = select(self.model.id, self.model.name, self.model.email).where(
            self.model.id == user_id
        )
        result = await self.db.execute(stmt)
        user = result.mappings().one_or_none()
        if not user:
            return None

        return dict(user)

    async def forgot_password(self, data: ForgotPasswordRequest) -> dict | None:
        stmt = select(self.model).where(self.model.email == data.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        code = generate_email_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        stmt = (
            update(self.model)
            .where(self.model.email == data.email)
            .values(reset_code=str(code), reset_code_expires_at=expires_at)
        )
        await self.db.execute(stmt)
        await self.db.commit()

        return {"email": data.email, "code": code}

    async def reset_password(self, data: ResetPasswordRequest) -> str | bool:
        # Check if user exists
        stmt = select(self.model).where(self.model.email == data.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return "We couldn’t find an account with this email"

        # Check reset code
        if not user.reset_code or user.reset_code != str(data.code):
            return "The reset code you entered is incorrect"

        # Check expiry
        if not user.reset_code_expires_at or user.reset_code_expires_at < datetime.now(
            timezone.utc
        ):
            return "This reset code has expired. Please request a new one"

        # Update password
        stmt = (
            update(self.model)
            .where(self.model.email == data.email)
            .values(
                password=hash_password(data.new_password),
                reset_code=None,
                reset_code_expires_at=None,
            )
        )

        await self.db.execute(stmt)
        await self.db.commit()
        return True
