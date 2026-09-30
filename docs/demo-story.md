# End-to-end demo story

Five short conversations that exercise every requirement, including the fixture traps. Run them by hand in the UI, or automatically:

```bash
python3 scripts/story.py                                         # local Docker, http://localhost:8000
python3 scripts/story.py https://claims-assistant-4wy7.onrender.com
```

The script checks 32 things and exits 0 when all pass. It uses the session state the API returns plus the facts each reply must contain, so it holds whatever wording the model picks.

Start each story with **New conversation**. The right-hand **Session** panel shows the phase, verification progress, the selected claim, what the assistant remembers, and recovery counters. It shows field names only, never values.

## Story 1: Margaret Chen's denied claim (all four phases)

| Step | Type or click | What you should see |
|---|---|---|
| 1 | *(new conversation)* | Stepper on **Verify identity** (`VERIFY_ID`). Session: Not verified, 0 of 3 |
| 2 | `What is RL?` | A polite decline and a steer back to verification. Recovery: Off-topic **1** |
| 3 | `My name is Margaret Chen. I'm calling about my denied healthcare claim from January.` | Asks for more details. **No claim information**: no CL-2048, no amounts, no dates. Session: Full name ✓ (1 of 3). Memory already shows Type Healthcare, Status Denied, Month January |
| 4 | `My date of birth is 1985-03-15.` | Still not verified (2 of 3), still no claim information |
| 5 | `SSN last four is 4472.` | **Verified**, and the stepper jumps to **Handle claim** (`PROCESS_CASE`) without asking which claim; it used the remembered hint. The reply covers **CL-2048**: denied, missing pathology report and office note, submit them within a week, appeal deadline March 18, 2026, **17 days** from the demo business date of Mar 1, 2026. Selected claim card: CL-2048 · Denied |
| 6 | `This is so frustrating. What if I can't get the pathology report?` | Acknowledges the frustration first, then the approved guidance: a replacement copy or supporting records, and a human review if neither is available |
| 7 | `What about claim CL-3001?` | "Couldn't find a claim matching that". CL-3001 belongs to another customer and looks exactly like a missing claim, with nothing about it shown. Lists Margaret's own claims |
| 8 | `OK, back to the denied one.` | CL-2048 selected again |
| 9 | `That's all, thanks.` | Stepper on **Wrap up** (`POST_PROCESS`). An email summary card: To m\*\*\*\*\*\*\*@email.com, subject with CL-2048, the body with status, reason, documents, deadline and next steps. **Send summary** / **Skip** |
| 10 | Click **Send summary** | The conversation closes. With Docker Compose the email arrives in Mailpit at http://localhost:8025. On the live demo the card says it was recorded but not delivered, because there's no mail server |

## Story 2: someone guessing Margaret's SSN

| Step | Type | What you should see |
|---|---|---|
| 1 | `My name is Margaret Chen, DOB 1985-03-15, SSN last four 1111.` | "Couldn't verify", without saying which detail was wrong. Failed attempts **1 of 3** |
| 2 | Same with `2222` | Failed attempts **2 of 3** |
| 3 | Same with `3333` | Automated verification stops and a human is **requested**; it's simulated and never shown as connected |
| 4 | Same with the correct `4472` | Still not verified: a locked conversation can't keep trying |

## Story 3: Ma Tian and a national ID

| Step | Type | What you should see |
|---|---|---|
| 1 | `My name is Ma Tian, DOB 1964-09-10, SSN last four 6688.` | Not verified. 6688 is her **national ID**, which never counts as an SSN |
| 2 | `My name is Ma Tian, born 1964-09-10, phone (650) 208-8799.` | Verified, and only her own claim, **CL-3001**, is listed |

## Story 4: a caller who won't share details

| Step | Type | What you should see |
|---|---|---|
| 1 | `Why do you need my SSN? I don't want to give it.` | Explains why verification protects them and offers the other fields. Recovery: Refusals **1** |
| 2 | `I'm not comfortable sharing any of that.` | Refusals **2**, and a human is offered |
| 3 | `Please connect me to a human.` (or click **Talk to a human**) | A banner says a human representative has been **requested** (simulated in this demo) |

## Story 5: nothing is guessed

| Step | Type | What you should see |
|---|---|---|
| 1 | `My name is Margaret Chen, DOB 03/04/1985.` | The date isn't accepted: it asks whether you mean **March 4 or April 3**. Session: only Full name ✓ |
| 2 | `My name is Margaret Chen, born March 15, 1985, email margaret@email.com.` | Verified (name, date of birth, email). Lists her four claims and asks what she needs |
| 3 | `It's about my healthcare claim from January.` | Two claims match, **CL-2048** (2026) and **CL-2011** (2025), so it asks which one |
| 4 | `The denied one.` | CL-2048 selected |

## Requirement coverage

| Requirement | Where |
|---|---|
| Strict identity check: 3 of 5 fields, no disclosure before it | Story 1 steps 3–5, Story 2, Story 3 |
| Clarifying questions, partial answers, refusals, alternate fields | Story 1 steps 3–4, Story 4, Story 5 |
| Intent resolved from messy language, answers only from claim data | Story 1 steps 5–8, Story 5 steps 3–4 |
| Memory of early hints, used after verification | Story 1 step 3 → step 5 |
| Email summary with send or skip | Story 1 steps 9–10 |
| Off-topic declined; repeated, a human offered | Story 1 step 2 (say it 3 times to see the escalation) |
| Emotional support and escalation without bypassing gates | Story 1 step 6, Story 2 step 3, Story 4 |
