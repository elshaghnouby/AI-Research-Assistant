"""Read the 17 decks and report how they are built.

    python -m training.inspect_decks              # fetch all 17, print a report
    python -m training.inspect_decks --save       # also keep the raw HTML
    python -m training.inspect_decks --only dubai-training-deck-1

Nothing here writes to a deck. It issues plain GET requests and reads the HTML.

The report answers the questions the tracker needs settled:
  · are the questions in the markup, or in a script, or fetched at runtime?
  · what marks an option as chosen, and as right or wrong?
  · do the 17 share one template, so one adapter covers them all?
  · does anything already get sent to a server?

Send the printed summary (or deck-report.json) back and the adapter can be
written against it. The saved HTML is only needed if the summary is ambiguous.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import httpx

from .seed import DECKS, HOST

OUT = Path("deck_dumps")

SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
SRC_RE = re.compile(r'<script\b[^>]+src=["\']([^"\']+)["\']', re.I)
TAG_RE = re.compile(r"<([a-zA-Z][\w-]*)")
CLASS_RE = re.compile(r'class=["\']([^"\']+)["\']')
DATA_RE = re.compile(r"\b(data-[a-z0-9-]+)\s*=")

# Words that suggest a quiz, and words that suggest a verdict being rendered.
QUIZ_WORDS = ("question", "answer", "correct", "incorrect", "option", "choice",
              "quiz", "score", "explanation", "wrong")
SEND_RE = re.compile(
    r"(fetch\s*\(|XMLHttpRequest|sendBeacon|axios\.|\$\.(?:post|ajax)|"
    r"gtag\s*\(|dataLayer|firebase|supabase)", re.I)
URLISH_RE = re.compile(r'["\'](https?://[^"\']{6,120}|/api/[^"\']{1,80})["\']')


def fingerprint(html: str) -> str:
    """A structural hash: tag sequence only, so copy differences do not matter."""
    tags = TAG_RE.findall(html.lower())[:400]
    return hashlib.sha1(" ".join(tags).encode()).hexdigest()[:12]


def interesting_classes(html: str) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for chunk in CLASS_RE.findall(html):
        for cls in chunk.split():
            low = cls.lower()
            if any(w in low for w in QUIZ_WORDS):
                counts[cls] += 1
    return counts.most_common(14)


def inline_js(html: str) -> str:
    return "\n".join(SCRIPT_RE.findall(html))


def examine(slug: str, title: str, html: str) -> dict:
    js = inline_js(html)
    low = html.lower()
    data_attrs = Counter(DATA_RE.findall(html))
    quiz_data = sorted({a for a in data_attrs if any(w in a for w in QUIZ_WORDS)})

    sends = sorted(set(m.group(0) for m in SEND_RE.finditer(js)))
    urls = sorted({u for u in URLISH_RE.findall(js)
                   if not u.startswith(("https://fonts.", "https://www.w3.org"))})[:12]

    # Does the page appear to carry the questions itself?
    inline_questions = bool(re.search(r'["\']?(questions|quiz|items)["\']?\s*[:=]\s*\[', js, re.I))
    correct_in_source = bool(re.search(r'\b(correct|answer)(Index|_index|Idx)?\s*[:=]', js, re.I)) \
        or "data-correct" in low

    counts = {w: low.count(w) for w in QUIZ_WORDS if low.count(w)}

    return {
        "slug": slug,
        "title": title,
        "bytes": len(html),
        "fingerprint": fingerprint(html),
        "external_scripts": SRC_RE.findall(html)[:10],
        "looks_like_quiz": bool(counts.get("question") or counts.get("answer")),
        "questions_inline_in_js": inline_questions,
        "correct_answer_in_source": correct_in_source,
        "quiz_data_attributes": quiz_data,
        "quiz_class_names": interesting_classes(html),
        "word_counts": counts,
        "sends_data": sends,
        "endpoints_seen": urls,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", action="store_true", help=f"write raw HTML into {OUT}/")
    ap.add_argument("--only", default="", help="inspect one slug")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    decks = [(s, t) for s, t, _sub, _cat in DECKS if not args.only or args.only in s]
    if not decks:
        print(f"No deck matches {args.only!r}.")
        return 1
    if args.save:
        OUT.mkdir(exist_ok=True)

    reports, failures = [], []
    with httpx.Client(follow_redirects=True, timeout=args.timeout,
                      headers={"user-agent": "Mozilla/5.0 (deck-inspector)"}) as client:
        for i, (slug, title) in enumerate(decks, 1):
            url = f"https://{slug}-{HOST}/"
            print(f"[{i:>2}/{len(decks)}] {title:<24} ", end="", flush=True)
            try:
                res = client.get(url)
                res.raise_for_status()
            except Exception as exc:                       # noqa: BLE001 — report, don't crash
                print(f"FAILED — {type(exc).__name__}: {exc}")
                failures.append({"slug": slug, "error": f"{type(exc).__name__}: {exc}"})
                continue
            html = res.text
            if args.save:
                (OUT / f"{slug}.html").write_text(html, encoding="utf-8")
            rep = examine(slug, title, html)
            reports.append(rep)
            print(f"{rep['bytes']:>7,} bytes  "
                  f"{'quiz' if rep['looks_like_quiz'] else 'no quiz markers'}"
                  f"{'  · sends data' if rep['sends_data'] else ''}")

    if not reports:
        print("\nNothing could be read. Check the URLs and your connection.")
        return 1

    groups = Counter(r["fingerprint"] for r in reports)
    print("\n" + "=" * 68)
    print(f"READ {len(reports)} of {len(decks)} decks")
    if failures:
        print(f"  {len(failures)} failed: " + ", ".join(f['slug'] for f in failures))

    print(f"\nTEMPLATE  {len(groups)} distinct structure(s) across {len(reports)} decks")
    for fp, n in groups.most_common():
        members = [r["slug"] for r in reports if r["fingerprint"] == fp]
        print(f"  {fp}  ×{n}  e.g. {members[0]}")
    print("  → one adapter covers each group." if len(groups) <= 3 else
          "  → decks differ; expect per-deck adapters.")

    print("\nQUIZ DATA")
    print(f"  questions inline in JS   {sum(r['questions_inline_in_js'] for r in reports)}/{len(reports)}")
    print(f"  correct answer in source {sum(r['correct_answer_in_source'] for r in reports)}/{len(reports)}")

    attrs = Counter(a for r in reports for a in r["quiz_data_attributes"])
    print("  data attributes          " + (", ".join(f"{a}×{n}" for a, n in attrs.most_common(10)) or "none"))
    classes = Counter()
    for r in reports:
        for cls, n in r["quiz_class_names"]:
            classes[cls] += n
    print("  class names              " + (", ".join(f"{c}×{n}" for c, n in classes.most_common(12)) or "none"))

    senders = [r for r in reports if r["sends_data"]]
    print(f"\nALREADY SENDING ANYWHERE?  {len(senders)}/{len(reports)} decks")
    for r in senders[:5]:
        print(f"  {r['slug']}: {', '.join(r['sends_data'])}")
        for u in r["endpoints_seen"][:4]:
            print(f"      → {u}")
    if not senders:
        print("  No deck sends results anywhere. The tracker is required.")

    Path("deck-report.json").write_text(
        json.dumps({"decks": reports, "failures": failures}, indent=2), encoding="utf-8")
    print("\nWrote deck-report.json — send that back.")
    if args.save:
        print(f"Raw HTML in {OUT}/ (gitignored) — only needed if the summary is unclear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
