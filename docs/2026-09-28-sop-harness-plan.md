# Insurance claims SOP harness: architecture and delivery plan

Date: 2026-09-28. Status: proposed design; no application has been implemented.

## Outcome and scope

Build a Docker-runnable, text-chat demo using the six supplied fixtures and a configurable server-side model API token. Preserve the four business phases: VERIFY_ID → RESOLVE_INTENT → PROCESS_CASE → POST_PROCESS. Make the conversation natural without giving the model authority to bypass business gates. Include email send/skip, an observable workflow trace, and emotional recovery.

Assumption: start with synthetic fixture data and a local email sink; retain adapters for real identity, claims, email, and human-support systems. Production deployment is a later release gate, not a label earned by a polished demo. Three matching PII fields meet the assignment's verification requirement; real deployment needs an insurer-approved authentication and representative-authorization policy, potentially including a signed-in session or step-up authentication.

No finite test suite covers every possible conversation. The design must cover identified failure classes, block unauthorized actions independently of model behavior, and clarify or escalate unfamiliar situations.

## Architecture decision

| Approach | Benefit | Main limitation | Decision |
|---|---|---|---|
| One large system prompt | Fast prototype | Workflow and permissions depend on model obedience | Reject |
| Deterministic workflow with bounded model interpretation | Explicit gates, natural language, replayable decisions | Requires careful state and tool contracts | Choose |
| General multi-agent planner or distributed workflow platform | Useful for many teams and long business processes | Unnecessary coordination and operational complexity for this scope | Defer |

Use a modular monolith: React/TypeScript chat UI, Python/FastAPI API, Pydantic contracts, PostgreSQL state/audit/outbox, and a separate worker process built from the same backend image. Use a provider adapter for model calls, a classifier adapter for Jev with the generative model's labels as fallback, fixture adapters for identity/claims, and Mailpit as the local email sink. Pin supported dependency versions and image digests during implementation. A vector database, autonomous agent swarm, and message broker are not required for six structured fixtures.

The model is an interpreter and response planner. Jev supplies per-turn labels with confidence; like the model, it proposes and never authorizes. The application is the authority for identity, permission, phase transitions, tool execution, claim facts, and delivery receipts.

```mermaid
flowchart LR
  U[Chat UI] --> API[Session API]
  API --> I[Model interpreter: typed proposals]
  I --> P[Policy engine and state machine]
  API --> C[Jev classifier: labels with confidence]
  C --> P
  P --> T[Authorized tool gateway]
  T --> D[Identity and claims adapters]
  D --> R[Grounded response planner]
  P --> R
  R --> V[Validation and server rendering]
  V --> U
  P --> S[(State, audit, outbox)]
  S --> W[Email and handoff worker]
```

## Non-negotiable invariants

1. No customer claim query or protected claim output before identity and applicable representative authority are established.
2. Verification requires at least three distinct permitted fields matching exactly one eligible policyholder. When several eligible records reach three, ask for another permitted field or escalate; never select the first result. Policy number may help find candidates; it is not one of the required three fields and never breaks a tie.
3. Caller statements and model outputs can propose facts; only trusted verification/tool results establish verified facts.
4. The gateway checks every tool call against that tool's row in Tool permissions: required authority, phase, and conditions. Tenant and session are bound server-side. Verified authority is required only where that table says so, so verification and unverified handoff work before verification. Tool permissions are enforced even if the model is compromised.
5. Every claim query is restricted to the authorized subject. A caller-supplied case ID does not establish ownership.
6. Only the state machine changes phases. The model cannot set verified=true, choose arbitrary tools, modify audit history, or grant consent.
7. Email requires an authorized destination and explicit approval bound to the actual summary version. Skip and refusal terminate the offer without persuasion.
8. An assistant never claims an email was sent, a human connected, documents uploaded, an appeal filed, or a claim changed without the corresponding tool receipt.
9. Failures do not convert unknown identity, ownership, consent, or claim status into success.
10. Raw PII and provider API secrets do not appear in telemetry, public debug panels, or email summaries.

