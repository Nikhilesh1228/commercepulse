from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Principal, hash_password, verify_password
from app.models.commerce import User
from app.schemas.auth import RegisterRequest


def register(db: Session, payload: RegisterRequest) -> User:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        roles=["shopper"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if (
        user is None
        or user.password_hash is None
        or not verify_password(password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def as_principal(user: User) -> Principal:
    return Principal(user_id=user.id, email=user.email, roles=user.roles)


def upsert_oidc_user(
    db: Session, *, provider: str, subject: str, email: str, display_name: str
) -> User:
    user = db.scalar(
        select(User).where(User.oidc_provider == provider, User.oidc_subject == subject)
    )
    if user is None:
        user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        user = User(
            email=email.lower(),
            display_name=display_name,
            roles=["shopper"],
            oidc_provider=provider,
            oidc_subject=subject,
        )
        db.add(user)
    else:
        user.oidc_provider = provider
        user.oidc_subject = subject
    db.commit()
    db.refresh(user)
    return user
