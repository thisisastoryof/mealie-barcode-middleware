import secrets

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApiToken


def hash_token(raw_token: str) -> str:
    return bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()


def verify_token(raw_token: str, token_hash: str) -> bool:
    return bcrypt.checkpw(raw_token.encode(), token_hash.encode())


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def require_token(request: Request, db: Session = Depends(get_db)) -> ApiToken:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    raw_token = auth_header.removeprefix("Bearer ").strip()
    tokens = db.query(ApiToken).all()
    for t in tokens:
        if verify_token(raw_token, t.token_hash):
            return t
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
    )
