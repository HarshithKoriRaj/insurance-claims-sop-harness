import { CircleCheck, Mail, MailCheck, MailX, Send } from 'lucide-react'
import type { SessionView } from './api'

interface SummaryCardProps {
  summary: SessionView['summary']
  pending: boolean
  /** Whether `send_summary` / `skip_summary` are in `view.available_actions`. */
  canSend: boolean
  canSkip: boolean
  onSendSummary: () => void
  onSkipSummary: () => void
}

export default function SummaryCard({
  summary,
  pending,
  canSend,
  canSkip,
  onSendSummary,
  onSkipSummary,
}: SummaryCardProps) {
  if (summary.status === 'none') {
    return null
  }

  const recipient = summary.recipient ?? 'the policyholder'

  if (summary.status === 'offered') {
    return (
      <section className="summary" aria-label="Conversation summary">
        <header className="summary__head">
          <span className="summary__icon" aria-hidden="true">
            <Mail size={15} />
          </span>
          <h3 className="summary__title">Email summary</h3>
          <span className="summary__tag">Preview</span>
        </header>

        <div className="summary__meta">
          <p className="summary__row">
            <span className="summary__label">To:</span> <span className="summary__value">{recipient}</span>
          </p>
          {summary.subject && (
            <p className="summary__row">
              <span className="summary__label">Subject:</span>{' '}
              <span className="summary__value">{summary.subject}</span>
            </p>
          )}
        </div>

        <div className="summary__body" role="region" aria-label="Summary text" tabIndex={0}>
          {summary.body ?? ''}
        </div>

        {(canSend || canSkip) && (
          <div className="summary__actions">
            {canSend && (
              <button type="button" className="btn btn--primary" onClick={onSendSummary} disabled={pending}>
                <Send size={15} aria-hidden="true" />
                Send summary
              </button>
            )}
            {canSkip && (
              <button type="button" className="btn btn--secondary" onClick={onSkipSummary} disabled={pending}>
                Skip
              </button>
            )}
          </div>
        )}
      </section>
    )
  }

  if (summary.status === 'sent') {
    return (
      <section className="summary summary--result summary--sent" aria-label="Conversation summary">
        <span className="summary__result-icon" aria-hidden="true">
          {summary.delivered ? <MailCheck size={18} /> : <CircleCheck size={18} />}
        </span>
        <div className="summary__result-text">
          <p className="summary__kicker">Email summary</p>
          {summary.delivered ? (
            <p>
              <strong>Summary emailed to {recipient}.</strong>
            </p>
          ) : (
            <p>
              <strong>Summary recorded.</strong> This deployment has no mail server, so it was not delivered to an
              inbox.
            </p>
          )}
        </div>
      </section>
    )
  }

  return (
    <section className="summary summary--result summary--skipped" aria-label="Conversation summary">
      <span className="summary__result-icon" aria-hidden="true">
        <MailX size={18} />
      </span>
      <div className="summary__result-text">
        <p className="summary__kicker">Email summary</p>
        <p>
          <strong>Summary not sent.</strong> You chose to skip the email summary.
        </p>
      </div>
    </section>
  )
}
