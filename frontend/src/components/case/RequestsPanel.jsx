import { Check, Circle, FileText, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useFetch } from '../../hooks/useFetch'
import { approveRequest, closeRequest, demoRun, getReply, getRequests, sendRequest, simulateRequest } from '../../lib/api'
import { CHOKE_POINTS, REQUEST_STAGES, REQUEST_STATUS, REQUESTS } from '../../lib/colors'
import { formatTime } from '../../lib/format'

const btn = 'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50'

function Stepper({ status }) {
  const at = REQUEST_STAGES.indexOf(status)
  return (
    <ol aria-label="Request progress" className="flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
      {REQUEST_STAGES.map((s, i) => (
        <li key={s} data-state={i < at ? 'done' : i === at ? 'current' : 'todo'} className={`flex items-center gap-1 ${i === at ? 'font-semibold text-accent' : i < at ? 'text-emerald-300' : 'text-muted'}`}>
          {i < at ? <Check className="size-3" /> : <Circle className="size-3" />}
          {REQUEST_STATUS[s]}
        </li>
      ))}
    </ol>
  )
}

function ReplyView({ requestId }) {
  const { data, error } = useFetch(() => getReply(requestId), [requestId])
  if (error && !data) return <p role="alert" className="text-xs text-red-300">{error.message}</p>
  if (!data) return <p className="text-xs text-muted">Loading the reply…</p>
  return (
    <div className="space-y-2 rounded-md border border-amber-400/30 bg-amber-400/5 p-3" aria-label="Reply">
      <p className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[11px] font-semibold text-amber-200">FICTIONAL DEMO DATA</span>
        <span>{data.summary}</span>
      </p>
      <dl className="grid grid-cols-[160px_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
        {data.fields.map((f) => (
          <div key={f.label} className="contents">
            <dt className="text-muted">{f.label}</dt>
            <dd className="font-mono break-words">{f.value}</dd>
          </div>
        ))}
      </dl>
      <p className="text-[11px] text-muted">
        {data.new_identifier_ids.length
          ? `${data.new_identifier_ids.length} new identifier${data.new_identifier_ids.length === 1 ? '' : 's'} added to this case, opening new leads.`
          : 'This reply added no new identifiers.'}
      </p>
    </div>
  )
}

function RequestCard({ r, onChange }) {
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [show, setShow] = useState(null) // 'letter' | 'reply'

  const act = async (name, fn) => {
    setBusy(name)
    setError(null)
    try {
      await fn(r.request_id)
      onChange()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(null)
    }
  }
  const toggle = (what) => setShow((s) => (s === what ? null : what))

  return (
    <li className="space-y-2 rounded-lg border border-line bg-panel-2/40 p-3" data-testid="request" data-status={r.status}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold">{REQUESTS[r.kind] ?? r.kind}</span>
        <span className="text-sm text-muted">· {r.holder}</span>
        <span className="text-xs text-muted">({CHOKE_POINTS[r.choke_point]})</span>
        <span className="ml-auto font-mono text-[11px] text-muted">{r.request_id}</span>
      </div>
      <p className="text-xs text-muted">
        About <span className="font-mono">{r.subject}</span> · {formatTime(r.updated_at)}
        {r.reference && <span> · ref {r.reference}</span>}
      </p>
      <Stepper status={r.status} />
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => toggle('letter')} className={`${btn} border-line hover:bg-panel-2`}>
          <FileText className="size-3.5" /> {show === 'letter' ? 'Hide letter' : 'View letter'}
        </button>
        {r.status === 'draft' && (
          <button type="button" disabled={!!busy} onClick={() => act('approve', approveRequest)} className={`${btn} border-accent/60 text-accent hover:bg-accent/10`}>
            Approve
          </button>
        )}
        {r.status === 'approved' && (
          <button type="button" disabled={!!busy} onClick={() => act('send', sendRequest)} className={`${btn} border-accent/60 bg-accent text-bg hover:bg-accent/90`}>
            Send
          </button>
        )}
        {(r.status === 'sent' || r.status === 'acknowledged') && (
          <button type="button" disabled={!!busy} onClick={() => act('sim', simulateRequest)} className={`${btn} border-amber-400/50 text-amber-200 hover:bg-amber-400/10`}>
            {busy === 'sim' && <Loader2 className="size-3.5 animate-spin" />}
            {r.status === 'sent' ? 'Simulate acknowledgement (demo)' : 'Simulate reply (demo)'}
          </button>
        )}
        {r.status === 'replied' && (
          <button type="button" onClick={() => toggle('reply')} className={`${btn} border-line hover:bg-panel-2`}>
            {show === 'reply' ? 'Hide reply' : 'View reply'}
          </button>
        )}
        {['sent', 'acknowledged', 'replied'].includes(r.status) && (
          <button type="button" disabled={!!busy} onClick={() => act('close', closeRequest)} className={`${btn} border-line text-muted hover:text-ink`}>
            Close
          </button>
        )}
      </div>
      {error && <p role="alert" className="text-xs text-red-300">{error.message}</p>}
      {show === 'letter' && <pre className="max-h-96 overflow-auto rounded-md bg-bg p-3 text-[11px] leading-relaxed whitespace-pre-wrap">{r.letter_body}</pre>}
      {show === 'reply' && <ReplyView requestId={r.request_id} />}
    </li>
  )
}

// Letters to the institutions that hold the identity behind each lead. Drafts only: an officer approves, and in this demo
// nothing is ever transmitted (the acknowledgement and the reply are simulated, and the replies are fictional).
export default function RequestsPanel({ caseId, version = 0, onChange = () => {} }) {
  const { data, error, reload } = useFetch(() => getRequests(caseId), [caseId, version])
  const [running, setRunning] = useState(false)
  const [ran, setRan] = useState(null)
  const [runError, setRunError] = useState(null)
  const changed = () => {
    reload()
    onChange()
  }
  const run = async () => {
    setRunning(true)
    setRunError(null)
    try {
      setRan(await demoRun(caseId, 2))
      changed()
    } catch (e) {
      setRunError(e)
    } finally {
      setRunning(false)
    }
  }
  return (
    <section className="space-y-3 rounded-lg border border-line bg-panel p-5" aria-label="Requests to institutions">
      <div>
        <h2 className="text-sm font-semibold">Requests to institutions</h2>
        <p className="text-xs text-muted">
          Draft a request from a lead below, review the letter, approve it, then send. Nothing is transmitted in this demo: the acknowledgement
          and reply are simulated, and every reply is fictional.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={run} disabled={running} className={`${btn} border-amber-400/50 text-amber-200 hover:bg-amber-400/10`}>
          {running && <Loader2 className="size-3.5 animate-spin" />} Demo: simulate the whole investigation
        </button>
        <span className="text-xs text-muted">Drafts, approves and sends the main request for every lead and simulates the replies (two rounds). Everything is simulated.</span>
        {ran && <span className="text-xs text-emerald-300" role="status">{ran.requests} requests answered, {ran.new_identifiers} new identifiers added.</span>}
        {runError && <span role="alert" className="text-xs text-red-300">{runError.message}</span>}
      </div>
      {error && !data ? (
        <p role="alert" className="text-sm text-red-300">Could not load requests: {error.message}</p>
      ) : !data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : data.length === 0 ? (
        <p className="text-sm text-muted">No requests yet. Use “Draft” on a lead.</p>
      ) : (
        <ul className="space-y-3">
          {data.map((r) => (
            <RequestCard key={r.request_id} r={r} onChange={changed} />
          ))}
        </ul>
      )}
    </section>
  )
}
