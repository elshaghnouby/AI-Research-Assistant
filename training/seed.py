"""Seed the database.

    python -m training.seed              # the 17 decks + a manager account
    python -m training.seed --sample     # ...plus 20 staff and a synthetic event log

The 17 trainings are REAL: their slugs and URLs are the live decks, and nothing
here ever writes to them. Everything created under --sample is flagged
is_sample=True, which is what keeps the "Sample data" badge on the dashboard
until real events arrive.

Passwords are never hard-coded. Set SEED_PASSWORD, or one is generated and
printed once.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import sys

from sqlalchemy import delete, select

from .auth import create_staff, hash_password
from .db import init_db, session
from .models import Answer, Attempt, Question, Session, Staff, Training

HOST = "2kezckbdvq-ew.a.run.app"

# (slug, title, sub, category) — the 17 live decks, in reading order.
DECKS = [
    ("baron-cabot-managers-handbook-2", "Managers Handbook", "Baron Cabot", "Handbook"),
    ("london-zones1-3-training-deck-7", "London Zones 1–3", "Territory", "Training"),
    ("london-zones4-6-training-deck-2", "London Zones 4–6", "Territory", "Training"),
    ("manchester-training-deck", "Manchester", "Territory", "Training"),
    ("birmingham-training-deck-1", "Birmingham", "Territory", "Training"),
    ("leicester-training-deck-1", "Leicester", "Territory", "Training"),
    ("liverpool-training-deck", "Liverpool", "Territory", "Training"),
    ("dubai-training-deck-1", "Dubai", "Territory", "Training"),
    ("phuket-training-deck", "Phuket", "Territory", "Training"),
    ("the-hilight-sales-slides-3", "The Hilight", "Development", "Sales"),
    ("paper-yard-sales-slides", "Paper Yard", "Development", "Sales"),
    ("waterhouse-gardens-sales-slides", "Waterhouse Gardens", "Development", "Sales"),
    ("furness-quay-sales-slides", "Furness Quay", "Development", "Sales"),
    ("vivere-sales-slides", "Vivere", "Development", "Sales"),
    ("velocity-sales-slides", "Velocity", "Development", "Sales"),
    ("viadux-penthouses-sales-slides-1", "Viadux Penthouses", "Development", "Sales"),
    ("w-residences-sales-slides", "W Residences", "Development", "Sales"),
]

# Placeholder question bank for the sample log. Real questions and their correct
# answers live inside the decks; these rows exist so the prototype's question
# panel has something to show before the decks have been read and tagged.
BANK = [
    ("Q01", "obj", .52, "A client says the service charge is higher than at a competing development. What is the strongest first response?",
     ["Offer a discount on the purchase price", "Ask what they are comparing it to, then break down what the charge covers", "Explain that every development has a service charge", "Move them on to a different unit"], 1),
    ("Q02", "obj", .61, '"I want to think about it." What does this objection most often actually mean?',
     ["The client is not interested", "A concern has not been surfaced yet", "The price is too high", "They need to speak to a partner"], 1),
    ("Q03", "obj", .44, "A buyer objects that the completion date is too far out. Which response builds the most value?",
     ["Agree that it is a long wait", "Offer an alternative development", "Frame the build period against the payment plan and the price held to completion", "Ask them to reserve anyway"], 2),
    ("Q04", "close", .70, "Which of these is a legitimate assumptive close?",
     ['"Shall I hold Apartment 402 for you on a 48-hour reservation?"', '"This is the last one at this price."', '"Do you want to buy it?"', '"Let me know when you decide."'], 0),
    ("Q05", "close", .58, "When should you first attempt a trial close?",
     ["Only after the full presentation", "As soon as the client gives a buying signal", "At the very start of the meeting", "Only on a second viewing"], 1),
    ("Q06", "close", .49, "A client is ready but hesitates at the reservation fee. Best action?",
     ["Waive the fee", "Restate what the fee secures and how it is treated under the reservation terms", "End the meeting and follow up next week", "Escalate to the sales manager immediately"], 1),
    ("Q07", "pk", .93, 'What does "off-plan" mean?',
     ["A property sold without floor plans", "A property purchased before construction is complete", "A property outside the masterplan", "A resale property"], 1),
    ("Q08", "pk", .82, "In a UK leasehold purchase, what is ground rent?",
     ["A charge for building maintenance", "A periodic payment to the freeholder for the land", "A local authority tax", "A one-off cost at completion"], 1),
    ("Q09", "pk", .88, "What does the service charge typically cover?",
     ["The buyer's mortgage interest", "Communal maintenance, building insurance and shared facilities", "Stamp duty", "The developer's profit margin"], 1),
    ("Q10", "pk", .47, "What is the Dubai Land Department transfer fee on a property purchase?",
     ["2%", "4%", "5%", "7%"], 1),
    ("Q11", "pk", .55, "What is an Oqood certificate?",
     ["A tenancy contract", "The interim registration of an off-plan sale with the DLD", "A mortgage pre-approval", "A snagging report"], 1),
    ("Q12", "price", .78, "A client asks why two units of identical size are priced differently. Which factor is most likely?",
     ["The developer's pricing mood", "Floor level, aspect and outlook", "The colour scheme", "The unit number"], 1),
    ("Q13", "price", .62, "On a 60/40 payment plan, what does the 40 represent?",
     ["A 40% deposit", "40% payable on completion and handover", "A 40% discount", "40 monthly instalments"], 1),
    ("Q14", "price", .53, "Which of these is NOT part of the buyer's upfront cost on a UK new-build purchase?",
     ["Reservation fee", "SDLT (stamp duty)", "Legal fees", "The year-five service charge"], 3),
    ("Q15", "qual", .74, "Which question best qualifies a buyer's motivation?",
     ['"What is your budget?"', '"Are you buying to live in or to let?"', '"Do you like the kitchen?"', '"When can you visit?"'], 1),
    ("Q16", "qual", .66, "A lead will not disclose their budget. Best next step?",
     ["Show only the cheapest units", "End the call", "Present two price points and read the reaction", "Insist on a figure before continuing"], 2),
    ("Q17", "qual", .71, "Which is the strongest buying signal?",
     ['"It looks nice."', '"How soon would I need to pay the second instalment?"', '"Send me the brochure."', '"I will speak to my wife."'], 1),
    ("Q18", "comp", .80, "A client asks you to guarantee a rental yield. What do you do?",
     ["Give your best estimate as a guarantee", "State only figures you can evidence and never guarantee future returns", "Quote the highest yield the development has achieved", "Refer to a competitor's published numbers"], 1),
    ("Q19", "comp", .77, "When must the reservation terms be provided to the buyer?",
     ["After payment is taken", "Before the reservation fee is taken", "At legal completion", "Only if the buyer asks"], 1),
    ("Q20", "comp", .86, "A buyer asks whether they should take a mortgage. You should:",
     ["Recommend the best product you know", "Refer them to a regulated adviser", "Give your personal opinion", "Compare current rates for them"], 1),
    ("Q21", "fu", .72, "A viewing ended with no decision. When is the best follow-up?",
     ["Within 24 hours, with a specific next step", "After a week, so they have space", "Only if they call you", "Immediately and repeatedly"], 0),
    ("Q22", "fu", .68, "What makes a follow-up message effective?",
     ["Repeating the full presentation", "Referencing a specific concern they raised and answering it", "Sending the price list again", 'Asking "any update?"'], 1),
    ("Q23", "obj", .41, '"Your competitor is offering a better payment plan." Best response?',
     ["Match the plan immediately", "Point out weaknesses in the competitor", "Compare total cost, delivery record and specification, not the plan alone", "Explain that plans cannot be changed"], 2),
    ("Q24", "close", .84, "The client says yes verbally. What actually secures the sale?",
     ["A handshake and a diary note", "Completing the reservation form and taking the fee", "Emailing a summary that evening", "Telling your manager"], 1),
    ("Q25", "pk", .87, "What is a snagging list?",
     ["A list of unsold units", "A record of defects found before handover for the developer to fix", "A list of interested buyers", "The construction programme"], 1),
    ("Q26", "qual", .69, "Why does cash buyer versus mortgage buyer matter at qualification?",
     ["Cash buyers always pay more", "It changes the timeline, the payment plan fit and the evidence needed", "It makes no practical difference", "Mortgage buyers are less serious"], 1),
    ("Q27", "price", .81, "What is SDLT?",
     ["A service charge band", "Stamp Duty Land Tax on UK property purchases", "A developer levy", "A leasehold covenant"], 1),
    ("Q28", "fu", .75, "A buyer goes quiet after reserving. First action?",
     ["Cancel the reservation", "Contact them with the next milestone and its deadline", "Wait for them to make contact", "Speak only to their solicitor"], 1),
]

PEOPLE = [
    ("Aisha Rahman", "London"), ("Tom Bradshaw", "Manchester"), ("Priya Nair", "London"),
    ("Callum Reid", "Manchester"), ("Fatima Al Suwaidi", "Dubai"), ("James Okafor", "Birmingham"),
    ("Sofia Marchetti", "London"), ("Hassan Darwish", "Dubai"), ("Ellie Thompson", "Liverpool"),
    ("Daniel Kovacs", "Leicester"), ("Noor Haddad", "Dubai"), ("Ryan Whitfield", "Manchester"),
    ("Chloe Bennett", "London"), ("Omar Farouk", "Birmingham"), ("Grace Adeyemi", "London"),
    ("Liam Doherty", "Liverpool"), ("Zainab Iqbal", "Leicester"), ("Marcus Bell", "Manchester"),
    ("Hana Suzuki", "London"), ("Peter Novak", "Birmingham"),
]

FOCUS = {
    "Handbook": {"comp", "close", "obj", "qual"},
    "Training": {"qual", "obj", "pk", "fu", "comp"},
    "Sales": {"pk", "price", "obj", "close"},
}


def rng(seed: int):
    """mulberry32 — the same generator the prototype uses, so figures line up."""
    state = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = (t ^ (t >> 15)) * (1 | t) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return nxt


def seed_trainings(db) -> list[Training]:
    out = []
    for i, (slug, title, sub, cat) in enumerate(DECKS):
        row = db.scalar(select(Training).where(Training.slug == slug))
        if not row:
            row = Training(id=f"t{i + 1:02d}", slug=slug)
            db.add(row)
        row.title, row.sub, row.category = title, sub, cat
        row.url, row.position = f"https://{slug}-{HOST}", i
        out.append(row)
    db.commit()
    return out


def seed_questions(db, trainings) -> dict[str, list[str]]:
    """Assign 8 placeholder questions per deck, biased to that deck's focus."""
    db.execute(delete(Question))
    layout: dict[str, list[str]] = {}
    for i, t in enumerate(trainings):
        r = rng(9000 + i * 37)
        want = FOCUS[t.category]
        scored = sorted(BANK, key=lambda q: (0 if q[1] in want else 1) + r() * .6)
        picked = sorted(scored[:8], key=lambda q: q[0])
        layout[t.id] = [q[0] for q in picked]
        for idx, (ref, skill, _base, text, options, correct) in enumerate(picked):
            db.add(Question(training_id=t.id, q_index=idx, ref=ref, skill=skill,
                            text=text, options=json.dumps(options), correct_index=correct))
    db.commit()
    return layout


