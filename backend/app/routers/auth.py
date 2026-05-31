from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(body: UserCreate, db: Session = Depends(get_db)) -> User:
    user = User(
        email=body.email.strip().lower(),
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        ) from e
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(
        subject=user.email, user_id=user.id, role=user.role
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> User:
    return current
