# Sales Training Intelligence Dashboard — Handoff Brief

Paste the prompt block below into a **fresh local Claude Code session**.
The 17 deck URLs live in `training_staff_links.md` in this repo.

---

```
Build a Sales Training Intelligence Dashboard for sales managers.

## STARTING STATE
- 17 sales training / quiz decks are live on Google Cloud Run. URLs are in
  training_staff_links.md in this repo.
- Each deck ALREADY contains its quiz questions, the correct answers, and
  instant client-side grading: a rep clicks an option, the deck marks it
  right or wrong and reveals the correct answer.
- ~20 sales staff will use them.
- No auth, no database, no dashboard exists yet. This is greenfield.

## HARD SCOPE LOCK — never violate
- NEVER change the content, wording, questions, answers, styling, or URLs of
  the 17 decks. They stay byte-identical to what reps see today.
- Adding a tracking layer is allowed ONLY after I approve the method (step 2).
- Only build what is described here. Do not add extra features, abstractions,
  or files.

## TARGET STATE
1. Central staff registration + login
2. The 17 existing decks, reached through the new app
3. A new dedicated database
4. A manager dashboard

## STEP 1 — INSPECT FIRST, BEFORE ANY CODE
Open at least 3 decks (one city training deck, one sales slides deck, one
handbook) and report:
- How questions are stored in the page (inline JS array? HTML? fetched JSON?)
- How many questions per deck
- The exact DOM event that fires when a rep picks an answer
- Whether anything is currently POSTed to any server
- Whether questions carry any id, number, or topic/skill label
Do not guess any of this. Read the actual page source.

## STEP 2 — TRANSPORT DECISION, THEN STOP AND ASK
Grading happens in the browser and never leaves the page. The dashboard needs
those events on a server. Propose the method, then WAIT for my approval:
- Option A (preferred): serve the decks through the new app as a same-origin
  reverse proxy, injecting a small tracker script at serve time. The 17 Cloud
  Run services are never touched or redeployed.
- Option B: add one script tag to each deck and redeploy.
Event payload: {staff_id, deck_id, question_index, chosen, is_correct, ms}
Skill tags live in OUR database as a question_index -> skill mapping.
Never inside the deck.

## STEP 3 — DASHBOARD
Navigation (4 items):
  Overview | Team | Trainings | Skills & Questions
Drill-down views, NOT in the nav:
  Staff detail (/team/:id) | Training detail (/trainings/:id)
  Question detail (side panel, never a full page)

Overview, in this exact order — worst always on top:
  1. KPI row: Total Staff, Completion %, Avg Score, Avg Time, At Risk
  2. Team Weak Areas          <- most important, above the fold
  3. Most Missed Questions    <- top 5, each row clickable
  4. Training Completion      <- all 17, sorted ascending (worst first)
  5. Score Distribution

Team page: sortable roster + a 20x17 coverage matrix using status dots
  (a table, NOT a colored heatmap).
Trainings page: per deck - started, completed, rate, avg score, avg time,
  weakest topic.
Skills & Questions: ranked skills on top, missed questions below, filtered
  by the selected skill.
Staff detail: completion, scores, time, wrong answers GROUPED BY SKILL (not a
  raw list), history. Keep it simple.

Drill path that must never lose the user:
  Overview -> weak skill -> question -> distractor breakdown -> staff
- Breadcrumb visible at every level
- All filters stored in the URL, so browser Back keeps them and links are
  shareable
- Question opens in a side panel so the context behind it stays on screen

Copy rule: write "Objection Handling is the weakest area - 11 of 20" rather
than "Ahmed scored 62%". Describe the situation, not the person.

## CHARTS — exactly these 5, nothing more
- Ranked horizontal bars: completion by training
- Ranked horizontal bars: weak skills
- Ranked horizontal bars: most missed questions
- Histogram: score distribution (10-point buckets)
- Line: completion over time — HIDE this until 4+ weeks of data exist
Banned: donut charts, radar charts, gauges, colored 20x17 heatmaps.

## VISUAL DIRECTION
Premium B2B SaaS. Information hierarchy over visual effects.
- Fixed 240px sidebar, content max-width 1440, 8pt spacing grid
- One sans-serif (Inter). 4 sizes: 28/18/14/12. Weights 600/500/400.
  Numbers use tabular-nums.
- Neutral slate base. Color communicates STATUS ONLY:
  green >=80, amber 60-79, red <60. One blue accent for interactive only.
- Thresholds defined in ONE config file and used everywhere. No ad-hoc values.
- Charts: neutral gray bars; status color appears only past a threshold.
- 1px borders, not shadows. Max 6px radius. No gradients. No animation beyond
  simple state transitions.
- Every widget needs a real empty state ("No attempts recorded yet"), a
  loading skeleton, and an error state with retry.
- Desktop-first, usable on tablet.

## DATA HONESTY — mandatory
- NEVER fabricate analytics and present them as real.
- Any sample data must render a persistent "Sample data" badge in the header.
- Show n= next to every percentage. With only 20 staff, HIDE the percentage
  entirely when n < 5 — never let a coaching decision rest on 3 people.

## STOP AND ASK BEFORE
- Touching any of the 17 decks in any way
- Choosing the stack (propose it in step 1 and wait)
- Creating or migrating any database schema
- Adding any dependency
- Deleting any file
- Deploying anything

## CHECKPOINTS
After each step output: DONE: [what was completed] -> [what is next]
Stop after step 1 and after step 2 for my approval. Do not run ahead.
```

---

**Note:** this prompt is for an agentic tool with real system access. Review the
scope locks, forbidden actions, and stop conditions before pasting. Confirm file
paths and permissions match the actual project.
