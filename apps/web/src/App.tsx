import { useEffect, useState } from 'react'
import { CircleAlert, RotateCcw, ShieldCheck, X } from 'lucide-react'
import {
  ApiError,
  createSession,
  getSession,
  loadStoredSession,
  postAction,
  postMessage,
  saveStoredSession,
} from './api'
import type { ActionType, SessionView } from './api'
import PhaseStepper from './PhaseStepper'
import Chat from './Chat'
import SummaryCard from './SummaryCard'
import Inspector from './Inspector'
import GitHubMark from './GitHubMark'
import { formatBusinessDate } from './format'

const SOURCE_URL = 'https://github.com/HarshithKoriRaj/insurance-claims-sop-harness'

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    return err.detail || `Request failed (${err.status}).`
  }
  if (err instanceof Error) {
    return err.message
  }
  return 'Something went wrong. Please try again.'
}

function BrandMark({ large = false, loading = false }: { large?: boolean; loading?: boolean }) {
  const classes = ['brand__mark', large ? 'brand__mark--lg' : '', loading ? 'is-loading' : '']
  return (
    <span className={classes.filter(Boolean).join(' ')} aria-hidden="true">
      <ShieldCheck size={large ? 26 : 20} strokeWidth={2.25} />
    </span>
  )
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [view, setView] = useState<SessionView | null>(null)
  const [booting, setBooting] = useState(true)
  const [bootError, setBootError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [sendingText, setSendingText] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function applyNewSession(): Promise<void> {
    const created = await createSession()
    saveStoredSession({ session_id: created.session_id, token: created.token })
    setSessionId(created.session_id)
    setToken(created.token)
    setView(created.view)
    setDraft('')
  }

  async function bootstrap(): Promise<void> {
    setBooting(true)
    setBootError(null)

    const stored = loadStoredSession()
    if (stored) {
      try {
        const { view: fetchedView } = await getSession(stored.session_id, stored.token)
        setSessionId(stored.session_id)
        setToken(stored.token)
        setView(fetchedView)
        setBooting(false)
        return
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 404) {
          setBootError(describeError(err))
          setBooting(false)
          return
        }
        // Stored session/token is unknown or invalid — fall through and start fresh.
      }
    }

    try {
      await applyNewSession()
    } catch (err) {
      setBootError(describeError(err))
    }
    setBooting(false)
  }

  // Run once on mount: this reads whatever session is in localStorage (if any)
  // at load time and otherwise creates a new one.
  useEffect(() => {
    void bootstrap()
  }, [])

  /** Shared recovery for 404 (unknown session) and 409 (stale session) responses. */
  async function handleMutationError(err: unknown, restoreDraft?: string): Promise<void> {
    if (restoreDraft !== undefined) {
      setDraft(restoreDraft)
    }

    if (err instanceof ApiError && err.status === 404) {
      setErrorMessage('This conversation could not be found, so a new one was started.')
      try {
        await applyNewSession()
      } catch (innerErr) {
        setErrorMessage(describeError(innerErr))
      }
      return
    }

    if (err instanceof ApiError && err.status === 409 && sessionId && token) {
      setErrorMessage('The conversation had changed. Refreshed to the latest state — please try again.')
      try {
        const { view: freshView } = await getSession(sessionId, token)
        setView(freshView)
      } catch (innerErr) {
        if (innerErr instanceof ApiError && innerErr.status === 404) {
          try {
            await applyNewSession()
          } catch (innerErr2) {
            setErrorMessage(describeError(innerErr2))
          }
        } else {
          setErrorMessage(describeError(innerErr))
        }
      }
      return
    }

    setErrorMessage(describeError(err))
  }

  async function handleSend(): Promise<void> {
    if (!sessionId || !token || !view) return
    const text = draft.trim()
    if (!text || pending || view.lifecycle === 'CLOSED') return

    setPending(true)
    setDraft('')
    setSendingText(text)
    try {
      const { view: newView } = await postMessage(sessionId, token, text)
      setView(newView)
    } catch (err) {
      setSendingText(null)
      await handleMutationError(err, text)
    } finally {
      setSendingText(null)
      setPending(false)
    }
  }

  async function handleAction(action: ActionType): Promise<void> {
    if (!sessionId || !token || pending) return

    setPending(true)
    try {
      const { view: newView } = await postAction(sessionId, token, action)
      setView(newView)
    } catch (err) {
      await handleMutationError(err)
    } finally {
      setPending(false)
    }
  }

  async function handleNewConversation(): Promise<void> {
    if (pending) return
    setPending(true)
    try {
      await applyNewSession()
    } catch (err) {
      setErrorMessage(describeError(err))
    } finally {
      setPending(false)
    }
  }

  if (booting) {
    return (
      <div className="boot">
        <div className="boot__panel">
          <BrandMark large loading />
          <p className="boot__title">Claims Assistant</p>
          <p className="boot__text" role="status">
            Loading&#8230;
          </p>
        </div>
      </div>
    )
  }

  if (bootError || !view || !sessionId || !token) {
    return (
      <div className="boot">
        <div className="boot__panel card">
          <BrandMark large />
          <h1 className="boot__title">Claims Assistant</h1>
          <p className="boot__error" role="alert">
            {bootError ?? 'Could not load a conversation.'}
          </p>
          <button type="button" className="btn btn--primary" onClick={() => void bootstrap()}>
            <RotateCcw size={16} aria-hidden="true" />
            Retry
          </button>
        </div>
      </div>
    )
  }

  const canRequestHuman = view.available_actions.includes('request_human')
  const canEndConversation = view.available_actions.includes('end_conversation')
  const canSendSummary = view.available_actions.includes('send_summary')
  const canSkipSummary = view.available_actions.includes('skip_summary')

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__inner">
          <div className="brand">
            <BrandMark />
            <div className="brand__text">
              <h1 className="brand__title">Claims Assistant</h1>
              <p className="brand__subtitle">Insurance claims support · SOP demo</p>
            </div>
          </div>

          <div className="topbar__actions">
            <a className="btn btn--ghost" href={SOURCE_URL} target="_blank" rel="noopener noreferrer" title="View source">
              <GitHubMark size={16} />
              <span className="btn__label">View source</span>
              <span className="visually-hidden"> (opens in a new tab)</span>
            </a>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => void handleNewConversation()}
              title="New conversation"
            >
              <RotateCcw size={16} aria-hidden="true" />
              <span className="btn__label">New conversation</span>
            </button>
          </div>
        </div>
      </header>

      <main className="workspace">
        <PhaseStepper phase={view.phase} settled={view.lifecycle === 'CLOSED'} />

        <Chat
          messages={view.messages}
          phase={view.phase}
          lifecycle={view.lifecycle}
          modelMode={view.model_mode}
          summaryOffered={view.summary.status === 'offered'}
          canRequestHuman={canRequestHuman}
          canEndConversation={canEndConversation}
          pending={pending}
          sendingText={sendingText}
          draft={draft}
          onDraftChange={setDraft}
          onSend={() => void handleSend()}
          onRequestHuman={() => void handleAction('request_human')}
          onEndConversation={() => void handleAction('end_conversation')}
          onNewConversation={() => void handleNewConversation()}
          footerSlot={
            <SummaryCard
              summary={view.summary}
              pending={pending}
              canSend={canSendSummary}
              canSkip={canSkipSummary}
              onSendSummary={() => void handleAction('send_summary')}
              onSkipSummary={() => void handleAction('skip_summary')}
            />
          }
        />

        <Inspector view={view} />
      </main>

      <footer className="footer">
        <p>
          Demo data only. The business date is pinned to {formatBusinessDate(view.business_date)}; human handoff is
          simulated.
        </p>
      </footer>

      {errorMessage && (
        <div className="toast" role="alert">
          <CircleAlert className="toast__icon" size={18} aria-hidden="true" />
          <p className="toast__text">{errorMessage}</p>
          <button
            type="button"
            className="toast__dismiss"
            onClick={() => setErrorMessage(null)}
            aria-label="Dismiss error"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  )
}