def seed_sample(db, trainings, layout) -> None:
    base = {q[0]: q[2] for q in BANK}
    password = os.getenv("SEED_PASSWORD") or secrets.token_urlsafe(12)
    staff: list[tuple[Staff, float, float]] = []

    for i, (name, office) in enumerate(PEOPLE):
        r = rng(400 + i * 13)
        email = name.lower().replace(" ", ".") + "@baroncabot.example"
        row = db.scalar(select(Staff).where(Staff.email == email))
        if not row:
            row = create_staff(db, name=name, email=email, password=password,
                               office=office, is_sample=True)
        staff.append((row, (r() - .45) * .26, .52 + r() * .58))

    now_ms = dt.datetime.now(dt.timezone.utc)
    week = dt.timedelta(weeks=1)

    for si, (person, ability, engagement) in enumerate(staff):
        for ti, t in enumerate(trainings):
            r = rng(si * 977 + ti * 131 + 7)
            roll = r()
            if roll > engagement + .22:
                continue
            complete = roll < engagement
            refs = layout[t.id]
            slots = list(range(len(refs))) if complete else list(range(2 + int(r() * 4)))
            started = now_ms - week * (r() * 10)
            attempt = Attempt(staff_id=person.id, training_id=t.id, seq=1,
                              started_at=started, last_seen_at=started, is_sample=True)
            db.add(attempt)
            db.flush()
            total_ms = 0
            for slot in slots:
                ref = refs[slot]
                p = max(.08, min(.97, base[ref] + ability))
                ok = r() < p
                correct_idx = next(q[5] for q in BANK if q[0] == ref)
                if ok:
                    chosen = correct_idx
                else:
                    wrong = [x for x in range(4) if x != correct_idx]
                    chosen = wrong[int(r() * len(wrong)) % len(wrong)]
                ms = 9000 + int(r() * 46000)
                total_ms += ms
                db.add(Answer(attempt_id=attempt.id, staff_id=person.id,
                              training_id=t.id, q_index=slot, chosen=chosen,
                              is_correct=ok, ms=ms, is_sample=True))
            attempt.duration_ms = total_ms + 240000 + int(r() * 420000)
            if complete:
                attempt.completed_at = started + dt.timedelta(milliseconds=attempt.duration_ms)
        db.commit()

    if not os.getenv("SEED_PASSWORD"):
        print(f"  sample staff password: {password}   (set SEED_PASSWORD to choose your own)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", action="store_true",
                    help="also create 20 staff and a synthetic event log")
    ap.add_argument("--reset", action="store_true", help="drop all rows first")
    ap.add_argument("--manager-email", default="manager@baroncabot.example")
    args = ap.parse_args()

    init_db()
    db = session()

    if args.reset:
        for model in (Answer, Attempt, Question, Session, Staff, Training):
            db.execute(delete(model))
        db.commit()
        print("· cleared")

    trainings = seed_trainings(db)
    print(f"· {len(trainings)} trainings")

    layout = seed_questions(db, trainings)
    print(f"· {sum(len(v) for v in layout.values())} question slots tagged "
          f"(placeholder text — replace after reading the decks)")

    manager = db.scalar(select(Staff).where(Staff.email == args.manager_email))
    if not manager:
        pw = os.getenv("MANAGER_PASSWORD") or secrets.token_urlsafe(12)
        manager = create_staff(db, name="Sales Manager", email=args.manager_email,
                               password=pw, office="Head Office", role="manager")
        print(f"· manager {args.manager_email}")
        if not os.getenv("MANAGER_PASSWORD"):
            print(f"  manager password: {pw}   (set MANAGER_PASSWORD to choose your own)")

    if args.sample:
        seed_sample(db, trainings, layout)
        n_att = db.scalar(select(Attempt).where(Attempt.is_sample)) is not None
        print(f"· sample event log written  (flagged is_sample — the dashboard "
              f"shows the 'Sample data' badge while these rows exist)")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
