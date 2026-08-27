import type { CSSProperties } from 'react'
import type { RiskLevel } from './types'

const STAMP_LABEL: Record<RiskLevel, string> = {
  green: 'CLEARED',
  yellow: 'HOLD',
  red: 'FLAG',
}

// Deterministic per-instance rotation hashed from a stable seed (e.g. the
// entity name) so the same entity always renders the same tilt across
// re-renders, but different entities don't all look uniformly stamped.
function rotationFor(seed: string): number {
  let hash = 0
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) | 0
  return (Math.abs(hash) % 7) - 3 // -3..3 degrees
}

export function Stamp({
  risk,
  seed,
  size = 'md',
}: {
  risk: RiskLevel
  seed: string
  size?: 'sm' | 'md'
}) {
  const style = { '--stamp-rotate': `${rotationFor(seed)}deg` } as CSSProperties
  return (
    <span className={`stamp stamp-${risk} stamp-${size}`} style={style}>
      {STAMP_LABEL[risk]}
    </span>
  )
}
