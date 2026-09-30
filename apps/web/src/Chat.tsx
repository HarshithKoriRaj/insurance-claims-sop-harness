import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent, ReactNode } from 'react'
import { ArrowUp, CircleCheck, Headset, LogOut, RotateCcw, ShieldCheck, Sparkles } from 'lucide-react'
import type { Lifecycle, Message, ModelMode, Phase } from './api'
import MessageText from './MessageText'
import { MODEL_LABELS, formatClock } from './format'

const DEMO_MESSAGE =
  "I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied healthcare claim from January. DOB is 1985-03-15, SSN last four is 4472."

interface Suggestion {
  label: string
  text: string
  /** Accessible name, when it should say more than the visible label. */
  name?: string
  featured?: boolean
}

// A suggestion only fills the composer; it never sends.
const SUGGESTIONS: Record<Phase, Suggestion[]> = {
  VERIFY_ID: [
    // Also named "Try the demo": the README and existing scripts look for that button.
    { label: 'Demo: Margaret Chen', text: DEMO_MESSAGE, name: 'Try the demo: Margaret Chen', featured: true },
    { label: 'Off-topic: What is RL?', text: 'What is RL?' },
    { label: 'Refuse to share', text: "Why do you need my SSN? I don't want to give it." },
  ],
  RESOLVE_INTENT: [
    { label: 'The denied one', text: 'The denied one' },
    { label: 'My auto claim', text: 'What about my auto claim?' },
  ],
  PROCESS_CASE: [
    { label: "Can't get a document", text: "What if I can't get the pathology report?" },
    { label: 'How long?', text: 'How long does processing take after I submit?' },
    { label: 'Another claim', text: 'What about my auto claim?' },
    { label: "I'm done", text: "That's all, thanks." },
  ],
  // Only while the summary is offered; see suggestionsFor.
  POST_PROCESS: [
    { label: 'Yes, send it', text: 'Yes, send it' },
    { label: 'No thanks', text: 'No thanks' },
  ],
}

/** Size the composer to its content, from one line up to five, then scroll. */
function fitToContent(node: HTMLTextAreaElement) {
  node.style.height = 'auto'
  const styles = window.getComputedStyle(node)
  const lineHeight = Number.parseFloat(styles.lineHeight) || 22
  const padding = Number.parseFloat(styles.paddingTop) + Number.parseFloat(styles.paddingBottom)
  const maxHeight = lineHeight * 5 + padding
  node.style.height = `${Math.min(node.scrollHeight, maxHeight)}px`
  node.style.overflowY = node.scrollHeight > maxHeight ? 'auto' : 'hidden'
}

function suggestionsFor(phase: Phase, lifecycle: Lifecycle, summaryOffered: boolean): Suggestion[] {
  if (lifecycle !== 'ACTIVE') return []
  if (phase === 'POST_PROCESS' && !summaryOffered) return []
  return SUGGESTIONS[phase]
}

type StatusTone = 'online' | 'warning' | 'muted'

function connectionStatus(lifecycle: Lifecycle, modelMode: ModelMode): { tone: StatusTone; text: string } {
  if (lifecycle === 'CLOSED') return { tone: 'muted', text: 'Conversation ended' }
  if (lifecycle === 'HANDOFF_PENDING') return { tone: 'warning', text: 'Human requested' }
  if (modelMode === 'offline') return { tone: 'warning', text: 'Offline rules' }
  return { tone: 'online', text: `Online · ${MODEL_LABELS[modelMode]}` }
}

function AssistantAvatar() {
  return (
    <span className="avatar avatar--assistant" aria-hidden="true">
      <ShieldCheck size={15} strokeWidth={2.25} />
    </span>
  )
}

