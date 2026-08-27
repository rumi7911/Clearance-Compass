import type { EntityResult } from './types'
import { Stamp } from './Stamp'

const CATEGORY_LABEL: Record<EntityResult['category'], string> = {
  brand: 'Brand / trademark',
  person: 'Public figure',
  song: 'Song / composition',
  archival: 'Archival footage',
  location: 'Real location',
  other: 'Other',
}

function ToolCall({ item }: { item: EntityResult['search_trail'][number] }) {
  const summary =
    item.tool === 'web_search'
      ? (item.args.objective as string) ?? JSON.stringify(item.args)
      : (item.args.url as string) ?? JSON.stringify(item.args)
  return (
    <li className="tool-call">
      <span className="tool-call-tag mono">{item.tool}</span>
      <span className="tool-call-summary">{summary}</span>
    </li>
  )
}

export function EntityDetail({ entity }: { entity: EntityResult }) {
  return (
    <div className="entity-detail">
      <div className="entity-detail-meta">
        <span className="eyebrow">{CATEGORY_LABEL[entity.category]}</span>
        {entity.license_ref && (
          <span className="eyebrow mono">license {entity.license_ref}</span>
        )}
      </div>

      <p className="entity-detail-reasoning">{entity.reasoning}</p>

      {!entity.resolved && entity.source !== 'error' && (
        <div className="scope-box">
          <span className="eyebrow">Needs manual review</span>
          <p>
            The research loop exhausted its retry budget without reaching
            confidence. The risk shown above is a best-effort guess, not a
            settled clearance -- a human should verify this one directly.
          </p>
        </div>
      )}

      {entity.source === 'error' && (
        <div className="scope-box">
          <span className="eyebrow">Research failed</span>
          <p>This entity couldn&rsquo;t be researched and needs manual review.</p>
        </div>
      )}

      {entity.source === 'internal-release-repository' ? (
        <div className="scope-box">
          <span className="eyebrow">Internal check</span>
          <p>
            Resolved from the production's own rights/release repository —
            no external research needed for this item.
          </p>
        </div>
      ) : entity.source === 'agent-memory' ? (
        <>
          <div className="scope-box">
            <span className="eyebrow">Agent memory</span>
            <p>
              Reused from a past live research run
              {entity.resolved_at && (
                <>
                  {' '}
                  resolved on{' '}
                  <span className="mono">
                    {new Date(entity.resolved_at).toLocaleDateString()}
                  </span>
                </>
              )}
              {' '}— still within the ~18-month evidence-recency window the
              research critic itself requires, so this wasn't re-researched.
              Check &ldquo;Force fresh research&rdquo; before running to
              re-verify it live.
            </p>
          </div>
          <EvidenceTrail entity={entity} labelPrefix="Original " />
        </>
      ) : (
        <EvidenceTrail entity={entity} labelPrefix="" />
      )}
    </div>
  )
}

function EvidenceTrail({ entity, labelPrefix }: { entity: EntityResult; labelPrefix: string }) {
  return (
    <>
      {entity.search_trail.length > 0 && (
        <div className="entity-detail-block">
          <span className="eyebrow">{labelPrefix}Live search trail</span>
          <ul className="tool-call-list">
            {entity.search_trail.map((item, i) => (
              <ToolCall item={item} key={i} />
            ))}
          </ul>
        </div>
      )}

      {entity.attempts.length > 0 && (
        <div className="entity-detail-block">
          <span className="eyebrow">
            {labelPrefix}Evaluation rounds ({entity.attempts.length})
          </span>
          <div className="attempts">
            {entity.attempts.map((attempt, i) => (
              <div className="attempt" key={i}>
                <div className="attempt-head">
                  <span className="mono">Round {i + 1}</span>
                  <Stamp risk={attempt.risk_level} seed={`${entity.name}:round-${i}`} size="sm" />
                  <span className="mono attempt-confidence">
                    confidence {attempt.confidence.toFixed(2)}
                  </span>
                </div>
                <p className="attempt-reasoning">{attempt.reasoning}</p>
                {attempt.retry_query && (
                  <p className="attempt-retry">
                    <span className="eyebrow">Retrying with</span>{' '}
                    &ldquo;{attempt.retry_query}&rdquo;
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
