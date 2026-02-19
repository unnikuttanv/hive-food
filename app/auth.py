from __future__ import annotations
import bcrypt
from itsdangerous import URLSafeSerializer, BadSignature
from fastapi import Request, Response
from .config import SECRET_KEY

serializer = URLSafeSerializer(SECRET_KEY, salt="session")

COOKIE_NAME = "hive_food_session"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def set_login_cookie(response: Response, user_id: int) -> None:
    token = serializer.dumps({"user_id": user_id})
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=False,  # set True behind HTTPS
        max_age=60 * 60 * 24 * 14,  # 14 days
    )

def clear_login_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)

def get_user_id_from_request(request: Request) -> int | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = serializer.loads(token)
        return int(data.get("user_id"))
    except (BadSignature, Exception):
        return None
