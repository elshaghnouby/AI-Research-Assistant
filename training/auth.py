"""Registration, login and role checks.

Password hashing uses hashlib.scrypt from the standard library — no extra
dependency, and the parameters below are the interactive-login defaults.
Sessions are opaque random tokens stored server-side, so signing out is a delete
rather than a hope that a signed cookie expires.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets

from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .db import get_db
from .models import Session, Staff, now

COOKIE = "stid"
SESSION_DAYS = 14
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=_N, r=_R, p=_P, dklen=32
    )
    return digest.hex(), salt


def verify_password(password: str, pw_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, pw_hash)


def next_staff_id(db: DbSession) -> str:
    n = db.query(Staff).count() + 1
    while db.get(Staff, f"s{n:02d}"):
        n += 1
    return f"s{n:02d}"


def create_staff(db: DbSession, *, name: str, email: str, password: str,
                 office: str = "", role: str = "staff", is_sample: bool = False) -> Staff:
    email = email.strip().lower()
    if db.scalar(select(Staff).where(Staff.email == email)):
        raise HTTPException(409, "That email is already registered.")
    pw_hash, salt = hash_password(password)
    staff = Staff(
        id=next_staff_id(db), name=name.strip(), email=email, office=office,
        role=role, pw_hash=pw_hash, pw_salt=salt, is_sample=is_sample,
    )
    db.add(staff)
    db.commit()
    return staff


def start_session(db: DbSession, staff: Staff, response: Response) -> str:
    token = secrets.token_urlsafe(32)
    db.add(Session(
        token=token, staff_id=staff.id,
        expires_at=now() + dt.timedelta(days=SESSION_DAYS),
    ))
    db.commit()
    response.set_cookie(
        COOKIE, token, max_age=SESSION_DAYS * 86400,
        httponly=True, samesite="lax", secure=False, path="/",
    )
    return token


def end_session(db: DbSession, token: str | None, response: Response) -> None:
    if token:
        row = db.get(Session, token)
        if row:
            db.delete(row)
            db.commit()
    response.delete_cookie(COOKIE, path="/")


def current_staff(stid: str | None = Cookie(default=None),
                  db: DbSession = Depends(get_db)) -> Staff | None:
    """Resolve the signed-in user, or None. Never raises — routes decide."""
    if not stid:
        return None
    row = db.get(Session, stid)
    if not row:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=dt.timezone.utc)
    if expires < now():
        db.delete(row)
        db.commit()
        return None
    staff = db.get(Staff, row.staff_id)
    return staff if staff and staff.active else None


def require_staff(staff: Staff | None = Depends(current_staff)) -> Staff:
    if not staff:
        raise HTTPException(401, "Sign in to continue.")
    return staff


def require_manager(staff: Staff = Depends(require_staff)) -> Staff:
    if staff.role != "manager":
        raise HTTPException(403, "This page is for managers.")
    return staff
