import { useEffect, useState } from 'react'

const STEPS = [
  'Extracting entities from the script…',
  'Researching each entity live…',
  'Evaluating evidence and confidence…',
  'Iterating on low-confidence findings…',
]
const STEP_INTERVAL_MS = 4000

export function LoadingState() {
  const [stepIndex, setStepIndex] = useState(0)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const id = window.setInterval(
      () => setStepIndex((i) => (i + 1) % STEPS.length),
      STEP_INTERVAL_MS,
    )
    return () => window.clearInterval(id)
  }, [])

  return (
    <div className="loading-state" role="status" aria-live="polite">
      <p className="loading-step mono">{STEPS[stepIndex]}</p>
      <p className="loading-note">
        The agent is extracting entities, then researching and evaluating
        each one live through Parallel — with a fresh Google Cloud
        project's default quota this runs sequentially and can take up to
        ~10 minutes end to end. It speeds up once a Vertex AI quota
        increase is granted.
      </p>
    </div>
  )
}
