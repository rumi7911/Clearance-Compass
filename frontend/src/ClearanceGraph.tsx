import { useState } from 'react'
import type { ClearanceGraphData, EntityResult } from './types'
import { EntityDetail } from './EntityDetail'
import { Stamp } from './Stamp'

function riskRank(risk: EntityResult['risk']): number {
  return risk === 'red' ? 0 : risk === 'yellow' ? 1 : 2
}

function EntityChip({
  entity,
  open,
  onToggle,
}: {
  entity: EntityResult
  open: boolean
  onToggle: () => void
}) {
  return (
    <div className={`entity-row risk-${entity.risk} ${open ? 'is-open' : ''}`}>
      <button className="entity-chip" onClick={onToggle} aria-expanded={open}>
        <Stamp risk={entity.risk} seed={entity.name} size="sm" />
        <span className="entity-name">{entity.name}</span>
        <span className="entity-chevron mono">{open ? '−' : '+'}</span>
      </button>
      {open && <EntityDetail entity={entity} />}
    </div>
  )
}

export function ClearanceGraph({ data }: { data: ClearanceGraphData }) {
  const [openKey, setOpenKey] = useState<string | null>(null)

  const totalEntities = data.scenes.reduce((n, s) => n + s.entities.length, 0)
  const counts = { red: 0, yellow: 0, green: 0 }
  for (const scene of data.scenes) {
    for (const entity of scene.entities) counts[entity.risk]++
  }

  return (
    <div className="graph">
      <div className="graph-summary stat-grid">
        <div className="stat-cell">
          <span className="eyebrow">Entities reviewed</span>
          <div className="value">{totalEntities}</div>
        </div>
        <div className="stat-cell">
          <span className="eyebrow">High risk</span>
          <div className="value risk-text-red">{counts.red}</div>
        </div>
        <div className="stat-cell">
          <span className="eyebrow">Needs attention</span>
          <div className="value risk-text-yellow">{counts.yellow}</div>
        </div>
        <div className="stat-cell">
          <span className="eyebrow">Cleared</span>
          <div className="value risk-text-green">{counts.green}</div>
        </div>
      </div>

      {data.scenes.map((scene) => (
        <section className="scene" key={scene.id}>
          <div className="scene-head">
            <span className="eyebrow">{scene.heading}</span>
            <p className="scene-text">{scene.text}</p>
          </div>
          <div className="entity-list">
            {[...scene.entities]
              .sort((a, b) => riskRank(a.risk) - riskRank(b.risk))
              .map((entity) => {
                const key = `${scene.id}:${entity.name}`
                return (
                  <EntityChip
                    key={key}
                    entity={entity}
                    open={openKey === key}
                    onToggle={() =>
                      setOpenKey(openKey === key ? null : key)
                    }
                  />
                )
              })}
          </div>
        </section>
      ))}
    </div>
  )
}
