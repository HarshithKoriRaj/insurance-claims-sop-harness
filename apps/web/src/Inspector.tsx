import { useState } from 'react'
import {
  CalendarDays,
  Car,
  Check,
  ChevronDown,
  CircleCheck,
  CircleDashed,
  Cpu,
  EyeOff,
  FileText,
  HeartPulse,
  Sparkles,
  Stethoscope,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { CaseHints, Lifecycle, SessionView } from './api'
import { FIELD_LABELS, IDENTITY_FIELDS, MODEL_LABELS, formatBusinessDate, humanize, monthName } from './format'

// Shows workflow state only. Identity values never appear here: fields are
// listed by name, and the backend does not send the values in the first place.

type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'neutral'

const LIFECYCLE_TONE: Record<Lifecycle, Tone> = {
  ACTIVE: 'success',
  HANDOFF_PENDING: 'warning',
  CLOSED: 'neutral',
}

const CASE_ICONS: Record<string, LucideIcon> = {
  healthcare: HeartPulse,
  auto: Car,
  dental: Stethoscope,
}

function claimStatusTone(status: string): Tone {
  switch (status.toLowerCase()) {
    case 'denied':
      return 'danger'
    case 'open':
      return 'warning'
    case 'closed':
      return 'neutral'
    default:
      return 'primary'
  }
}

function hintTags(hints: CaseHints): Array<{ key: string; label: string; value: string }> {
  const tags: Array<{ key: string; label: string; value: string }> = []
  if (hints.case_id) tags.push({ key: 'case_id', label: 'Case', value: hints.case_id })
  if (hints.case_type) tags.push({ key: 'case_type', label: 'Type', value: humanize(hints.case_type) })
  if (hints.status) tags.push({ key: 'status', label: 'Status', value: humanize(hints.status) })
  if (typeof hints.month === 'number') tags.push({ key: 'month', label: 'Month', value: monthName(hints.month) })
  if (typeof hints.year === 'number') tags.push({ key: 'year', label: 'Year', value: String(hints.year) })
  return tags
}

function PrivacyBadge() {
  return (
    <span className="privacy-badge">
      <EyeOff size={13} aria-hidden="true" />
      No personal data
    </span>
  )
}

interface InspectorProps {
  view: SessionView
}

export default function Inspector({ view }: InspectorProps) {
  // Only matters below 900px, where the inspector collapses under the chat.
  const [open, setOpen] = useState(false)
  const { verification, selected_case: selectedCase, memory, recovery } = view

  const provided = new Set(verification.fields_provided)
  const providedCount = verification.fields_provided.length
  const required = verification.fields_required
  const percent = required > 0 ? Math.min(100, (providedCount / required) * 100) : 0
  const failed = verification.failed_attempts
  const attemptsTone: Tone = failed === 0 ? 'neutral' : failed >= verification.max_attempts ? 'danger' : 'warning'
  const tags = hintTags(memory.case_hints)
  const CaseIcon = (selectedCase && CASE_ICONS[selectedCase.case_type.toLowerCase()]) || FileText
  const ModelIcon = view.model_mode === 'offline' ? Cpu : Sparkles
  const businessDate = formatBusinessDate(view.business_date)

  return (
    <aside className={`inspector card${open ? ' is-open' : ''}`} aria-label="Session details">
      {/* Desktop header. The business date lives here so the whole panel fits on one screen. */}
      <div className="inspector__head">
        <div className="inspector__heading">
          <h2 className="inspector__title">Session</h2>
          <PrivacyBadge />
        </div>
        <p className="inspector__date">
          <CalendarDays size={13} aria-hidden="true" />
          Business date <strong>{businessDate}</strong>
        </p>
      </div>

      <button
        type="button"
        className="inspector__toggle"
        aria-expanded={open}
        aria-controls="inspector-body"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="inspector__toggle-label">Session details</span>
        <PrivacyBadge />
        <ChevronDown className="inspector__chevron" size={18} aria-hidden="true" />
      </button>

      <div id="inspector-body" className="inspector__body">
        <section className="ins-section" aria-labelledby="ins-status">
          <h3 id="ins-status" className="ins-section__title">
            Status
          </h3>
          <dl className="kv">
            <div className="kv__row">
              <dt>Phase</dt>
              <dd>
                <span className="pill pill--primary pill--mono">{view.phase}</span>
              </dd>
            </div>
            <div className="kv__row">
              <dt>Lifecycle</dt>
              <dd>
                <span className={`pill pill--${LIFECYCLE_TONE[view.lifecycle]} pill--mono`}>
                  <span className="pill__dot" aria-hidden="true" />
                  {view.lifecycle}
                </span>
              </dd>
            </div>
            <div className="kv__row">
              <dt>Model</dt>
              <dd>
                <span className={`pill pill--${view.model_mode === 'offline' ? 'warning' : 'primary'}`}>
                  <ModelIcon size={13} aria-hidden="true" />
                  {MODEL_LABELS[view.model_mode]}
                </span>
              </dd>
            </div>
          </dl>
        </section>

        <section className="ins-section" aria-labelledby="ins-verification">
          <div className="ins-section__head">
            <h3 id="ins-verification" className="ins-section__title">
              Verification
            </h3>
            {verification.verified ? (
              <span className="verify-state is-verified">
                <CircleCheck size={15} aria-hidden="true" />
                Verified
              </span>
            ) : (
              <span className="verify-state">
                <CircleDashed size={15} aria-hidden="true" />
                Not verified
              </span>
            )}
          </div>

          <div className={`meter${verification.verified ? ' is-complete' : ''}`}>
            <div
              className="meter__track"
              role="progressbar"
              aria-label="Identity fields provided"
              aria-valuemin={0}
              aria-valuemax={required}
              aria-valuenow={Math.min(providedCount, required)}
              aria-valuetext={`${providedCount} of ${required}`}
            >
              <span className="meter__fill" style={{ width: `${percent}%` }} />
            </div>
            <span className="meter__count" aria-hidden="true">
              {providedCount} of {required} fields
            </span>
          </div>

          <ul className="field-chips" aria-label="Identity fields">
            {IDENTITY_FIELDS.map((field) => {
              const isProvided = provided.has(field)
              return (
                <li key={field} className={`field-chip${isProvided ? ' is-provided' : ''}`}>
                  {isProvided ? (
                    <Check size={12} strokeWidth={3} aria-hidden="true" />
                  ) : (
                    <span className="field-chip__dot" aria-hidden="true" />
                  )}
                  {FIELD_LABELS[field]}
                  <span className="visually-hidden">{isProvided ? ', provided' : ', not provided'}</span>
                </li>
              )
            })}
          </ul>

          <p className="attempts">
            <span>Failed attempts</span>{' '}
            <span className={`pill pill--${attemptsTone} attempts__value`}>
              {failed} of {verification.max_attempts}
            </span>
          </p>
        </section>

        <section className="ins-section" aria-labelledby="ins-claim">
          <h3 id="ins-claim" className="ins-section__title">
            Selected claim
          </h3>
          {selectedCase ? (
            <div className="claim-card">
              <span className="claim-card__icon" aria-hidden="true">
                <CaseIcon size={18} />
              </span>
              <div className="claim-card__main">
                <p className="claim-card__id">{selectedCase.case_id}</p>
                <p className="claim-card__type">{humanize(selectedCase.case_type)} claim</p>
              </div>
              <span className={`pill pill--${claimStatusTone(selectedCase.status)}`}>
                {humanize(selectedCase.status)}
              </span>
            </div>
          ) : (
            <p className="empty-note">No claim selected yet</p>
          )}
        </section>

        <section className="ins-section" aria-labelledby="ins-memory">
          <h3 id="ins-memory" className="ins-section__title">
            Memory
          </h3>
          <dl className="kv">
            <div className="kv__row">
              <dt>Intent</dt>
              <dd>{memory.intent ? humanize(memory.intent) : <span className="kv__empty">None yet</span>}</dd>
            </div>
            <div className="kv__row">
              <dt>Follow-up topic</dt>
              <dd>
                {memory.followup_topic ? (
                  humanize(memory.followup_topic)
                ) : (
                  <span className="kv__empty">None</span>
                )}
              </dd>
            </div>
          </dl>
          {tags.length > 0 ? (
            <ul className="hint-tags" aria-label="Case hints">
              {tags.map((tag) => (
                <li key={tag.key} className="hint-tag">
                  <span className="hint-tag__key">{tag.label}</span> {tag.value}
                </li>
              ))}
            </ul>
          ) : (
            <p className="ins-note">No case hints yet</p>
          )}
        </section>

        <section className="ins-section" aria-labelledby="ins-recovery">
          <h3 id="ins-recovery" className="ins-section__title">
            Recovery
          </h3>
          <div className="counters">
            <div className={`counter${recovery.off_topic > 0 ? ' is-active' : ''}`}>
              <span className="counter__value">{recovery.off_topic}</span>
              <span className="counter__label">Off-topic</span>
            </div>
            <div className={`counter${recovery.refusals > 0 ? ' is-active' : ''}`}>
              <span className="counter__value">{recovery.refusals}</span>
              <span className="counter__label">Refusals</span>
            </div>
          </div>
        </section>

        {/* Phones only: the desktop header shows the business date instead. */}
        <section className="ins-section ins-section--compact-only" aria-labelledby="ins-session">
          <h3 id="ins-session" className="ins-section__title">
            Session
          </h3>
          <dl className="kv">
            <div className="kv__row">
              <dt>Business date</dt>
              <dd className="kv__with-icon">
                <CalendarDays size={14} aria-hidden="true" />
                {businessDate}
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </aside>
  )
}
