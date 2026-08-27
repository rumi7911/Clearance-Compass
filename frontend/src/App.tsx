import { useEffect, useRef, useState } from 'react'
import type { ClearanceGraphData } from './types'
import { ClearanceGraph } from './ClearanceGraph'
import { ScriptInput } from './ScriptInput'
import { LoadingState } from './LoadingState'
import { Landing } from './Landing'

type Status = 'idle' | 'loading' | 'error' | 'done'

export function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [script, setScript] = useState('')
  const [scriptReady, setScriptReady] = useState(false)
  const [forceFresh, setForceFresh] = useState(false)
  const [data, setData] = useState<ClearanceGraphData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const runningRef = useRef(false)

  useEffect(() => {
    fetch('/api/demo-script')
      .then((res) => res.json())
      .then((body: { script: string }) => {
        setScript(body.script)
        setScriptReady(true)
      })
      .catch(() => {
        setError('Could not load the demo script. You can still type your own below.')
        setScriptReady(true)
      })
  }, [])

  async function runAnalysis() {
    if (runningRef.current) return
    runningRef.current = true
    setStatus('loading')
    setError(null)
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script, force_fresh: forceFresh }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        if (res.status === 409) {
          throw new Error('An analysis is already running — wait for it to finish.')
        }
        if (res.status === 400) {
          throw new Error(payload?.detail ?? 'Invalid script.')
        }
        throw new Error(`Request failed: ${res.status}`)
      }
      const graph: ClearanceGraphData = await res.json()
      setData(graph)
      setStatus('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setStatus('error')
    } finally {
      runningRef.current = false
    }
  }

  function newAnalysis() {
    setStatus('idle')
    setData(null)
    setError(null)
    // `script` is intentionally left as-is so an edited draft survives
  }

  return (
    <div className="page">
      <Landing />

      <main className="page-body" id="case-file">
        {status === 'loading' && <LoadingState />}
        {(status === 'idle' || status === 'error') && (
          <ScriptInput
            value={script}
            onChange={setScript}
            onRun={runAnalysis}
            ready={scriptReady}
            error={status === 'error' ? error : null}
            forceFresh={forceFresh}
            onForceFreshChange={setForceFresh}
          />
        )}
        {data && (
          <>
            <button className="new-analysis-button" onClick={newAnalysis}>
              New analysis
            </button>
            {data.warning && <p className="warning-note">{data.warning}</p>}
            <ClearanceGraph data={data} />
          </>
        )}
      </main>
    </div>
  )
}
