import type { Phase } from './api'

const STEPS: ReadonlyArray<{ phase: Phase; label: string }> = [
  { phase: 'VERIFY_ID', label: 'Verify identity' },
  { phase: 'RESOLVE_INTENT', label: 'Understand request' },
  { phase: 'PROCESS_CASE', label: 'Handle claim' },
  { phase: 'POST_PROCESS', label: 'Wrap up' },
]

interface PhaseStepperProps {
  phase: Phase
}

export default function PhaseStepper({ phase }: PhaseStepperProps) {
  const currentIndex = STEPS.findIndex((step) => step.phase === phase)

  return (
    <ol className="phase-stepper" aria-label="Conversation phase">
      {STEPS.map((step, index) => {
        const status: 'complete' | 'current' | 'upcoming' =
          currentIndex < 0
            ? 'upcoming'
            : index < currentIndex
              ? 'complete'
              : index === currentIndex
                ? 'current'
                : 'upcoming'

        return (
          <li
            key={step.phase}
            className={`phase-step phase-step--${status}`}
            aria-current={status === 'current' ? 'step' : undefined}
          >
            <span className="phase-step__marker" aria-hidden="true">
              {status === 'complete' ? '✓' : index + 1}
            </span>
            <span className="phase-step__text">
              <span className="phase-step__label">{step.label}</span>
              <span className="phase-step__code mono">{step.phase}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
