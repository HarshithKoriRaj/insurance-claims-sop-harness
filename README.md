# Claims Assistant: an SOP harness for an insurance claims support agent

A chat agent for insurance claims support that follows a standard operating procedure in four phases. Claude reads each message and words each reply. Deterministic code decides everything in between: who the caller is, what they may see, and what happens next.

| Phase | What happens | Gate to leave it |
|---|---|---|
| `VERIFY_ID` | Collects identity details. Discloses nothing about claims. Handles partial answers, refusals, clarifying questions and alternate fields. | 3 distinct permitted fields match exactly one policyholder, and no supplied field contradicts that record |
| `RESOLVE_INTENT` | Works out which of the caller's claims they mean, using hints remembered from earlier, e.g. "my denied healthcare claim from January" | Exactly one owned claim selected |
| `PROCESS_CASE` | Answers from the claim record and approved guidance only | Caller is done, or picks another claim |
| `POST_PROCESS` | Shows an email summary and asks the caller to send or skip it | Explicit send or skip. An email only goes out after "send" |

The permitted identity fields are full name, date of birth, phone, email, and the last 4 digits of the SSN. A policy number is not an identity field.

## Quick start (Docker)

```bash
cp .env.example .env          # put your Anthropic API key in ANTHROPIC_API_KEY
docker compose up --build
```

- Chat UI: http://localhost:8000
- Demo inbox for the email summaries (Mailpit): http://localhost:8025
- API docs: http://localhost:8000/api/docs

Without an API key the app still works, in a rule-based offline mode. The inspector panel shows which mode is active.

### Try the demo script

Click **Try the demo** under the input box, or paste:

> I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied healthcare claim from January. DOB is 1985-03-15, SSN last four is 4472.

The assistant:
1. Verifies her from name, date of birth and SSN last 4. The policy number doesn't count.
2. Uses the remembered hint (denied, healthcare, January) to select **CL-2048** without asking again. That rules out her other January claim, CL-2011, which is closed.
3. Explains the denial, the documents needed, and the appeal deadline. The deadline is **17 days** away on the pinned demo date, 2026-03-01.
4. When she's done, offers the summary email with **Send summary** / **Skip**.

Other scenarios worth trying:

| Try | Expected |
|---|---|
| "What is RL?" three times | Polite decline, then an offer of a human, then a (simulated) handoff |
| Wrong SSN three times | Automated verification stops and a human is requested |
| "Why do you need my SSN?" | Explains why, offers the other fields, offers a human on a second refusal |
| `DOB 03/04/1985` | Asks whether that's March 4 or April 3; never guesses |
| Ma Tian (P12) with name, DOB and SSN 6688 | Not verified: that's a national ID, not an SSN. Name, DOB and phone work |
| Verified Margaret asks about CL-3001 | "Couldn't find a claim", the same answer as for a claim that doesn't exist, because CL-3001 belongs to someone else |
| "I'm frustrated…" | The reply acknowledges the feeling first |
| "Talk to a human" | Handoff requested, never shown as "connected" |

## Configuration

