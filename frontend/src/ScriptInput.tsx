import { MAX_SCRIPT_CHARS } from './demoScript'

const PIPELINE_STEPS = ['Extract', 'Research', 'Evaluate', 'Iterate']

interface ScriptInputProps {
  value: string
  onChange: (v: string) => void
  onRun: () => void
  ready: boolean
  error: string | null
  forceFresh: boolean
  onForceFreshChange: (v: boolean) => void
}

export function ScriptInput({
  value,
  onChange,
  onRun,
  ready,
  error,
  forceFresh,
  onForceFreshChange,
}: ScriptInputProps) {
  const overLimit = value.length > MAX_SCRIPT_CHARS

  return (
    <div className="intake-desk">
      <span className="folder-tab mono">Case File — Script Intake</span>
      <p className="prose intake-guidance">
        Paste or edit a scene below. Real screenplay sluglines (
        <span className="mono">INT.</span> / <span className="mono">EXT.</span>) split it
        into scenes automatically — no sluglines, and the whole thing runs as
        one scene.
      </p>
      <ol className="pipeline-steps mono">
        {PIPELINE_STEPS.map((step, i) => (
          <li key={step}>
            <span className="step-index">{String(i + 1).padStart(2, '0')}</span>
            {step}
          </li>
        ))}
      </ol>
      <textarea
        className="script-textarea"
        value={ready ? value : 'Loading demo script…'}
        onChange={(e) => onChange(e.target.value)}
        rows={16}
        spellCheck={false}
        disabled={!ready}
        aria-label="Script text"
      />
      <label className="force-fresh-toggle mono">
        <input
          type="checkbox"
          checked={forceFresh}
          onChange={(e) => onForceFreshChange(e.target.checked)}
        />
        Force fresh research (bypass agent memory)
      </label>
      <div className="intake-footer">
        <span className={`mono char-count ${overLimit ? 'char-count-over' : ''}`}>
          {value.length.toLocaleString()} / {MAX_SCRIPT_CHARS.toLocaleString()}
        </span>
        <button className="run-button" onClick={onRun} disabled={!ready || overLimit}>
          Run Analysis
        </button>
      </div>
      {error && <p className="error-note">{error}</p>}
    </div>
  )
}
