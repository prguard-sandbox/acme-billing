"""API-key authentication. Only SHA-256 hashes of keys are stored."""

import hashlib
import secrets
import sys

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db, init_db
from app.models import User


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_user(db: Session, email: str) -> tuple[User, str]:
    """Creates a user and returns it with its raw API key.

    The raw key cannot be recovered later, so the caller has to show it once.
    """
    raw_key = f"abk_{secrets.token_urlsafe(32)}"
    user = User(email=email, api_key_hash=hash_api_key(raw_key))
    db.add(user)
    db.commit()
    return user, raw_key


def get_current_user(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    user = db.scalar(select(User).where(User.api_key_hash == hash_api_key(x_api_key)))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return user


if __name__ == "__main__":
    # python -m app.auth you@example.com
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.auth <email>")
    init_db()
    with SessionLocal() as session:
        _, api_key = create_user(session, sys.argv[1])
    sys.stdout.write(f"{api_key}\n")