Set these in `.env` (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Enables Claude. Read once at startup; never logged or returned by the API |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Model for interpreting and replying |
| `APP_MODE` | `demo` | `demo` pins the business date to 2026-03-01 so the fixture appeal deadlines are still open. `production` uses the real date and rejects overrides |
| `BUSINESS_DATE_OVERRIDE` | (empty) | Demo mode only: `YYYY-MM-DD` or `today` |

## How it works

```
browser ──► FastAPI ──► ConversationService.interpret ──► Claude (forced tool call) → Interpretation
                    ├─► WorkflowEngine (deterministic) ──► ClaimAccess (owner-scoped), GuidanceLibrary, Mailer
                    └─► ConversationService.respond ─────► Claude (writes from the engine's brief) → reply
```

- **The model proposes; the code decides.** Each turn, Claude fills in a strict schema: identity details as stated, intent, claim hints, scope, emotion, and whether the caller wants a human, is refusing, or is choosing to send or skip. The engine validates that and makes every transition. No model output can mark a caller verified, pick another customer's claim, or send an email.
- **Nothing is disclosed before verification.** Claim lookups need a verified party ID. Before verification the reply brief contains no claim data. As a backstop, any model reply that mentions a claim ID or an amount before verification is discarded and replaced with a template.
- **Only the caller's own claims.** Every lookup is scoped to the verified party. Another customer's case ID and a nonexistent one get the same "couldn't find it" answer.
- **Verification** compares normalized values (NFKC, case, spacing, E.164 phones, ISO dates) against every record and every alias, with no first-match shortcut.
  - A national ID never counts as an SSN.
  - An unclear value (a date that could be day-first or month-first, a phone number that looks mistyped) is asked about again rather than guessed, and doesn't count as a failed attempt.
  - Three failed attempts stop automated matching.
- **Cross-phase memory.** Intent and claim hints given before verification are kept and used as soon as verification succeeds.
- **Consent.** The summary preview is generated by code from the claim record and approved guidance, and shown in full. The email goes only to the address on file, after an explicit Send (button or a clear typed yes to the active offer). Each preview has an ID, so a retry can't send it twice. A new question withdraws the preview.
- **Recovery.**
  - Consecutive off-topic requests: declined, then a human is offered, then handed off (2 and 3, set in `policies/defaults.toml`).
  - Identity refusals: explained, with alternatives offered.
  - Emotions: acknowledged first.
  - Handoff to a human is requested and clearly labelled as simulated.
- **Resilience.** If Claude is unavailable, interpretation falls back to rules and replies fall back to templates, so the workflow and its gates still work.
- **Sessions** are stored in SQLite with a hashed bearer token and optimistic versioning. After 30 minutes idle, verification expires, the conversation resumes at `VERIFY_ID`, and earlier claim details are hidden.

Code map:

```
services/api/app/
  policies.py, clock.py            versioned policy defaults; business-date clock
  contracts/fixtures.py            strict models for the six fixture files
  claims/                          importer (read-only, cross-checked), documents, guidance, money,
                                   deadlines, access.py (owner-scoped claim tools)
  identity/                        normalize.py, fields.py, verify.py
  workflow/                        state.py, engine.py (phases, gates, transitions)
  conversation/                    claude.py, interpretation.py (schema + offline rules), templates.py, service.py
  summaries/mailer.py              idempotent SMTP sender (Mailpit in Docker)
  main.py, runtime.py, settings.py API, composition root, env settings
apps/web/                          React + Vite chat UI with phase stepper and session inspector
fixtures/                          supplied data, never modified (hash-checked by a test)
policies/                          defaults.toml (thresholds), document_codes.toml (label aliases)
docs/                              architecture plan and milestone plan
```

## Local development

```bash
uv sync
uv run pytest                        # 287 tests; offline, deterministic
set -a; . ./.env; set +a             # load the API key into this shell
uv run uvicorn app.main:create_app --factory --app-dir services/api --reload
cd apps/web && npm install && npm run dev      # http://localhost:5173, proxies /api to :8000
```

## Design decisions and known limitations

- **Fixture traps handled:**
  - Policy number isn't an identity field.
  - P12 and P13 hold national IDs.
  - "Yaven Li" is an alias.
  - P9's and P13's phone numbers differ by one digit.
  - Some dates of birth read differently day-first and month-first.
  - Document labels differ from guidance keys.
  - P9 has two January healthcare claims.
  - The appeal deadlines have passed at the real date.

  The demo clock pins the date; `BUSINESS_DATE_OVERRIDE=today` shows the expired case.
- **Representatives:** someone calling on another person's behalf is offered a human rather than being verified. The consent-scenario flow in the fixtures is not automated.
- **Human handoff** is simulated. The session moves to `HANDOFF_PENDING` and never claims a person has joined.
- **Deliberately scoped out for the deadline:**
  - the Jev classifier (designed in `docs/2026-09-28-sop-harness-plan.md` as an optional fast path, with Claude's labels as the fallback);
  - Postgres (SQLite here);
  - a background email worker (sending is in-process and idempotent);
  - claim-data refresh (the fixtures are static).
- The follow-up templates in the supplied guidance are written for plural document lists. The agent keeps approved wording as-is rather than rewriting it.