function MessageRow({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const time = formatClock(message.at)

  return (
    <div className={`msg msg--${message.role}`}>
      {!isUser && <AssistantAvatar />}
      <div className="msg__stack">
        <div className="msg__bubble">
          <span className="visually-hidden">{isUser ? 'You:' : 'Assistant:'}</span>
          <MessageText text={message.text} />
        </div>
        <div className="msg__meta">
          {time && <time dateTime={message.at}>{time}</time>}
          <span className="phase-pill">{message.phase}</span>
        </div>
      </div>
      {isUser && (
        <span className="avatar avatar--user" aria-hidden="true">
          You
        </span>
      )}
    </div>
  )
}

/** Echo of the message in flight, replaced by the server's copy when it replies. */
function SendingRow({ text }: { text: string }) {
  return (
    <div className="msg msg--user is-sending" aria-hidden="true">
      <div className="msg__stack">
        <div className="msg__bubble">
          <MessageText text={text} />
        </div>
        <div className="msg__meta">
          <span>Sending…</span>
        </div>
      </div>
      <span className="avatar avatar--user">You</span>
    </div>
  )
}

function TypingRow() {
  return (
    <div className="msg msg--assistant">
      <AssistantAvatar />
      <div className="msg__stack">
        <div className="msg__bubble typing">
          <span className="typing__dot" aria-hidden="true" />
          <span className="typing__dot" aria-hidden="true" />
          <span className="typing__dot" aria-hidden="true" />
          <span className="visually-hidden">Assistant is typing…</span>
        </div>
      </div>
    </div>
  )
}

interface ChatProps {
  messages: Message[]
  phase: Phase
  lifecycle: Lifecycle
  modelMode: ModelMode
  summaryOffered: boolean
  canRequestHuman: boolean
  canEndConversation: boolean
  pending: boolean
  /** The message being sent, shown until the server's reply arrives. */
  sendingText: string | null
  draft: string
  onDraftChange: (value: string) => void
  onSend: () => void
  onRequestHuman: () => void
  onEndConversation: () => void
  onNewConversation: () => void
  footerSlot?: ReactNode
}

export default function Chat({
  messages,
  phase,
  lifecycle,
  modelMode,
  summaryOffered,
  canRequestHuman,
  canEndConversation,
  pending,
  sendingText,
  draft,
  onDraftChange,
  onSend,
  onRequestHuman,
  onEndConversation,
  onNewConversation,
  footerSlot,
}: ChatProps) {
  const historyRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const refocusAfterSend = useRef(false)
  /** Whether the reader is at the bottom of the log (so a resize should keep them there). */
  const pinnedToBottom = useRef(true)
  const [focusRequest, setFocusRequest] = useState(0)

  const disabled = lifecycle === 'CLOSED'
  const canSend = !disabled && !pending && draft.trim().length > 0
  const status = connectionStatus(lifecycle, modelMode)
  const suggestions = suggestionsFor(phase, lifecycle, summaryOffered)
  const startedAt = messages.length > 0 ? formatClock(messages[0].at) : ''

  // Keep the newest message (or the typing indicator) in view.
  useEffect(() => {
    const node = historyRef.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [messages, pending, sendingText])

  // When the log changes size (window resize, a phone keyboard opening), stay at
  // the bottom if that's where the reader was.
  useEffect(() => {
    const node = historyRef.current
    if (!node || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => {
      if (pinnedToBottom.current) node.scrollTop = node.scrollHeight
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  function handleHistoryScroll() {
    const node = historyRef.current
    if (node) {
      pinnedToBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 48
    }
  }

  // Grow the composer with its content, and re-fit when a resize changes the wrapping.
  useLayoutEffect(() => {
    if (inputRef.current) fitToContent(inputRef.current)
  }, [draft])

  useEffect(() => {
    function handleResize() {
      if (inputRef.current) fitToContent(inputRef.current)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // The textarea is disabled while a reply is pending, which drops focus; give it back.
  useEffect(() => {
    if (!pending && !disabled && refocusAfterSend.current) {
      refocusAfterSend.current = false
      inputRef.current?.focus()
    }
  }, [pending, disabled])

  // After a suggestion fills the composer, focus it with the caret at the end.
  useEffect(() => {
    if (focusRequest === 0) return
    const node = inputRef.current
    if (!node || node.disabled) return
    node.focus()
    const end = node.value.length
    node.setSelectionRange(end, end)
  }, [focusRequest])

  function submit() {
    if (canSend) {
      refocusAfterSend.current = true
      onSend()
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  function applySuggestion(text: string) {
    onDraftChange(text)
    setFocusRequest((count) => count + 1)
  }

  return (
    <section className="chat card" aria-label="Conversation">
      <header className="chat__header">
        <div className="chat__identity">
          <span className="avatar avatar--assistant avatar--lg" aria-hidden="true">
            <ShieldCheck size={20} strokeWidth={2.25} />
          </span>
          <div className="chat__who">
            <h2 className="chat__name">Claims Assistant</h2>
            <p className={`chat__status is-${status.tone}`}>
              <span className="status-dot" aria-hidden="true" />
              {status.text}
            </p>
          </div>
        </div>

        {(canRequestHuman || canEndConversation) && (
          <div className="chat__actions" role="group" aria-label="Conversation actions">
            {canRequestHuman && (
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={onRequestHuman}
                disabled={pending}
                title="Talk to a human"
              >
                <Headset size={16} aria-hidden="true" />
                <span className="btn__label">Talk to a human</span>
              </button>
            )}
            {canEndConversation && (
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={onEndConversation}
                disabled={pending}
                title="End conversation"
              >
                <LogOut size={16} aria-hidden="true" />
                <span className="btn__label">End conversation</span>
              </button>
            )}
          </div>
        )}
      </header>

      {lifecycle === 'HANDOFF_PENDING' && (
        <div className="banner banner--handoff" role="status">
          <span className="banner__icon" aria-hidden="true">
            <Headset size={16} />
          </span>
          <p className="banner__text">
            <strong>A human representative has been requested.</strong> In this demo the transfer is simulated.
          </p>
        </div>
      )}

      <div
        className="chat__history"
        ref={historyRef}
        onScroll={handleHistoryScroll}
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-label="Messages"
        tabIndex={0}
      >
        {startedAt && (
          <p className="chat__divider" aria-hidden="true">
            <span>Conversation started · {startedAt}</span>
          </p>
        )}

        {messages.length === 0 && !pending && <p className="chat__empty">Start the conversation below.</p>}

        {messages.map((message) => (
          <MessageRow key={message.id} message={message} />
        ))}

        {sendingText !== null && <SendingRow text={sendingText} />}
        {pending && <TypingRow />}

        {footerSlot}
      </div>

      <div className="chat__footer">
        {lifecycle === 'CLOSED' && (
          <div className="banner banner--closed" role="status">
            <span className="banner__icon" aria-hidden="true">
              <CircleCheck size={16} />
            </span>
            <p className="banner__text">This conversation has ended.</p>
            <button type="button" className="btn btn--primary btn--sm" onClick={onNewConversation}>
              <RotateCcw size={15} aria-hidden="true" />
              Start a new conversation
            </button>
          </div>
        )}

        {suggestions.length > 0 && (
          <div className="suggestions" role="group" aria-label="Suggested messages">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.label}
                type="button"
                className={`chip${suggestion.featured ? ' chip--featured' : ''}`}
                onClick={() => applySuggestion(suggestion.text)}
                disabled={pending}
                aria-label={suggestion.name}
              >
                {suggestion.featured && <Sparkles size={14} aria-hidden="true" />}
                {suggestion.label}
              </button>
            ))}
          </div>
        )}

        <form className="composer" onSubmit={handleSubmit}>
          <div className={`composer__field${disabled ? ' is-disabled' : ''}`}>
            <label htmlFor="chat-input" className="visually-hidden">
              Message
            </label>
            <textarea
              id="chat-input"
              ref={inputRef}
              className="composer__input"
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={disabled ? 'Start a new conversation to keep chatting' : 'Type a message…'}
              rows={1}
              disabled={disabled || pending}
              aria-describedby={disabled ? undefined : 'composer-hint'}
            />
            <button type="submit" className="composer__send" disabled={!canSend} aria-label="Send" title="Send">
              <ArrowUp size={18} strokeWidth={2.5} aria-hidden="true" />
            </button>
          </div>
          {!disabled && (
            <p id="composer-hint" className="composer__hint">
              <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
            </p>
          )}
        </form>
      </div>
    </section>
  )
}
