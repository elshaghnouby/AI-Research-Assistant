# Sales Training Intelligence

A manager dashboard over the 17 live training decks, plus the login and tracking
that feed it.

**The decks are never modified.** Their content, wording, answers, styling and
URLs stay exactly as they are. This app sits in front of them, records what
happens, and reports on it.

## Run it

This is not a hosted site. It runs on your own machine, and the address below
only answers once you have started the server yourself.

**Windows (PowerShell)**

```powershell
pip install -r requirements-training.txt

$env:MANAGER_PASSWORD = "choose-one"
python -m training.seed --sample          # 17 decks + a manager + demo data
python -m uvicorn training.main:app --reload --port 8000
```

**macOS / Linux**

```bash
pip install -r requirements-training.txt

MANAGER_PASSWORD='choose-one' python -m training.seed --sample
python -m uvicorn training.main:app --reload --port 8000
```

Leave that last command running — it is the server. When it prints
`Application startup complete`, open `127.0.0.1:8000` in a browser and sign in
with the manager email and the password you set. Closing the terminal stops the
server and the address stops answering.

Drop `--sample` for an empty system: you still get the 17 decks and a manager
account, and every page shows its real empty state until someone answers
something. Passwords are never stored in this repo; set `MANAGER_PASSWORD` and
`SEED_PASSWORD`, or the seeder generates them and prints them once.

`DATABASE_URL` defaults to SQLite under `data/`. Point it at Postgres
(`postgresql+psycopg://…`) and nothing else changes.

## How a click becomes a number

```
rep opens  /t/<deck-slug>
              │
              ├─ proxy fetches the real deck from Cloud Run, unchanged
              ├─ injects  <base href="https://<deck>.run.app/">   (assets keep loading from there)
              └─ injects  <script src="/static/tracker.js">       (last line before </body>)
                             │
                             │ rep answers; the deck grades it as it always has
                             ▼
                    POST /api/events   {q, chosen, correct, ms}
                             │
                             ▼
                    answers table — one row per answered question
                             │
                             ▼
                    GET /api/dashboard → the event log
                             │
                             ▼
                    dashboard.html reduces it into every figure on screen
```

Nothing is stored pre-aggregated. Correct an event and every number that
depended on it corrects with it.

## Layout

| File | What it holds |
|------|---------------|
| `models.py` | schema — staff, trainings, questions, attempts, answers, sessions |
| `auth.py` | scrypt passwords, server-side sessions, `staff` / `manager` roles |
| `proxy.py` | `/t/{slug}` — same-origin deck proxy with tracker injection |
| `main.py` | routes, including `POST /api/events` ingest |
| `analytics.py` | the dashboard payload, and our skill vocabulary |
| `seed.py` | the 17 real decks; `--sample` adds a synthetic event log |
| `static/tracker.js` | the injected tracker **(see the caveat below)** |
| `static/dashboard.html` | the manager dashboard |
| `static/trainings.html` | the rep's list of 17 |
| `static/login.html` | sign in / create account |

## Two things still to do

**1. The tracker is unverified.** It reads the grading the decks already do, but
nobody has yet read a deck's source to confirm which DOM signal it uses. The
generic adapter in `tracker.js` reports nothing rather than guessing when the
signal is unclear, so bad data will not accumulate — but real data will not
either, until a deck is checked. Open one deck with `?tracker=debug`, click a
right answer and a wrong one, and compare the console output to what you
clicked. If it does not match, add an entry to `ADAPTERS` keyed by the deck slug.

**2. Question text and skill tags are placeholders.** `seed.py` writes 8
plausible property-sales questions per deck so the question panel has something
to show. The real questions live in the decks. Once a deck has been read,
replace those `Question` rows with its actual questions and tag each one with a
skill. The tagging lives here, never in the deck.

Until real events arrive, the dashboard carries a **Sample data** badge, driven
by the `is_sample` flag on the seeded rows.

## Deploying

The app is a single FastAPI service and deploys to Cloud Run the same way the
decks do. Set `DATABASE_URL` to a managed Postgres instance, set
`MANAGER_PASSWORD`, and serve behind HTTPS — then flip the session cookie to
`secure=True` in `auth.py`.
