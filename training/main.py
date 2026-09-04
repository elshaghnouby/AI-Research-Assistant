"""Sales Training Intelligence — application entry point.

Routes fall into four groups:
  /auth/*      registration, login, logout
  /api/events  the tracker's ingest endpoint (staff)
  /api/dashboard  the event log the dashboard reduces (manager)
  /t/{slug}    the 17 decks, proxied same-origin with the tracker injected
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from . import auth as A
from .analytics import dashboard_payload
from .db import get_db, init_db
from .models import Answer, Attempt, Question, Staff, Training, now
from .proxy import router as proxy_router

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Sales Training Intelligence", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.include_router(proxy_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    if os.getenv("SEED_ON_START") == "1":
        _seed_if_empty()


def _seed_if_empty() -> None:
    """First boot on a fresh deployment: create the 17 decks and a manager.

    Only ever runs against an empty database, so a redeploy never overwrites
    real training data. SEED_SAMPLE=1 also loads the demo event log.
    """
    from .db import session
    from .seed import seed_questions, seed_sample, seed_trainings

    db = session()
    try:
        if db.scalar(select(Training.id)):
            return
        trainings = seed_trainings(db)
        layout = seed_questions(db, trainings)
        email = os.getenv("MANAGER_EMAIL", "manager@baroncabot.example")
        password = os.getenv("MANAGER_PASSWORD")
        if password:
            A.create_staff(db, name="Sales Manager", email=email,
                           password=password, office="Head Office", role="manager")
        if os.getenv("SEED_SAMPLE") == "1":
            seed_sample(db, trainings, layout)
    finally:
        db.close()


# --------------------------------------------------------------------------- auth
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    office: str = Field(default="", max_length=60)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@app.post("/auth/register")
def register(body: RegisterIn, response: Response, db: DbSession = Depends(get_db)):
    staff = A.create_staff(db, name=body.name, email=body.email,
                           password=body.password, office=body.office)
    A.start_session(db, staff, response)
    return {"id": staff.id, "name": staff.name, "role": staff.role}


@app.post("/auth/login")
def login(body: LoginIn, response: Response, db: DbSession = Depends(get_db)):
    staff = db.scalar(select(Staff).where(Staff.email == body.email.strip().lower()))
    if not staff or not staff.active or not A.verify_password(
            body.password, staff.pw_hash, staff.pw_salt):
        raise HTTPException(401, "Email or password is incorrect.")
    A.start_session(db, staff, response)
    return {"id": staff.id, "name": staff.name, "role": staff.role}


@app.post("/auth/logout")
def logout(response: Response, stid: str | None = None,
           request: Request = None, db: DbSession = Depends(get_db)):
    A.end_session(db, request.cookies.get(A.COOKIE), response)
    return {"ok": True}


@app.get("/api/me")
def me(staff: Staff | None = Depends(A.current_staff)):
    if not staff:
        return JSONResponse({"signedIn": False}, status_code=200)
    return {"signedIn": True, "id": staff.id, "name": staff.name,
            "role": staff.role, "office": staff.office}


# ------------------------------------------------------------------------ ingest
class EventIn(BaseModel):
    q: int = Field(ge=0, le=500)
    chosen: int = Field(ge=0, le=50)
    correct: bool
    ms: int = Field(default=0, ge=0, le=3_600_000)


class EventsIn(BaseModel):
    deck: str
    elapsed_ms: int = Field(default=0, ge=0)
    final: bool = False
    events: list[EventIn] = Field(default_factory=list, max_length=200)


def _open_attempt(db: DbSession, staff_id: str, training_id: str) -> Attempt:
    attempt = db.scalar(
        select(Attempt)
        .where(Attempt.staff_id == staff_id, Attempt.training_id == training_id)
        .order_by(Attempt.seq.desc())
    )
    if attempt is None:
        attempt = Attempt(staff_id=staff_id, training_id=training_id, seq=1)
        db.add(attempt)
        db.flush()
    return attempt


def _expected_questions(db: DbSession, training_id: str) -> int | None:
    """How many questions the deck has, if we know.

    Prefer our tagged Question rows. Failing that, infer from the highest slot
    anyone has answered — which is a floor, not a count, so it only ever marks a
    deck complete once someone has reached the end of it.
    """
    tagged = db.scalar(select(func.count(Question.id))
                       .where(Question.training_id == training_id))
    if tagged:
        return int(tagged)
    highest = db.scalar(select(func.max(Answer.q_index))
                        .where(Answer.training_id == training_id))
    return None if highest is None else int(highest) + 1


@app.post("/api/events")
def ingest(body: EventsIn, staff: Staff = Depends(A.require_staff),
           db: DbSession = Depends(get_db)):
    training = db.scalar(select(Training).where(Training.slug == body.deck))
    if not training:
        raise HTTPException(404, "Unknown training deck.")

    attempt = _open_attempt(db, staff.id, training.id)
    attempt.last_seen_at = now()
    attempt.duration_ms = max(attempt.duration_ms, body.elapsed_ms)

    written = 0
    for ev in body.events:
        existing = db.scalar(
            select(Answer).where(Answer.attempt_id == attempt.id,
                                 Answer.q_index == ev.q))
        if existing:                       # idempotent: a replayed beacon updates
            existing.chosen = ev.chosen
            existing.is_correct = ev.correct
            existing.ms = ev.ms or existing.ms
            continue
        db.add(Answer(
            attempt_id=attempt.id, staff_id=staff.id, training_id=training.id,
            q_index=ev.q, chosen=ev.chosen, is_correct=ev.correct, ms=ev.ms,
        ))
        written += 1
    db.flush()

    answered = db.scalar(select(func.count(Answer.id))
                         .where(Answer.attempt_id == attempt.id)) or 0
    expected = _expected_questions(db, training.id)
    if expected and answered >= expected and attempt.completed_at is None:
        attempt.completed_at = now()

    db.commit()
    return {"ok": True, "recorded": written, "answered": answered,
            "expected": expected, "complete": attempt.completed_at is not None}


# --------------------------------------------------------------------- dashboard
@app.get("/api/dashboard")
def dashboard_data(staff: Staff = Depends(A.require_manager),
                   db: DbSession = Depends(get_db)):
    return dashboard_payload(db)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(staff: Staff | None = Depends(A.current_staff)):
    if not staff:
        return RedirectResponse("/login?next=/dashboard", status_code=303)
    if staff.role != "manager":
        return RedirectResponse("/", status_code=303)
    return FileResponse(STATIC / "dashboard.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)   # browsers always ask; don't log a 404 for it


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return FileResponse(STATIC / "login.html")


@app.get("/", response_class=HTMLResponse)
def home(staff: Staff | None = Depends(A.current_staff),
         db: DbSession = Depends(get_db)):
    if not staff:
        return RedirectResponse("/login", status_code=303)
    if staff.role == "manager":
        return RedirectResponse("/dashboard", status_code=303)
    return FileResponse(STATIC / "trainings.html")


@app.get("/api/trainings")
def my_trainings(staff: Staff = Depends(A.require_staff),
                 db: DbSession = Depends(get_db)):
    """The staff-facing list: the 17 decks and where this person stands."""
    rows = []
    for t in db.scalars(select(Training).order_by(Training.position)):
        attempt = db.scalar(
            select(Attempt).where(Attempt.staff_id == staff.id,
                                  Attempt.training_id == t.id))
        answered = db.scalar(select(func.count(Answer.id)).where(
            Answer.staff_id == staff.id, Answer.training_id == t.id)) or 0
        rows.append({
            "id": t.id, "slug": t.slug, "title": t.title, "sub": t.sub,
            "cat": t.category, "href": f"/t/{t.slug}",
            "status": ("complete" if attempt and attempt.completed_at
                       else "started" if attempt else "not_started"),
            "answered": answered,
        })
    return {"staff": {"id": staff.id, "name": staff.name}, "trainings": rows}
