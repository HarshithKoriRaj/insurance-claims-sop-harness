import type { SessionView } from './api'

interface SummaryCardProps {
  summary: SessionView['summary']
  pending: boolean
  onSendSummary: () => void
  onSkipSummary: () => void
}

export default function SummaryCard({ summary, pending, onSendSummary, onSkipSummary }: SummaryCardProps) {
  if (summary.status === 'none') {
    return null
  }

  return (
    <section className="summary-card" aria-label="Conversation summary">
      {summary.status === 'offered' && (
        <>
          <h2 className="summary-card__title">Summary ready</h2>
          {summary.subject && (
            <p className="summary-card__subject">
              <strong>Subject:</strong> {summary.subject}
            </p>
          )}
          <pre className="summary-card__body">{summary.body ?? ''}</pre>
          <p className="summary-card__recipient">
            Will be sent to: {summary.recipient ?? 'the policyholder'}
          </p>
          <div className="summary-card__actions">
            <button type="button" className="button" onClick={onSendSummary} disabled={pending}>
              Send summary
            </button>
            <button
              type="button"
              className="button button--secondary"
              onClick={onSkipSummary}
              disabled={pending}
            >
              Skip
            </button>
          </div>
        </>
      )}

      {summary.status === 'sent' && (
        <p className="summary-card__status">
          {summary.delivered
            ? `Summary emailed to ${summary.recipient ?? 'the policyholder'}.`
            : 'Summary recorded. This deployment has no mail server, so it was not delivered to an inbox.'}
        </p>
      )}

      {summary.status === 'skipped' && <p className="summary-card__status">Summary not sent.</p>}
    </section>
  )
}
