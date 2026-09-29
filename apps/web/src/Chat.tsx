import { useEffect, useRef } from 'react'
import type { FormEvent, KeyboardEvent, ReactNode } from 'react'
import type { Message } from './api'

const DEMO_MESSAGE =
  "I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied healthcare claim from January. DOB is 1985-03-15, SSN last four is 4472."

interface ChatProps {
  messages: Message[]
  pending: boolean
  disabled: boolean
  draft: string
  onDraftChange: (value: string) => void
  onSend: () => void
  footerSlot?: ReactNode
}

export default function Chat({
  messages,
  pending,
  disabled,
  draft,
  onDraftChange,
  onSend,
  footerSlot,
}: ChatProps) {
  const historyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = historyRef.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [messages, pending])

  const canSend = !disabled && !pending && draft.trim().length > 0

  function submit() {
    if (canSend) {
      onSend()
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <section className="chat" aria-label="Conversation">
      <div className="chat__history" ref={historyRef} role="log" aria-live="polite" aria-atomic="false">
        {messages.length === 0 && !pending && (
          <p className="chat__empty">Start the conversation below.</p>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`message-row message-row--${message.role}`}>
            <div className="bubble">
              <div className="bubble__meta">
                <span className="bubble__role">{message.role === 'user' ? 'You' : 'Assistant'}</span>
                <span className="bubble__phase mono">{message.phase}</span>
              </div>
              <div className="bubble__text">{message.text}</div>
            </div>
          </div>
        ))}

        {pending && (
          <div className="message-row message-row--assistant">
            <div className="bubble bubble--typing">
              <span className="typing-dots" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <span>Assistant is typing&#8230;</span>
            </div>
          </div>
        )}

        {footerSlot}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <label htmlFor="chat-input" className="visually-hidden">
          Message
        </label>
        <textarea
          id="chat-input"
          className="composer__input"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message…"
          rows={2}
          disabled={disabled || pending}
        />
        <button type="submit" className="button" disabled={!canSend}>
          Send
        </button>
      </form>

      <div className="composer__footer">
        <button
          type="button"
          className="chip chip--action"
          onClick={() => onDraftChange(DEMO_MESSAGE)}
          disabled={disabled || pending}
        >
          Try the demo
        </button>
      </div>
    </section>
  )
}