These controls follow the separation of untrusted model input from privileged actions and least-privilege tool access described in [OWASP's prompt injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html). A second model checking the first is supplemental, not the authorization boundary.

## State and memory

Persist a versioned ConversationState with session_id, tenant_id, lifecycle, phase, phase_substate, case_cycle_id, revision, active_prompt_id, workflow_version, prompt_version, and model_version.

Keep separate structures:

- IdentityEvidence: field, encrypted normalized value or protected reference, source turn/span, correction history, and verifier result. Permitted demo fields: full_name, dob, phone, email, ssn_last4.
- VerificationReceipt: subject_id, method, distinct matched field names, verifier version, issued_at, expires_at, and authorization scope. Do not expose individual match results to callers.
- RepresentativeAuthority: representative identity, subject identity, grant reference, permitted actions, expiry, and revoked status; absent authority means no protected access.
- IntentMemory: caller role, requested tasks as an ordered queue (see Interrupted workflows), case hints, source turn/span, and tentative/confirmed status. A user saying “denied in January” is a search hint, not proof of a denial.
- CaseContext, one per case cycle: task (a selected case ID, or general service with no case), cycle status (see Interrupted workflows), resume pointer (phase, substate, pending question), ownership-checked fact snapshot, source version, fetched_at, unresolved ambiguity, and discussed fact IDs with the source version each was stated from. Refresh rules are under Claim-data freshness.
- RecoveryState: consecutive unrelated requests, failed verification submissions, refusal count, last recovery action, and human-transfer status. Emotion labels are temporary conversational cues, not persistent customer traits.
- SummaryConsent: preference, preview version/hash, masked destination reference, approval turn, consent expiry, cancellation state, and delivery status.

Memory is scoped to the session and verified subject. Every accepted interpretation cites an actual user turn/span; unsupported model inferences cannot become verification evidence. Resolve correction language deterministically after extraction. Keep a short recent-turn window plus typed memory; do not rely on an ever-growing transcript or an LLM-generated summary to preserve permissions.

Verification expiry or an identity correction invalidates the receipt and removes protected context from subsequent model requests. A different policyholder starts a new verification context and clears case-specific memory from the active context. Historical audit remains access controlled.

Session resumption: resuming after a browser refresh or reconnect requires the original session credential; a conversation ID alone is insufficient. Valid verification is required only to restore protected claim information. Protected history means every turn from the first verified turn onward, plus summary previews.

| Session credential | Verification | Resume at | Transcript and model context |
|---|---|---|---|
| Missing or invalid, past the maximum session age, or session CLOSED | Any | A new session | Nothing from the old session |
| Valid | Not yet verified | VERIFY_ID, at the pending question | Earlier turns with typed identity values masked; collected fields listed by name so the caller is not asked again |
| Valid | Valid receipt | The recorded phase and substate | Full history; case facts re-read per Claim-data freshness before reuse |
| Valid | Expired or invalidated (lifecycle EXPIRED) | VERIFY_ID | Pre-verification turns only; protected history withheld from both |

Unverified identity evidence lapses after the same idle limit as a verification receipt; the caller then re-enters fields, and remembered intent hints are kept. When an EXPIRED session re-verifies as the same subject, protected history returns and the interrupted case cycle resumes. A different subject starts a new verification context and never sees the earlier protected history.

Claim-data freshness: for fixtures, the source version is a hash of the claim record.

- Read the case fresh when a cycle selects it, when an interrupted cycle resumes, and before prepare_summary.
- Before any reply that states material facts (status, reason, money, documents, dates), re-read if the snapshot is older than CASE_FACT_MAX_AGE (default five minutes).
- On a changed source version, update the snapshot and mark earlier discussed facts superseded, not deleted. For a material change, tell the caller what changed before continuing and regenerate any pending answer. If the subject can no longer read the case, stop using the snapshot and treat it as no match.
- If a required re-read fails, do not present the snapshot as current: say the latest status cannot be confirmed, give the last-known value labeled with its fetched_at time, and offer a retry or a human. prepare_summary requires a successful re-read; otherwise offer retry, skip, or a human.
- The email reports the latest status from the pre-summary re-read, labeled with its as-of time. When it differs from what was discussed, the preview shows both and the agent explains the change before asking for approval; approval binds to that preview version. The worker does not re-read the claim; the as-of label keeps a sent email accurate.
- Tests use a fixture adapter that can change a claim's version mid-conversation; the supplied fixtures stay unchanged.

## Phase contracts

| Phase | Permitted actions | Exit guard | Stay or recover when |
|---|---|---|---|
| VERIFY_ID | Extract identity and future intent hints, explain privacy, ask for alternate fields, call verifier, answer generic questions from approved guidance without account data, request human assistance | Three distinct permitted fields matching exactly one eligible policyholder; no unresolved contradiction; representative authority if applicable | Missing/ambiguous/mismatched evidence, refusal, authorization pending, provider failure |
| RESOLVE_INTENT | Interpret remembered hints, list only owned cases, clarify case/need, explain in-scope general terms | Supported intent and one authorized selected case, or a clearly scoped general-service task | Multiple matching claims, unsupported action, no matching claim |
| PROCESS_CASE | Retrieve selected case, explain grounded status/denial/documents/timing, answer follow-ups, arrange authorized handoff | User confirms completion/declines further help, or bounded task reaches a documented outcome | Follow-up pending, conflicting data, tool failure, new claim ambiguity |
| POST_PROCESS | Build summary, show authorized destination, ask send/skip, dispatch once when approved, report receipt | Sent/accepted status truthfully reported, skip, or explicit deferred/handoff outcome | Ambiguous consent, changed summary, changed recipient, unknown delivery status |

Lifecycle is separate from phase: ACTIVE, PAUSED, HANDOFF_PENDING, HANDED_OFF, CLOSED, EXPIRED. EXPIRED means the verification receipt lapsed; the session credential still resumes the session at VERIFY_ID. A user can stop or request a human in any phase without artificial completion of later phases. Normal phase progression is monotonic within a case cycle; a verification interrupt suspends a cycle without resetting its phase. Never silently send a now-stale summary.

Interrupted workflows: a case cycle handles one task, either a selected owned case or a general-service task with no case. A cycle is active, completed, interrupted, or withdrawn. The session summary covers every cycle with discussed facts and lists interrupted or withdrawn tasks as open items.

| Event | Next state | Memory retained | Cancelled | Summary |
|---|---|---|---|---|
| Caller asks about a different claim during PROCESS_CASE | Current cycle completed, or interrupted if a follow-up was pending. A new cycle starts at RESOLVE_INTENT in the same turn and selects directly when the request identifies exactly one owned case | Verification, task queue, every cycle's discussed facts, the new request's hints | The previous cycle's pending clarification, kept as an open item | Covers both cycles |
| Verification expires during case discussion | Lifecycle EXPIRED, phase VERIFY_ID; the active cycle is interrupted with its resume pointer. Same-subject re-verification resumes it after a fresh case read; a different subject starts a new context | Caller-stated hints and the task queue. Protected facts leave model context; the resume pointer stays server-side | In-flight tool results (never disclosed) and any unapproved preview. An approved, queued summary still dispatches | Prepared only after verification is valid again |
| Several requests, in one message or across turns | Tasks queue in the caller's order unless they set priorities. Topics about the same case share a cycle; each other case or general task gets its own. After each cycle, offer the next task; enter POST_PROCESS only when the queue is empty or the caller declines the rest | The whole queue with source turns, across cycles and verification | Nothing automatically; a task leaves the queue only when completed or withdrawn by the caller | One summary with each task's outcome; unfinished and withdrawn tasks as open items |
| No owned case matches | Stay in RESOLVE_INTENT: say no claim on this account matches, summarize the owned claims, and ask for other details. With no claims at all, say so and offer general support or a human. A lookup failure gets an outage response, never “no match”. Use the same wording when a caller-supplied case ID does not exist or belongs to someone else | The unmatched hints, marked no-match so they are not reused silently | No PROCESS_CASE for that task | Records “no matching claim found” with next steps |
| General insurance support, no case needed | Unverified: answer from approved generic guidance and stay in VERIFY_ID, with no cycle. Verified: RESOLVE_INTENT opens a general-service cycle, then PROCESS_CASE without a selected case. A generic question inside a case cycle stays in that cycle | Any identity evidence or case hints given alongside | Nothing | Verified: lists the general topics with no claim status. Unverified: none, because email needs verified authority |
| New request during POST_PROCESS | New cycle at RESOLVE_INTENT if verification is valid, otherwise VERIFY_ID | Every cycle's discussed facts | The unapproved preview. An approved summary not yet dispatched is cancelled and the caller told; one already dispatching or sent stays sent | Regenerated to include the new cycle, with fresh approval. If the earlier one was sent, offer an additional summary covering only the new discussion |
| Caller explicitly ends the chat or asks for a human | End: CLOSED, with no summary offer. Human: HANDOFF_PENDING, then HANDED_OFF or an honest unavailable response | Handoff package limited to current authority | Unapproved preview and pending questions | No new summary; an approved, queued one still dispatches |

A single message may satisfy multiple sequential gates. Persist each transition and its reason in order, but do not force four chat turns. Margaret's full sample can verify, resolve CL-2048, and receive a grounded answer in the first assistant reply after tools succeed.

## Turn processing and bounded AI contracts

1. Authenticate the session; validate input size and turn idempotency key; load the current revision. Default limits: 8,000 input characters, 12 recent turns, 60 turns per session, 30-minute idle verification expiry, and 8-hour maximum session age. These are proposed configurable demo defaults, not insurer policy.
2. In parallel, extract values with the generative model and classify the turn with Jev (see Fast classification with Jev), then merge into a strict TurnInterpretation: identity_candidates, corrections, intent_candidates, case_hints, scope_segments, emotion, requested_action, consent_candidate, and classifier_source. Reject unknown keys and unsupported enums. Confidence may trigger clarification but cannot grant authorization.
3. Apply all relevant slots, including future-phase hints. For mixed requests, retain identity information and answer the permitted portion while declining unrelated portions.
4. Let the deterministic reducer evaluate evidence and active prompt context. It returns an allowed action and required tool arguments. At most four sequential business transitions are allowed in one turn; no open-ended model/tool loop.
5. Execute tools through the gateway. Bind subject and tenant server-side, never from model-selected identifiers. Revalidate state revision and verification immediately before dispatch and before committing results.
6. Construct an AnswerPlan from authorized fact IDs, approved knowledge snippets, requested clarification, optional empathy, and next allowed action. The model chooses relevant facts and conversational organization.
7. Render material facts—status, reason, money, documents, dates, available actions, and delivery outcome—from server-controlled fact blocks. Free wording is allowed for acknowledgment and nonmaterial connective language; claims explanations use reviewed knowledge snippets or source-backed blocks. A model-based semantic check may detect extra unsupported statements but cannot prove grounding.
8. Validate the complete response before display. On invalid output, try one constrained repair, then use a safe template or ask clarification. Never stream unvalidated protected text; stream a neutral progress indicator instead.
9. Atomically record accepted state, response, and redacted audit event. Use optimistic concurrency; serialize conflicting turns and discard/recompute stale model results. Return the stored result on exact retry; reject reused idempotency keys with different content.

Allow one extraction call, one Jev classification request, and one response-planning call per normal turn, plus at most one repair. Proposed provider timeout: 15 seconds per call (1.5 seconds for Jev) and 35 seconds overall turn budget. On exhaustion, preserve state and provide a safe retry/handoff response. The extraction service may receive user-supplied PII only under the approved provider configuration; the response planner receives masked identity state and the minimum authorized claim facts.

Suggested tool contracts:

- verify_identity(evidence_ref, policy_hint) → verified receipt only for exactly one eligible match; otherwise a generic insufficient/mismatch result, with ambiguity recorded as an internal reason code; never returns a policyholder record to the model.
- check_representative_authority(session_context, representative_ref, subject_ref) → pending/approved/denied/revoked/timeout receipt; the fixture adapter replays consent_scenarios.json only in labeled demo mode.
- resolve_owned_cases(auth_context, normalized_hints) → authorized candidate summaries.
- read_case(auth_context, case_id) → versioned case facts after ownership check.
- read_guidance(case_type, document_codes, topic, business_date) → approved guidance with provenance and applicability.
- prepare_summary(auth_context, discussed_fact_ids, next_steps) → preview version and allowed destination reference.
- enqueue_summary(auth_context, preview_version, consent_ref, idempotency_key) → queued receipt; invoked by application code only.
- cancel_summary(session_context, preview_version) → cancelled or already-dispatching receipt.
- request_handoff(session_context, reason_code, permitted_summary) → pending/accepted/unavailable receipt.

Tool permissions: every call needs a valid session credential, and the gateway binds tenant and session server-side. The model never calls a tool directly; the reducer selects the call and the gateway enforces this table.

| Tool | Required authority | Phases | Other conditions |
|---|---|---|---|
| verify_identity | None; accepts an unverified or re-verifying session | VERIFY_ID | Not locked by the failed-attempt limit; rate limits apply |
| check_representative_authority | Representative identity established by the configured method; subject identified by three permitted fields under the unique-match rule | VERIFY_ID | Polling budget not exhausted |
| request_handoff | None; accepts an unverified session | Any | Package limited to current authority; an unverified session sends only verification status, caller-provided hints, and attempted steps |
| read_guidance, generic | None | Any | No case-derived arguments; approved generic guidance only |
| read_guidance, case-scoped | Verified authority | RESOLVE_INTENT, PROCESS_CASE, POST_PROCESS | Case owned by the subject and selected in the active cycle |
| resolve_owned_cases | Verified authority | RESOLVE_INTENT, PROCESS_CASE | Subject bound server-side, never from model output |
| read_case | Verified authority | RESOLVE_INTENT, PROCESS_CASE, POST_PROCESS | Ownership checked on every call |
| prepare_summary | Verified authority | POST_PROCESS | Fact IDs were disclosed to this subject in this session; successful fresh case read |
| enqueue_summary | Verified authority plus consent bound to this preview version, recipient, and session | POST_PROCESS | Application code only; dispatch checks are under Email consent and reliable side effects |
| cancel_summary | None beyond the session credential | Any | Same session; succeeds only before dispatch |

Verified authority means an unexpired VerificationReceipt for the subject, or an unexpired RepresentativeAuthority grant whose permitted actions cover the call.

The demo explains existing claims and next steps. Actual adjudication, payment changes, appeal submission, document upload, contact-data changes, and policy changes are outside the first release's capabilities. Requests for those actions get grounded instructions or a handoff; the assistant must not pretend the action happened.

## Fast classification with Jev

Jev is TypeSafe AI's “System One” model, released 15 September 2026 and described by TypeSafe as early access. It answers typed questions and never generates text. Use it for the per-turn categorical decisions below. Value extraction, claim resolution, and reply wording stay with the generative model; every gate stays in deterministic code.

Design facts, from [TypeSafe's documentation](https://docs.typesafe.ai/introduction/quickstart) as of 2026-09-28:

- Primitives: Choice (one of named options, each with criteria text) and Score (ordered levels) return a probability distribution and a confidence value; Noul returns the probability that a statement is true. Questions in one request run in parallel and in isolation, so no answer can depend on another.
- API: POST https://api.typesafe.ai/v1/systemone with a bearer key; Python SDK typesafe-sdk. Pin jev-1.13.0; the jev-latest alias moves when releases ship ([models](https://docs.typesafe.ai/models.md)).
- Limits: 64k tokens per request, 32k for state plus the longest question; 1,200 requests per minute.
- Vendor-reported cost and speed: $0.042 per million input tokens, free output, 70–500 ms end to end.
- Confidence is a statistic of the returned distribution. TypeSafe recommends domain-specific thresholds and acting automatically only at high confidence ([confidence](https://docs.typesafe.ai/confidence.md)).
- [Documented 1.13 weaknesses](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md): negations and scoping are read literally; it does not do arithmetic or counting; dates are read as text; accuracy falls as irrelevant context grows; adversarial text can move answers; one question should not hide several judgments.
- Data: TypeSafe states it does not train on customer data and offers zero data retention to enterprise customers. Security certifications are not documented in the pages reviewed; confirm them before real customer data is sent.

One Jev request per turn carries the questions for the current phase. Thresholds apply to confidence for Choice questions and to the returned probability for Noul questions.

| Question | Type | Options or statement | Asked in | Act at or above | Otherwise |
|---|---|---|---|---|---|
| scope | Choice | Caller's primary request: claim_support, general_insurance, verification_or_privacy, summary_preference, small_talk, unrelated | Every phase | 0.80 | Treat as in scope, do not count it as unrelated, and ask what the caller needs |
| emotion | Choice | neutral, frustrated, angry, anxious, confused | Every phase | 0.70 | Neutral, respectful wording |
| wants_human | Noul | “The caller asks to speak with a human representative.” | Every phase | 0.85: transfer | 0.40–0.85: ask whether they want a representative; below 0.40: no action |
| refuses_step | Noul | “The caller declines to give the requested information or to continue this step.” | While a step awaits the caller | 0.80 | Treat as not refused; explain why the step matters and ask once more |
| intent | Choice | denial_question, status_inquiry, document_submission, next_steps, general_claim_question, none | VERIFY_ID (stored as a hint) and RESOLVE_INTENT | 0.70 | Ask one clarifying question |
| followup_topic | Choice | status, denial_reason, amounts, appeal_deadline, documents_needed, the six claim_followup_guidance topics, other | PROCESS_CASE | 0.70 | Ask which topic the caller means; use claim_followup_fallback for other |
| summary_decision | Choice | send, skip, unclear | Only while exactly one summary question is active | send 0.95; skip 0.80 | Ask a yes/no question; never send |
| done | Noul | “The caller indicates they have no more questions.” | PROCESS_CASE | 0.85 | Ask whether there is anything else |

These thresholds are starting values; replace each with the value the evaluation report supports.

State sent to Jev: the latest caller message after deterministic redaction (emails, phone numbers, digit runs of four or more, and dates become [EMAIL], [PHONE], [DIGITS], and [DATE]), the phase name, and a fixed description of the active prompt looked up by active_prompt_id. Never send the assistant's actual text, claim facts, reference PII, or older turns; irrelevant context lowers accuracy.

Jev never decides identity, ownership, permissions, or phase transitions, and never handles dates, amounts, or counts. A summary_decision label is valid only under the consent-binding rules in Email consent and reliable side effects. Injection detection with Jev is telemetry only. A wrong scope label cannot unlock content: the response planner still answers only from authorized facts and approved snippets.

Run the Jev request in parallel with the extraction call. If Jev times out, errors, or has no configured key, use the extraction call's labels under the rules above and record classifier_source on the turn. Jev is optional, so the demo still needs only the generative model's token.

## Verification and representative edge cases

- Collect partial answers across turns without repeatedly asking for supplied fields. Accept any three of the five permitted fields; offer alternatives to SSN rather than insisting on it.
- Require exactly one eligible policyholder match. Eligible means in the session's tenant and not locked or flagged for assisted service. Evaluate every candidate from permitted-field lookups; no first-result or LIMIT 1 shortcuts. If more than one eligible record reaches three matching fields, ask for a permitted field not yet supplied; if none remains or the ambiguity persists, escalate to a human. Tell the caller only that another detail is needed. An ambiguous result is not a failed attempt. The supplied fixtures cannot produce this case, so test it with a test-only duplicate record.
- Normalize names using case/spacing/Unicode normalization and explicit stored aliases; do not authorize based on unrestricted fuzzy matching. Reject invisible control-character ambiguity. DOB must resolve unambiguously; clarify dates such as 03/04/1985. Normalize phone country code only when known; do not guess. Trim email and normalize domain while preserving local-part semantics unless an explicit alias exists. Preserve leading zeroes in SSN last four.
- Repetition and aliases count as one field. Three matching fields across different people do not verify anybody.
- Conflicting active evidence blocks verification even if three other fields happen to match. Allow the user to explicitly correct or withdraw a mistaken value, retaining the attempt history for throttling.
- A lookup miss and mismatch produce neutral feedback that does not confirm whether a policy or particular field exists. Do not show a per-field match scoreboard to the caller.
- Proposed demo threshold: after three failed completed verification submissions, stop automated matching for that session and offer a human. Clarifications, incomplete answers, and refusals are not failed matches. Apply independent IP/session abuse controls; do not let an attacker permanently lock a policyholder just by naming their policy number.
- National-ID fixture values are not silently treated as SSNs. Use name/DOB/phone/email instead; add national ID only through an explicit future policy version.
- David Chen's fixture relationship does not authorize him to see Margaret's claims. A live representative flow requires representative authentication plus independently established authority from the insurer or policyholder. The fixture adapter may simulate approved/timeout authority only in visibly labeled demo mode.
- Pending, expired, denied, revoked, and unavailable authorization all keep the disclosure gate closed. Poll only within a finite budget; offer human assistance on timeout.

## Scope, empathy, and recovery policy

In scope: verification and privacy explanations, claim status, denial explanations, required documents, submission guidance, timing supported by sources, insurer terminology needed for the case, summary preferences, and human assistance. Small talk and frustration are conversational, not violations. A question about a medical term appearing in the denial is evaluated in its claim context; the system does not diagnose or give treatment advice.

First unrelated request: briefly decline and return to the active task. Second consecutive unrelated request: offer a human representative. Third: stop trying to answer unrelated requests and offer continue-with-claims, handoff, or end. Reset the consecutive counter when the caller returns to a substantive in-scope request. Mixed messages count as unrelated only if the primary request is unrelated; still retain valid identity/intent information. These thresholds are configurable and explicitly tested.

Recovery sequence: acknowledge emotion → explain the immediate reason for the requirement → offer one achievable next action or alternative. Do not claim to know exactly how the caller feels. Do not punish frustration with stricter verification. If an emotion classifier is uncertain, use neutral respectful wording.

Example before verification: “I understand this is frustrating. I need to verify your identity before I can discuss protected claim details. You can use your date of birth, phone number, or email instead of the last four digits of your SSN.” Adapt this to fields actually missing; never imply that fewer than three fields will suffice.

After two explicit refusals to continue verification, stop persuading and offer human assistance or ending the chat. A direct human request is honored immediately, without making the user complete verification first; transfer does not grant claim access. The handoff package contains the verification status, user-provided hints, attempted steps, and only facts permitted by the current authority. If no representative is available, say so and provide only a configured channel or genuinely supported callback option.

## Grounding and fixture normalization

Preserve the original fixtures. Create a validated import layer and a separate versioned policy/guidance overlay.

- Margaret's denied January healthcare claim resolves to CL-2048. January alone can match CL-2011 too; clarify if status/year does not disambiguate.
- Introduce document codes PATHOLOGY_REPORT and PROVIDER_OFFICE_NOTE, mapping both claim labels and guidance labels to them. Do not infer that an original paper copy is mandatory solely because a guidance key says “original.”
- Convert decimal amount strings using Decimal, not binary floating point. Preserve the difference between allowed maximum, expected reimbursement, and finalized payment. A maximum allowed amount is not a promise of payment.
- Use a visible injected demo clock of 2026-03-01 for the happy path. Provide a current-date scenario for expired deadlines. Production uses the authoritative business clock; startup must reject a demo clock override in production mode.
- Claim-specific deadlines take precedence over generic submission timing. The fixture's “within a week” text must be treated as generic guidance, not a new appeal entitlement. If the deadline has passed or guidance conflicts, report the stored date and arrange human review without promising an extension or declaring that no options remain.
- Review durations such as “usually less than a week” remain estimates, not guarantees. Missing documents do not automatically reverse a denial; receipt is not approval.
- Generic guidance does not provide a real portal URL, mailing address, or fax number. Do not invent any. The demo must clearly identify simulated actions.
- P7 and P13 have no claim records in the supplied file. Treat an authorized empty result as “no matching claims in this system,” distinct from a claims-service outage.
- The supplied consent sequences do not define their business purpose. Document the demo mapping to representative authorization; keep email summary consent as a separate object and state machine.
- No claim outcome can be inferred from missing optional fields. Unsupported questions result in explicit uncertainty and a next step, not invented policy.
- CL-3001's “diagnosis report” maps to DIAGNOSIS_REPORT, which has no document-specific guidance; use the default and healthcare guidance. Auto guidance (repair estimate, scene photos) applies to no supplied claim, and CL-2102 lists no documents, so never present those items as required.
- The claim_followup_guidance templates all set requires_documents: true. Use them only when the case lists documents; fill {case_id}, {documents}, and {average_processing_time_after_submission} server-side, and never render an empty or unfilled placeholder. Otherwise use claim_followup_fallback.
- Select a follow-up topic by classification (see Fast classification with Jev), not by match_any keywords, which overlap: “how soon” and “how long” belong to processing_time_after_submission, so keyword routing sends “how long do I have to submit?” to the wrong answer. Use match_any phrases only as examples in the topic criteria.
- The fixtures come from an audio-agent demo (claim_schema.json), so extraction accepts spoken forms such as “four four seven two” and “margaret at email dot com”; the verifier still compares normalized values.
- P13 has a primary email and an alias. The primary is the summary destination; the alias counts only as verification evidence.

## Email consent and reliable side effects

Generate a structured preview from actually discussed, authorized facts: topics discussed, current claim status/outcome from the pre-summary re-read (see Claim-data freshness), required documents, major next steps, and any unresolved items. Exclude DOB, SSN, verification answers, emotion labels, and unnecessary clinical details. Summarize the conversation outcome accurately: explaining a denial does not mean the denial was resolved.

Offer “Send summary” and “Skip” buttons plus natural-language equivalents. Bind a free-text affirmative to exactly one active unambiguous consent question; “yes” after multiple questions requires clarification. An early “email me later” is remembered as a preference and followed by approval of the eventual preview. “Don't send,” silence, timeout, and closing the browser are not approval. Approved/skipped consent is not repeatedly requested unless the user changes their mind or the content/recipient changes.

Use the approved email address on record, display it masked, and require an independently verified contact-change process for a new address. Having typed an email as a matching PII field does not establish control of a new mailbox.

Record the consent and outbox job in the same database transaction. Give each send intent a unique session/preview/recipient/consent key. The worker rechecks authority revocation, identity correction, consent expiry, cancellation, and content version before dispatch; idle expiry of the verification receipt after approval does not cancel an approved send. Changing summary content or recipient invalidates prior approval. Cancellation succeeds before dispatch; once dispatch begins or the provider has accepted it, do not promise recall.

Track queued, dispatching, provider_accepted, delivered, failed, unknown, and cancelled separately. Only say delivered when a verified delivery event supports it. A provider timeout after a possibly accepted send produces unknown status: reconcile by provider key/status rather than blindly sending again. Configure a real provider with idempotency or reconciliation support; otherwise require manual resolution of uncertain sends. Never promise exactly-once email delivery end-to-end.

This uses the [transactional outbox pattern](https://docs.aws.amazon.com/en_en/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) to coordinate database state with asynchronous work. Delivery can still be repeated downstream, so consumer/provider deduplication and uncertainty handling are separate requirements.

## Security, privacy, and operations

- Model API key supplied through server environment/secret manager, never browser storage or client bundles. Require MODEL_PROVIDER, MODEL_NAME, MODEL_API_KEY, DATABASE_URL, and APP_MODE. Optional TYPESAFE_API_KEY and CLASSIFIER_MODEL (a pinned version such as jev-1.13.0) enable Jev; without them the generative model's labels are used, so the demo still runs with one model token. Provider base URLs are operator configured and allowlisted, not supplied by chat users.
- Protect session APIs with opaque session credentials, secure HTTP-only cookies where applicable, origin/CSRF controls, rate limits, and input limits. Treat all model text, user text, and retrieved notes as untrusted; render sanitized text/Markdown with remote image loads disabled.
- Separate workflow capabilities from ordinary tools. No shell, arbitrary URL fetch, SQL generation, cross-user search, or unscoped email tools exposed to the model.
- Keep identity verification reference data out of model context. Untrusted fixture or claim-note instructions never override workflow policy. Model refusal or schema failure preserves state.
- Protect the production debug interface with operator authentication and field-level access controls. The public demo inspector shows phase, reason codes, masked memory, permitted actions, and redacted tool receipts—not reference PII, raw prompts, hidden reasoning, secrets, or other customers' records.
- Use PostgreSQL authorization scoping plus row-level policies for tenant isolation. The runtime role must not be a superuser, table owner, or BYPASSRLS role; set/reset tenant context transactionally when using pooled connections. Test under the actual runtime role. [PostgreSQL documents these RLS bypass conditions](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).
- Proposed demo retention: encrypted active conversation data deleted after 24 hours; raw supplied verification values purged after verification or session closure; redacted decision audit retained seven days. Keep only protected verification receipts after verification. Production retention and provider handling require the insurer's approved policy; redact transcript copies and backups consistently.
- Instrument phase transitions, latency, retries, verification failure categories, scope refusals, human-request completion, model/schema failures, provider spend, grounding fallbacks, outbox age, and email unknown outcomes. Avoid PII and identifiers in metric labels.
- Version prompts, policy, fixtures, knowledge, model selection, and evaluations together. Store explicit rule IDs and tool receipts for decisions; do not log or demand model chain-of-thought.
- Add health/readiness checks, database migrations, bounded retries with jitter for safe read operations, circuit breakers, graceful shutdown, restore tests, and alerts. Disable risky side effects via an operator kill switch while preserving safe explanations and human routing.
- Real-customer rollout requires configured and tested identity/claims/email/handoff adapters, access review, approved data handling and model-provider terms, staff ownership of escalations, incident response, and operational review. Do not market the demo as a compliance certification.

## API and file boundaries

Public endpoints: POST /sessions; POST /sessions/{id}/turns with turn_id and expected_revision; GET /sessions/{id} for authorized safe state/resume; POST /sessions/{id}/summary-decision referencing an active preview; POST /sessions/{id}/handoff; GET /health/live and /health/ready. Authenticate every session-specific endpoint. Internal worker/provider webhook endpoints require service authentication and replay protection.

Suggested layout:

```text
insurance_claims/
  fixtures/                         # original supplied data, unchanged
  apps/web/src/                     # chat, consent preview, accessible demo inspector
  services/api/app/
    contracts/                     # state, interpretation, tool and response schemas
    workflow/                      # reducer, guards, lifecycle, recovery, policy versions
    identity/                      # field normalization, matching, receipts, authority
    claims/                        # owned-case resolution, decimal/date/document mapping
    conversation/                  # extraction, memory merge, scope, response planning
    classifier/                    # Jev questions, thresholds, redaction, fallback to model labels
    tools/                         # gateway and fixture/production adapter interfaces
    summaries/                     # preview, consent binding, delivery state machine
    persistence/                   # repository, migrations, redacted audit, outbox
    api/                           # session auth, endpoints, errors, safe views
    worker/                        # outbox dispatch and reconciliation
  policies/                        # explicit defaults, capability tables, guidance overlay
  tests/unit/                      # normalization, guards, reducers, response blocks
  tests/integration/               # API auth, database isolation, worker behavior
  tests/conversations/             # human-written multi-turn scripts and assertions
  tests/adversarial/               # bypass, injection, leakage, race and replay tests
  evals/                           # versioned datasets, live-model runner, score reports
  deploy/                          # Dockerfiles, Compose, health checks
  docs/                            # design, setup, policy decisions, operations
```

## Delivery sequence and acceptance gates

Each milestone should be reviewable and runnable before proceeding. Write meaningful failing tests for gates and failure behavior, implement the owning module, and run its focused checks. This is an architecture/delivery plan; detailed code patches and dependency versions are selected at implementation time.

| Milestone | Deliverable and owning files | Acceptance gate |
|---|---|---|
| 1. Fixture and policy foundation | contracts/, policies/, claims/ importer, identity/ normalization | All six fixtures validate; document aliases resolve; date and Decimal behavior tested; national ID cannot count as SSN; original fixtures unchanged |
| 2. Deterministic workflow kernel | workflow/, persistence/, tests/unit/ | Gates pass without a model; generated event sequences cannot disclose before verification, cross subjects, or send without consent; corrections invalidate receipts; every row of the resumption and interrupted-workflow tables tested |
| 3. Authorized identity and claim tools | identity/, tools/, claims/, API session boundaries | Partial/corrected evidence works; three distinct fields matching exactly one eligible record required; each tool's permission row tested, including unverified verify/handoff; owner scoping and forged case IDs tested; claim changes and failed re-reads handled; representative pending/timeout remains blocked |
| 4. Bounded AI conversation | conversation/, classifier/, versioned prompts, tests/conversations/ | Margaret's exact utterance resolves CL-2048 without reasking the intent; partial answers, emotion, scope, ambiguity, and provider errors behave correctly; invalid model output cannot change authority; Jev thresholds come from the evaluation report and fallback to model labels is tested |
| 5. Summary and human recovery | summaries/, worker/, handoff adapter | Send/skip and ambiguous yes tested; modified preview requires consent again; duplicate requests and provider uncertainty cannot cause blind resend; unavailable human never reported as connected |
| 6. Demo UI and packaging | apps/web/, deploy/, .env.example, README | Fresh Docker start with model token; all four phases visible; reset/reconnect works; Mailpit shows approved summary only; keyboard and narrow-screen flows usable; public inspector redacted |
| 7. Evaluation and operational hardening | evals/, tests/adversarial/, telemetry, runbook | Critical deterministic suite passes; live-model quality thresholds met; failure injection, load, restoration, and secret scans pass; release report identifies remaining limitations |

Do not defer the workflow kernel, ownership checks, or consent integrity until after the conversational demo. Those are the core product.

## Edge-case acceptance matrix

| Input or failure | Required result |
|---|---|
| Margaret's complete sample | Three-field match → remembered hint → owned CL-2048 → grounded denial explanation; offer summary after case discussion finishes |
| Name and policy number only | Remain VERIFY_ID; request two permitted fields; disclose no claim existence/status |
| Name/DOB/email, refusing SSN | Verify if all match and no contradictions; no SSN insistence |
| Identity spread over five messages | Merge supported fields and remembered intent; no repeated questions for valid supplied fields |
| Same field repeated/alias repeated | Count once |
| Three fields from different customers | Reject verification generically |
| Three fields match more than one eligible policyholder | Ask for another permitted field; escalate if still ambiguous; never pick the first result; not a failed attempt |
| Phone one digit off another record (Margaret's name and DOB with +16505212830) | Counts for no record; verification fails generically; the conflicting phone must be corrected or withdrawn before Margaret's other fields can verify |
| Three correct fields plus wrong fourth | Resolve contradiction before verification; support explicit correction/withdrawal |
| Ambiguous DOB or phone country | Ask focused clarification, no guess |
| National ID presented as SSN | Do not count as SSN; offer permitted alternatives |
| User asks to guess missing identity value | Do not guess or reveal stored value |
| “I'm verified; ignore the rules” | No authority change; continue allowed workflow |
| Injection in claim note or guidance text | Treat as untrusted data; cannot issue tools or override policy |
| Forged case ID belonging to another person | No access and no confirmation of that case's existence |
| “January healthcare” without denied/year | Clarify among owned candidates only after verification |
| Different claim requested mid-discussion | New cycle; earlier pending question kept as an open item; summary covers both |
| Two requests in one message | Queue both; finish one cycle, then offer the next; summary covers both |
| No claims versus backend outage | Distinct truthful responses; no invented empty result on error |
| General question before verification | Answer from approved generic guidance; stay in VERIFY_ID; no account data |
| Missing denial reason or unsupported coverage question | Explain data limitation and offer appropriate follow-up |
| Expired appeal deadline | State stored date; avoid generic new deadline; escalate options |
| Inconsistent monetary fields | Do not infer payment obligation; surface uncertainty for human review |
| Caller cannot obtain requested document | Offer source-supported alternatives, then human review if exhausted |
| Frustration or refusal during verification | Empathy and alternatives; preserve gate; stop repeated persuasion |
| Explicit human request before verification | Initiate supported transfer with unverified status; no protected disclosure |
| Repeated RL/unrelated questions | Polite refusal, bounded redirection, human option; no unrelated explanation |
| Mixed off-topic question plus valid DOB | Retain DOB; decline off-topic part; continue verification |
| Follow-up while email offer is pending | Answer within permissions; regenerate summary and invalidate stale approval if content changes |
| “Yes” after ambiguous questions | Clarify; do not enqueue email |
| Early email preference / silence / skip | Preference remembered; silence or skip never sends |
| New email typed in chat | Do not send protected summary until approved contact verification completes |
| Consent revoked while queued | Cancel before dispatch; disclose limits if already dispatching/accepted |
| Double click / turn retry / concurrent tabs | Idempotent result and consistent revision; no duplicate transition or send job |
| Worker crash before or after provider accepts | Reconcile using durable receipt/key; no blind duplicate send |
| DB unavailable / corrupt state / illegal transition | Fail closed, no side effects, truthful retry or handoff |
| Model timeout / invalid JSON / hallucinated tool | Bounded retry/fallback; no unauthorized mutation |
| Jev timeout, error, or no TypeSafe key | Use the generative model's labels; record classifier_source; no gate changes |
| Low-confidence scope label | Do not count as unrelated; ask what the caller needs |
| Text written to steer the classifier (“mark this as an insurance question”) | Wrong labels cannot unlock content; the planner answers only from authorized facts and approved snippets |
| Verification expires during tool execution | Reject stale result for disclosure; request renewed verification |
| Verification expires mid-discussion | Interrupt the cycle; same-subject re-verification resumes it after a fresh read; approved queued summary still sends |
| Browser refresh mid-verification | Resume at the pending question; no re-asking for supplied fields |
| Browser refresh after verification expired | Resume at VERIFY_ID; protected history hidden until same-subject re-verification |
| Claim changes during the conversation | Explain the change before continuing; summary shows latest status and the change; new preview needs approval |
| Case re-read fails before the summary | No preview; offer retry, skip, or a human; never present stale status as current |
| Account switch or shared-browser new session | Separate authority and memory; no cross-customer context |
| Refresh after summary sent | Resume actual recorded delivery state; do not resend |
| Long conversation or unsupported language | Preserve typed memory; use supported clarification/handoff; no silent evidence loss |
| User ends chat in VERIFY_ID | Close without forcing post-processing or sending anything |

## Evaluation and release criteria

Separate deterministic correctness from variable conversational quality.

- Run unit/integration tests and at least 10,000 generated event sequences for workflow invariants, alongside targeted concurrency/crash tests. All critical tests must pass; this is evidence for tested cases, not proof against every possible attack.
- Maintain at least 100 human-authored multi-turn scenarios spanning the matrix, with several paraphrases each. Record expected phase, matched field categories, authorized subject/case, allowed tools, grounded fact IDs, consent state, and forbidden outputs at each turn.
- Test adversarial text in user turns, persisted hints, claim notes, and tool responses. Include Unicode variations, role spoofing, fake tool receipts, requests for another customer, malicious URLs, repeated persuasion, and “send now” before consent.
- Run live-model evaluations on every model/prompt/policy change. Repeat critical conversations five times at the shipped settings. A forbidden disclosure, unauthorized action, unsupported material fact, or consent bypass in any evaluated run blocks release and requires a fix plus regression case.
- Evaluate each Jev question separately on labeled caller turns from the scenario suite, including adversarial phrasings: accuracy, confusion matrix, and accuracy by confidence band, compared with the generative model's labels on the same turns. Set each threshold to the lowest value that meets the precision target, and keep Jev for a question only where it matches or beats the model at that threshold. Re-run on any classifier version change.
- Proposed quality targets: at least 95% successful completion on supported happy/recovery scenarios; at least 95% scope-routing precision and recall on a balanced evaluation set; at least 90% human-rated acceptable empathy/naturalness. Report sample sizes and uncertain cases. Do not rely solely on an LLM judge for factual or security assertions.
- Proposed performance target: p95 end-to-end response under eight seconds at 20 concurrent conversations with the selected provider in staging. Measure and publish per-turn token/cost distributions; provider choice and network may require revising the target before release.
- Capture response-grounding violations, unnecessary re-asking, mistaken refusals, handoff loops, and email delivery ambiguity as separate metrics. Add discovered production failures to the regression suite.
- Roll out synthetic demo → internal evaluation → restricted pilot with staffed handoff → measured expansion. Keep policy/model rollback and side-effect disable controls available at every stage.

## Final deliverables

Docker Compose demo; browser chat and redacted workflow inspector; server-side model token setup; fixture adapters and clearly simulated authority/handoff; local email inbox; send/skip workflow; automated tests and reproducible live-model evaluation command; architecture and policy decision docs; setup/troubleshooting README; and a production adapter/operations checklist.

The exact production authentication method, representative-authority source, retention schedule, approved claim knowledge, real email delivery policy, and staffed handoff integration require insurer decisions before real customer data is enabled. The demo defaults above make implementation concrete without pretending those business policies are already supplied.
