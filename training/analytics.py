"""The dashboard payload.

This returns the event log itself, not pre-computed figures. The front-end holds
the aggregation, so the same arithmetic that ran over seeded events in the
prototype now runs over database rows — swapping the source, not the maths.

At 20 staff x 17 decks that is a few thousand rows, which is small. When the log
outgrows the browser, move the reduce() calls in dashboard.html into SQL here;
the payload shape is the contract, and it need not change.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .models import Answer, Attempt, Question, Staff, Training, now

# Our skill vocabulary. Questions are tagged here, never inside a deck.
SKILLS = {
    "obj": "Objection Handling",
    "close": "Closing",
    "price": "Pricing & Payment Plans",
    "qual": "Qualification",
    "fu": "Follow-up",
    "pk": "Product Knowledge",
    "comp": "Compliance",
}

THRESHOLDS = {"good": 80, "warn": 60, "minN": 5}


def _ms(value) -> int:
    return int(value.timestamp() * 1000) if value else 0


def question_map(db: DbSession) -> dict[tuple[str, int], Question]:
    return {(q.training_id, q.q_index): q for q in db.scalars(select(Question))}


def ref_for(qmap, training_id: str, q_index: int) -> str:
    """A question's shared identity across decks.

    Once a deck has been read and its questions tagged, several decks can point
    at the same underlying question via `ref`. Until then each slot is its own
    question, named by deck and position.
    """
    q = qmap.get((training_id, q_index))
    if q and q.ref:
        return q.ref
    return f"{training_id}#{q_index}"


def dashboard_payload(db: DbSession) -> dict:
    qmap = question_map(db)

    staff = [
        {"id": s.id, "name": s.name, "office": s.office, "role": s.role}
        for s in db.scalars(select(Staff).where(Staff.active).order_by(Staff.id))
        if s.role != "manager"
    ]
    trainings = [
        {
            "id": t.id, "slug": t.slug, "title": t.title,
            "sub": t.sub, "cat": t.category, "url": t.url,
        }
        for t in db.scalars(select(Training).order_by(Training.position))
    ]

    attempts = [
        {
            "staff": a.staff_id, "training": a.training_id,
            "complete": a.completed_at is not None,
            "startedAt": _ms(a.started_at), "ms": a.duration_ms,
        }
        for a in db.scalars(select(Attempt))
    ]

    answers = []
    for a in db.scalars(select(Answer)):
        answers.append({
            "staff": a.staff_id, "training": a.training_id,
            "q": ref_for(qmap, a.training_id, a.q_index),
            "idx": a.q_index, "chosen": a.chosen, "ok": a.is_correct, "ms": a.ms,
        })

    # One entry per distinct question ref, carrying whatever we know about it.
    questions: dict[str, dict] = {}
    for (tid, idx), q in qmap.items():
        ref = q.ref or f"{tid}#{idx}"
        entry = questions.setdefault(ref, {
            "ref": ref, "skill": q.skill, "text": q.text,
            "options": json.loads(q.options or "[]"),
            "correct": q.correct_index, "trainings": [],
        })
        entry["trainings"].append(tid)
    # Slots that have answers but no tagging yet still need to appear.
    for a in answers:
        if a["q"] not in questions:
            questions[a["q"]] = {
                "ref": a["q"], "skill": "", "text": "", "options": [],
                "correct": None, "trainings": [a["training"]], "untagged": True,
            }

    sample = bool(db.scalar(select(Answer.id).where(Answer.is_sample).limit(1)))

    return {
        "meta": {
            "sample": sample,
            "generatedAt": _ms(now()),
            "thresholds": THRESHOLDS,
            "skills": SKILLS,
            "staffCount": len(staff),
            "trainingCount": len(trainings),
        },
        "staff": staff,
        "trainings": trainings,
        "questions": list(questions.values()),
        "attempts": attempts,
        "answers": answers,
    }
