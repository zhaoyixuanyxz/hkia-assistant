from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_token

security = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        return None
    uid = payload.get("uid")
    try:
        uid_int = int(uid)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return db.get(User, uid_int)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from None
    uid = payload.get("uid")
    try:
        uid_int = int(uid)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, uid_int)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
