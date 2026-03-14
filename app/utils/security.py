import secrets
import string

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify((password), hashed)


def generate_email_code() -> str:
    """
    Generate a secure 6-digit numeric OTP
    Example: 483920
    """
    return "".join(secrets.choice(string.digits) for _ in range(6))
