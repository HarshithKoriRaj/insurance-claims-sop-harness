import { Check, ClipboardList, Compass, Mail, ShieldUser } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Phase } from './api'

const STEPS: ReadonlyArray<{ phase: Phase; label: string; icon: LucideIcon }> = [
  { phase: 'VERIFY_ID', label: 'Verify identity', icon: ShieldUser },
  { phase: 'RESOLVE_INTENT', label: 'Understand request', icon: Compass },
  { phase: 'PROCESS_CASE', label: 'Handle claim', icon: ClipboardList },
  { phase: 'POST_PROCESS', label: 'Wrap up', icon: Mail },
]

type StepStatus = 'complete' | 'current' | 'upcoming'

const STATUS_TEXT: Record<StepStatus, string> = {
  complete: 'completed',
  current: 'current step',
  upcoming: 'not started',
}

interface PhaseStepperProps {
  phase: Phase
  /** True once the conversation has ended: the current step stops pulsing. */
  settled?: boolean
}

export default function PhaseStepper({ phase, settled = false }: PhaseStepperProps) {
  const currentIndex = STEPS.findIndex((step) => step.phase === phase)
  const current = currentIndex >= 0 ? STEPS[currentIndex] : undefined

  return (
    <section className={`progress card${settled ? ' is-settled' : ''}`} aria-label="Conversation progress">
      <ol className="progress__track" aria-label="Conversation phase">
        {STEPS.map((step, index) => {
          const status: StepStatus =
            currentIndex < 0
              ? 'upcoming'
              : index < currentIndex
                ? 'complete'
                : index === currentIndex
                  ? 'current'
                  : 'upcoming'
          const Icon = status === 'complete' ? Check : step.icon

          return (
            <li
              key={step.phase}
              className={`progress__step is-${status}`}
              aria-current={status === 'current' ? 'step' : undefined}
            >
              <span className="progress__node" aria-hidden="true">
                <Icon size={18} strokeWidth={status === 'complete' ? 2.75 : 2} />
              </span>
              <span className="progress__text">
                <span className="progress__label">{step.label}</span>
                <span className="progress__code">{step.phase}</span>
                <span className="visually-hidden"> ({STATUS_TEXT[status]})</span>
              </span>
              {index < STEPS.length - 1 && (
                <span className="progress__connector" aria-hidden="true">
                  <span className="progress__fill" />
                </span>
              )}
            </li>
          )
        })}
      </ol>

      {current && (
        // Compact layouts hide the per-step labels; this line names the current step.
        <p className="progress__summary" aria-hidden="true">
          <span className="progress__summary-count">
            Step {currentIndex + 1} of {STEPS.length}
          </span>
          <span className="progress__summary-label">{current.label}</span>
          <span className="progress__code">{current.phase}</span>
        </p>
      )}
    </section>
  )
}
