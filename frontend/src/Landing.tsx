import { RedactedReveal } from './RedactedReveal'

const EXHIBITS = [
  {
    tag: 'A',
    title: 'Plan',
    body: 'An extractor agent reads a scene and lists the real-world entities worth clearing.',
  },
  {
    tag: 'B',
    title: 'Act',
    body: "A researcher agent calls Parallel's web_search and web_fetch tools live, inside its own reasoning loop.",
  },
  {
    tag: 'C',
    title: 'Evaluate',
    body: 'A critic agent judges whether the evidence is strong enough — independent, recent sources — and scores its confidence.',
  },
  {
    tag: 'D',
    title: 'Iterate',
    body: 'Low confidence sends the critic back with a genuinely different search angle. Capped at two rounds.',
  },
]

export function Landing() {
  return (
    <header className="hero">
      <div className="masthead-row">
        <span className="eyebrow">Clearance Compass</span>
        <span className="eyebrow">Parallel &middot; ClickHouse &middot; Gemini</span>
      </div>

      <div className="hero-intro">
        <h1>Nothing clears itself.</h1>
        <p className="tagline">
          Every real-world mention in a script — a brand, a face, a song, a
          place — carries risk until an agent has actually gone and
          checked. Clearance Compass researches each one live and shows
          its work.
        </p>
      </div>

      <RedactedReveal />

      <div className="cta-row">
        <a className="cta-button" href="#case-file">
          Open the case file &darr;
        </a>
        <p className="filed-under mono">
          research: Parallel Search &amp; Extract MCP &middot; memory:
          ClickHouse agent memory &middot; model: Gemini on Vertex AI
          (Google ADK)
        </p>
      </div>

      <div className="exhibit-strip">
        {EXHIBITS.map((e) => (
          <div className="exhibit-card" key={e.tag}>
            <span className="exhibit-tag mono">Exhibit {e.tag}</span>
            <h3>{e.title}</h3>
            <p>{e.body}</p>
          </div>
        ))}
      </div>
    </header>
  )
}
