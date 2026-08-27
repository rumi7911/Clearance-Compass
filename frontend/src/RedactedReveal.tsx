import { useEffect, useRef, useState } from 'react'
import type { RiskLevel } from './types'
import { Stamp } from './Stamp'

const REVEALS: { risk: RiskLevel; label: string }[] = [
  { risk: 'green', label: 'No rights conflict found in the evidence.' },
  { risk: 'yellow', label: 'Licensing or permission likely required.' },
  { risk: 'red', label: 'Active enforcement risk — needs sign-off.' },
]

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function useInView<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  // Known synchronously at mount -- a lazy initializer avoids setting
  // state from inside the effect just to reflect a value we already had.
  const [inView, setInView] = useState(prefersReducedMotion)

  useEffect(() => {
    if (inView) return // reduced-motion case already resolved at init
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold: 0.4 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [inView])

  return [ref, inView] as const
}

export function RedactedReveal() {
  const [ref, inView] = useInView<HTMLDivElement>()

  return (
    <div>
      <div className="reveal-row" ref={ref}>
        {REVEALS.map((r, i) => (
          <div className="redact-tile" key={r.risk}>
            {inView && (
              <>
                <Stamp risk={r.risk} seed={r.label} />
                <span className="redact-tile-label">{r.label}</span>
              </>
            )}
            <span
              className="redact-bar"
              style={{ transitionDelay: `${i * 150}ms` }}
              data-revealed={inView}
            />
          </div>
        ))}
      </div>
      <p className="reveal-caption mono">
        Every entity resolves to one of these three — open the case file
        below to see it happen on a real script.
      </p>
    </div>
  )
}
