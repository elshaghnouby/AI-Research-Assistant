# Sales Training Intelligence Dashboard — Handoff Brief

Paste the prompt block below into a **fresh local Claude Code session** opened in
this repo. Design is already settled — this session finishes the parts that need
access to the live decks.

**Already in this repo:**
- `training_staff_links.md` — the 17 deck URLs, grouped
- `prototype/dashboard.html` — working single-file dashboard prototype on seeded
  sample data. This is the **approved front-end spec**, not a draft to redo.

---

```
Finish the Sales Training Intelligence Dashboard. Design is already decided —
do not redesign it.

## STARTING STATE
- 17 sales training / quiz decks are live on Google Cloud Run. URLs are in
  training_staff_links.md.
- Each deck ALREADY contains its questions, correct answers, and instant
  client-side grading: a rep clicks an option, the deck marks it right or wrong
  and reveals the correct answer.
- ~20 sales staff. Property sales (UK + Dubai + Phuket).
- prototype/dashboard.html is a working prototype and the APPROVED front-end
  spec: 4-item nav, drill-down to staff / training / question, 5 charts,
  thresholds in one place, n<5 suppression, sample-data badge.
  Read it before writing anything.
- No auth, no database, no backend exists yet.

## HARD SCOPE LOCK — never violate
- NEVER change the content, wording, questions, answers, styling or URLs of the
  17 decks. They stay byte-identical to what reps see today.
- Do NOT redesign the dashboard. Its information architecture, drill path, chart
  set and visual system are settled. Change it only where I ask.
- Only build what is described here. No extra features, abstractions or files.

## WHY THE PROTOTYPE IS SHAPED THE WAY IT IS
Every figure it shows is derived from an `answers` array whose rows are
  {staff, training, q, chosen, ok, ms}
which is exactly the tracker payload. Wiring real data must REPLACE THE SOURCE
of that array and leave the aggregation and charts untouched. If you find
yourself rewriting the aggregation, you have taken a wrong turn.

## STEP 1 — INSPECT THE DECKS FIRST, BEFORE ANY CODE
The previous session could not reach *.run.app (sandbox egress block), so this
was never done. Do it now. Open at least 3 decks — one city training deck, one
sales slides deck, and the managers handbook — and report:
- How questions are stored in the page (inline JS array? HTML? fetched JSON?)
- How many questions per deck, and whether the count is consistent
- The exact DOM event that fires when a rep picks an answer
- Whether anything is currently POSTed to any server
- Whether questions carry any id, number, or topic/skill label
- Whether the decks share one codebase/template or differ per deck
Read the actual page source. Do not guess any of it.
Then STOP and report before continuing.

## STEP 2 — TRANSPORT DECISION, THEN STOP AND ASK
Grading happens in the browser and never leaves the page. The dashboard needs
those events on a server. Propose the method and WAIT for my approval:
- Option A (preferred): serve the decks through the new app as a same-origin
  reverse proxy, injecting a small tracker script at serve time. The 17 Cloud
  Run services are never touched or redeployed.
- Option B: add one script tag to each deck and redeploy.
Event payload: {staff_id, deck_id, question_index, chosen, is_correct, ms}
Skill tags live in OUR database as a question_index -> skill mapping, never
inside the deck.

## STEP 3 — BACKEND
- Database schema: staff, trainings, attempts, answers, question_skill_map
- POST /api/events ingest endpoint matching the payload above (idempotent per
  staff+deck+question+attempt; reject unknown staff_id)
- Reverse proxy route per approved method
- Staff registration + login, ~20 users, manager role separate from staff role
Propose the stack in step 1 and wait for my approval before installing anything.

## STEP 4 — WIRE THE PROTOTYPE TO REAL DATA
Port prototype/dashboard.html to the chosen stack, keeping its layout,
components, thresholds and copy. Replace the seeded generator with real queries.
Remove the sample-data badge ONLY when the page is reading the real database;
while any figure is seeded, the badge stays.

## DATA HONESTY — mandatory
- NEVER fabricate analytics and present them as real.
- Show n= next to every percentage. With only 20 staff, HIDE the percentage
  entirely when n < 5 — never let a coaching decision rest on 3 people.
- Real empty states everywhere: "No attempts recorded yet", not a zero.

## STOP AND ASK BEFORE
- Touching any of the 17 decks in any way
- Choosing the stack, or adding any dependency
- Creating or migrating any database schema
- Deleting any file
- Deploying anything

## CHECKPOINTS
After each step output: DONE: [what was completed] -> [what is next]
Stop after step 1 and after step 2 for my approval. Do not run ahead.
```

---

**Note:** this prompt is for an agentic tool with real system access. Review the
scope locks, forbidden actions and stop conditions before pasting. Confirm file
paths and permissions match the actual project.
