"""Database schema.

Grain matters here: one row in `answers` per question a rep actually answered.
That row is the tracker payload, and every dashboard figure is derived from it —
nothing is stored pre-aggregated, so a corrected event corrects every number.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    office: Mapped[str] = mapped_column(String(60), default="")
    role: Mapped[str] = mapped_column(String(16), default="staff")  # staff | manager
    pw_hash: Mapped[str] = mapped_column(String(160))
    pw_salt: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)

    attempts: Mapped[list["Attempt"]] = relationship(back_populates="staff")


class Training(Base):
    """One of the 17 live decks. We record *about* them; we never modify them."""

    __tablename__ = "trainings"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    sub: Mapped[str] = mapped_column(String(60), default="")
    category: Mapped[str] = mapped_column(String(32), default="Training")
    url: Mapped[str] = mapped_column(String(400))
    position: Mapped[int] = mapped_column(Integer, default=0)

    questions: Mapped[list["Question"]] = relationship(back_populates="training")


class Question(Base):
    """A question inside a deck, addressed by its index within that deck.

    `skill` is OUR tagging — it lives here, never in the deck. `text`, `options`
    and `correct_index` are filled in once the deck source has been read; the
    dashboard works without them (it falls back to the index) but the question
    panel is far more useful with them.
    """

    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("training_id", "q_index", name="uq_question_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True)
    q_index: Mapped[int] = mapped_column(Integer)
    ref: Mapped[str] = mapped_column(String(24), default="")     # shared id across decks, e.g. "Q12"
    skill: Mapped[str] = mapped_column(String(32), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    options: Mapped[str] = mapped_column(Text, default="[]")     # JSON array of option labels
    correct_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    training: Mapped[Training] = relationship(back_populates="questions")


class Attempt(Base):
    """One staff member opening one deck. Completion is derived, not asserted."""

    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("staff_id", "training_id", "seq", name="uq_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id"), index=True)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=1)          # retakes get seq 2, 3, ...
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)

    staff: Mapped[Staff] = relationship(back_populates="attempts")
    answers: Mapped[list["Answer"]] = relationship(back_populates="attempt")


class Answer(Base):
    """The tracker payload, one row per answered question.

    Unique on (attempt, question slot) so a retried or duplicated beacon
    overwrites rather than double-counts.
    """

    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "q_index", name="uq_answer_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), index=True)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id"), index=True)
    training_id: Mapped[str] = mapped_column(ForeignKey("trainings.id"), index=True)
    q_index: Mapped[int] = mapped_column(Integer)
    chosen: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    ms: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
