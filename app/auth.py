import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserRole

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer()
AUTH_SECRET = os.environ["AUTH_SECRET"]
ALGORITHM = "HS256"
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@helpdesk-demo.com").lower()
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMe123!")


def ensure_default_specialist(db: Session) -> None:
    email = os.environ["SPECIALIST_EMAIL"].lower()
    if db.scalar(select(User).where(User.email == email)) is None:
        db.add(User(email=email, password_hash=password_hash.hash(os.environ["SPECIALIST_PASSWORD"]), role=UserRole.specialist))
        db.commit()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user and password_hash.verify(password, user.password_hash):
        return user
    return None


def register_employee(db: Session, email: str, password: str, full_name: str) -> User | None:
    if db.scalar(select(User).where(User.email == email.lower())) is not None:
        return None
    user = User(email=email.lower(), password_hash=password_hash.hash(password), role=UserRole.employee, full_name=full_name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def initialize_system_admin(db: Session, email: str, password: str, full_name: str) -> User | None:
    if db.scalar(select(User).where(User.role == UserRole.system_admin)) is not None:
        return None
    user = User(email=email.lower(), password_hash=password_hash.hash(password), role=UserRole.system_admin, full_name=full_name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_bootstrap_system_admin(db: Session) -> User | None:
    """Create the one-time local administrator only on a completely new installation."""
    existing = db.scalar(select(User).where(User.role == UserRole.system_admin))
    if existing is not None:
        return None
    user = User(
        email=BOOTSTRAP_ADMIN_EMAIL,
        password_hash=password_hash.hash(BOOTSTRAP_ADMIN_PASSWORD),
        role=UserRole.system_admin,
        full_name="",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def is_bootstrap_system_admin(user: User) -> bool:
    return user.role == UserRole.system_admin and user.email == BOOTSTRAP_ADMIN_EMAIL


def activate_system_admin(db: Session, user: User, email: str, password: str, full_name: str) -> User:
    if not is_bootstrap_system_admin(user):
        raise ValueError("Системный администратор уже активирован")
    normalized_email = email.lower()
    duplicate = db.scalar(select(User).where(User.email == normalized_email, User.id != user.id))
    if duplicate is not None:
        raise ValueError("Аккаунт с такой почтой уже существует")
    user.email = normalized_email
    user.password_hash = password_hash.hash(password)
    user.full_name = full_name.strip()
    db.commit()
    db.refresh(user)
    return user


def create_access_token(email: str, role: UserRole) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(hours=8)
    return jwt.encode({"sub": email, "role": role, "exp": expiry}, AUTH_SECRET, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(credentials.credentials, AUTH_SECRET, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except jwt.PyJWTError:
        email = None
    user = db.scalar(select(User).where(User.email == email)) if email else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нужно войти в аккаунт")
    return user


def get_current_specialist(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(credentials.credentials, AUTH_SECRET, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except jwt.PyJWTError:
        email = None
    user = db.scalar(select(User).where(User.email == email)) if email else None
    if user is None or user.role != UserRole.specialist:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нужен вход специалиста")
    return user


def get_current_it_operator(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Allow diagnostic actions for a support specialist or system owner."""
    try:
        payload = jwt.decode(credentials.credentials, AUTH_SECRET, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except jwt.PyJWTError:
        email = None
    user = db.scalar(select(User).where(User.email == email)) if email else None
    if user is None or user.role not in {UserRole.specialist, UserRole.system_admin}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нужен вход IT-специалиста или системного владельца")
    return user


def get_current_system_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(credentials.credentials, AUTH_SECRET, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except jwt.PyJWTError:
        email = None
    user = db.scalar(select(User).where(User.email == email)) if email else None
    if user is None or user.role != UserRole.system_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нужны права системного владельца")
    return user
