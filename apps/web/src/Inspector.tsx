import { useState } from 'react'
import type { IdentityField, SessionView } from './api'

const FIELD_LABELS: Record<IdentityField, string> = {
  full_name: 'Full name',
  dob: 'Date of birth',
  phone: 'Phone',
  email: 'Email',
  ssn_last4: 'SSN last 4',
}

const CASE_HINT_LABELS: Record<string, string> = {
  case_id: 'Case ID',
  case_type: 'Case type',
  status: 'Status',
  month: 'Month',
  year: 'Year',
}

interface InspectorProps {
  view: SessionView
}

export default function Inspector({ view }: InspectorProps) {
  const [open, setOpen] = useState(true)
  const { verification, selected_case: selectedCase, memory, recovery } = view

  const caseHintEntries = Object.entries(memory.case_hints).filter(
    (entry): entry is [string, string | number] => entry[1] !== null && entry[1] !== undefined,
  )

  return (
    <aside className="inspector">
      <button
        type="button"
        className="inspector__toggle"
        aria-expanded={open}
        aria-controls="inspector-panel"
        onClick={() => setOpen((value) => !value)}
      >
        <span>Session inspector (no personal data)</span>
        <span className="inspector__chevron" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
      </button>

      {open && (
        <div id="inspector-panel" className="inspector__panel">
          <section className="inspector__section">
            <h3>Status</h3>
            <dl className="inspector__dl">
              <div>
                <dt>Phase</dt>
                <dd className="mono">{view.phase}</dd>
              </div>
              <div>
                <dt>Lifecycle</dt>
                <dd>{view.lifecycle}</dd>
              </div>
            </dl>
          </section>

          <section className="inspector__section">
            <h3>Verification</h3>
            <p className={verification.verified ? 'status-ok' : 'status-pending'}>
              {verification.verified ? 'Verified' : 'Not verified'}
            </p>
            <ul className="chip-list">
              {verification.fields_provided.length === 0 && (
                <li className="chip chip--muted">None yet</li>
              )}
              {verification.fields_provided.map((field) => (
                <li key={field} className="chip">
                  {FIELD_LABELS[field] ?? field}
                </li>
              ))}
            </ul>
            <p>
              {verification.fields_provided.length} of {verification.fields_required} details
            </p>
            <p>
              Failed attempts: {verification.failed_attempts} of {verification.max_attempts}
            </p>
          </section>

          <section className="inspector__section">
            <h3>Selected case</h3>
            {selectedCase ? (
              <p>
                {selectedCase.case_type} &middot; {selectedCase.case_id} &middot; {selectedCase.status}
              </p>
            ) : (
              <p className="muted">None selected</p>
            )}
          </section>

          <section className="inspector__section">
            <h3>Memory</h3>
            <p>Intent: {memory.intent ?? 'None'}</p>
            <p>Follow-up topic: {memory.followup_topic ?? 'None'}</p>
            {caseHintEntries.length > 0 ? (
              <ul className="chip-list">
                {caseHintEntries.map(([key, value]) => (
                  <li key={key} className="chip">
                    {(CASE_HINT_LABELS[key] ?? key)}: {String(value)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No case hints yet</p>
            )}
          </section>

          <section className="inspector__section">
            <h3>Recovery</h3>
            <p>Off-topic: {recovery.off_topic}</p>
            <p>Refusals: {recovery.refusals}</p>
          </section>

          <section className="inspector__section">
            <h3>Session</h3>
            <p>Business date: {view.business_date}</p>
            <p>
              Model mode:{' '}
              <span className={`badge badge--${view.model_mode}`}>
                {view.model_mode === 'claude' ? 'Claude' : 'Offline rules'}
              </span>
            </p>
          </section>
        </div>
      )}
    </aside>
  )
}
