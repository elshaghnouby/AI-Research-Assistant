"""Same-origin reverse proxy for the 17 decks.

Why a proxy rather than editing the decks: the tracker has to run on our origin
to send an authenticated request, and a cross-origin iframe cannot see the
clicks inside it. Proxying gets both without redeploying a single Cloud Run
service — the deck source stays byte-identical.

Two things are added to the HTML on the way through, and nothing is removed:
  1. <base href="https://<deck-host>/"> so the deck's own CSS, JS and images
     still load straight from Cloud Run.
  2. our tracker <script>, last thing before </body>.

The proxy only serves slugs that exist in the trainings table, so this cannot be
turned into an open forwarder.
"""
from __future__ import annotations

import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .auth import Staff, require_staff
from .db import get_db
from .models import Training

router = APIRouter()

HOP_BY_HOP = {
    "content-encoding", "content-length", "transfer-encoding", "connection",
    "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
    "upgrade",
}
BASE_RE = re.compile(rb"<base\b", re.I)
HEAD_RE = re.compile(rb"<head[^>]*>", re.I)
BODY_END_RE = re.compile(rb"</body\s*>", re.I)


def _training(db: DbSession, slug: str) -> Training:
    t = db.scalar(select(Training).where(Training.slug == slug))
    if not t:
        raise HTTPException(404, "Unknown training.")
    return t


def inject(html: bytes, origin: str, slug: str, staff_id: str) -> bytes:
    """Add a <base> and the tracker. Never rewrite the deck's own markup."""
    if not BASE_RE.search(html):
        base = f'<base href="{origin}/">'.encode()
        m = HEAD_RE.search(html)
        html = html[:m.end()] + base + html[m.end():] if m else base + html

    tag = (
        f'<script src="/static/tracker.js" data-deck="{slug}" '
        f'data-staff="{staff_id}" data-endpoint="/api/events" defer></script>'
    ).encode()
    m = BODY_END_RE.search(html)
    return html[:m.start()] + tag + html[m.start():] if m else html + tag


@router.get("/t/{slug}")
@router.get("/t/{slug}/{path:path}")
async def serve_deck(
    slug: str,
    request: Request,
    path: str = "",
    staff: Staff = Depends(require_staff),
    db: DbSession = Depends(get_db),
):
    training = _training(db, slug)
    origin = training.url.rstrip("/")
    target = f"{origin}/{path}" if path else f"{origin}/"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            upstream = await client.get(
                target,
                params=dict(request.query_params),
                headers={"user-agent": request.headers.get("user-agent", "")},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Could not reach the training deck: {exc}") from exc

    ctype = upstream.headers.get("content-type", "")
    headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "content-security-policy"
    }

    if "text/html" in ctype:
        body = inject(upstream.content, origin, slug, staff.id)
        return HTMLResponse(body, status_code=upstream.status_code,
                            headers={k: v for k, v in headers.items()
                                     if k.lower() != "content-type"})
    return Response(upstream.content, status_code=upstream.status_code,
                    media_type=ctype or None, headers=headers)
