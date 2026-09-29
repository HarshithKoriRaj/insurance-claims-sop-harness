import { useEffect, useState } from 'react'
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

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    return err.detail || `Request failed (${err.status}).`
  }
  if (err instanceof Error) {
    return err.message
  }
  return 'Something went wrong. Please try again.'
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [view, setView] = useState<SessionView | null>(null)
  const [booting, setBooting] = useState(true)
  const [bootError, setBootError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
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
    try {
      const { view: newView } = await postMessage(sessionId, token, text)
      setView(newView)
    } catch (err) {
      await handleMutationError(err, text)
    } finally {
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
      <div className="app app--boot">
        <p>Loading&#8230;</p>
      </div>
    )
  }

  if (bootError || !view || !sessionId || !token) {
    return (
      <div className="app app--boot">
        <div className="boot-error">
          <h1>Claims Assistant</h1>
          <p role="alert">{bootError ?? 'Could not load a conversation.'}</p>
          <button type="button" className="button" onClick={() => void bootstrap()}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  const canRequestHuman = view.available_actions.includes('request_human')
  const canEndConversation = view.available_actions.includes('end_conversation')

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__row">
          <h1 className="app-header__title">Claims Assistant</h1>
          <button type="button" className="button button--secondary" onClick={() => void handleNewConversation()}>
            New conversation
          </button>
        </div>
        <PhaseStepper phase={view.phase} />
      </header>

      {view.lifecycle === 'HANDOFF_PENDING' && (
        <div className="banner banner--info" role="status">
          A human representative has been requested. In this demo the transfer is simulated.
        </div>
      )}

      {view.lifecycle === 'CLOSED' && (
        <div className="banner banner--closed" role="status">
          <span>This conversation has ended.</span>
          <button type="button" className="button" onClick={() => void handleNewConversation()}>
            Start a new conversation
          </button>
        </div>
      )}

      <div className="layout">
        <main className="chat-column">
          {(canRequestHuman || canEndConversation) && (
            <div className="actions-row" role="group" aria-label="Conversation actions">
              {canRequestHuman && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => void handleAction('request_human')}
                  disabled={pending}
                >
                  Talk to a human
                </button>
              )}
              {canEndConversation && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => void handleAction('end_conversation')}
                  disabled={pending}
                >
                  End conversation
                </button>
              )}
            </div>
          )}

          <Chat
            messages={view.messages}
            pending={pending}
            disabled={view.lifecycle === 'CLOSED'}
            draft={draft}
            onDraftChange={setDraft}
            onSend={() => void handleSend()}
            footerSlot={
              <SummaryCard
                summary={view.summary}
                pending={pending}
                onSendSummary={() => void handleAction('send_summary')}
                onSkipSummary={() => void handleAction('skip_summary')}
              />
            }
          />
        </main>

        <Inspector view={view} />
      </div>

      {errorMessage && (
        <div className="toast" role="alert">
          <span>{errorMessage}</span>
          <button
            type="button"
            className="toast__dismiss"
            onClick={() => setErrorMessage(null)}
            aria-label="Dismiss error"
          >
            &times;
          </button>
        </div>
      )}
    </div>
  )
}
