import { AlertTriangle, CheckCircle2, Circle, Loader2, RefreshCw, Search } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getComplaintStatus } from '../../lib/api'
import { STAGE_ORDER } from '../../lib/colors'
import { formatTime } from '../../lib/format'

const REFRESH_MS = 30000
const STEP_LABELS = {
  received: 'Received',
  under_review: 'Under review',
  investigating: 'Investigation in progress',
  action_initiated: 'Action initiated',
  closed: 'Closed',
}

// What the citizen sees about their complaint: the stage, one sentence for it, and when each stage began. The page
// reads ONLY those fields from the answer, so even a server mistake could not put anything else on screen.
function Progress({ stage }) {
  const at = STAGE_ORDER.indexOf(stage)
  return (
    <ol aria-label="Progress" className="grid gap-2 sm:grid-cols-5">
      {STAGE_ORDER.map((s, i) => {
        const done = i < at || (stage === 'closed' && i === at)
        const current = i === at && stage !== 'closed'
        return (
          <li
            key={s}
            aria-current={current ? 'step' : undefined}
            data-state={done ? 'done' : current ? 'current' : 'todo'}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
              current ? 'border-accent/60 bg-accent/10 text-accent' : done ? 'border-emerald-500/30 text-emerald-300' : 'border-line text-muted'
            }`}
          >
            {done ? <CheckCircle2 className="size-4 shrink-0" /> : <Circle className="size-4 shrink-0" />}
            {STEP_LABELS[s]}
          </li>
        )
      })}
    </ol>
  )
}

function Result({ view }) {
  return (
    <section role="status" aria-label="Complaint status" className="space-y-5 rounded-xl border border-line bg-panel p-6">
      <div>
        <p className="text-xs tracking-wide text-muted uppercase">Complaint</p>
        <p className="font-mono text-lg font-semibold" data-testid="tracked-id">{view.complaint_id}</p>
      </div>
      <div>
        <p className="text-xs tracking-wide text-muted uppercase">Status</p>
        <h2 className="text-2xl font-bold tracking-tight">{view.label}</h2>
        <p className="mt-1 text-sm text-ink/90">{view.message}</p>
        <p className="mt-1 text-xs text-muted">Last updated {formatTime(view.updated_at)}</p>
      </div>
      <Progress stage={view.stage} />
      <div>
        <h3 className="mb-2 text-sm font-semibold">What has happened so far</h3>
        <ol className="space-y-2 border-l border-line pl-4">
          {view.timeline.map((t) => (
            <li key={t.stage} className="text-sm">
              <p className="font-medium">{t.label}</p>
              <p className="text-muted">{t.message}</p>
              <p className="text-xs text-muted">{formatTime(t.at)}</p>
            </li>
          ))}
        </ol>
      </div>
      <p className="text-xs text-muted">
        For the integrity of the investigation, details of how a complaint is handled are not shown. For anything urgent, call the
        National Cyber Crime Helpline 1930.
      </p>
    </section>
  )
}

// Keep only the five fields a citizen is allowed to see.
const pick = (d) => ({
  complaint_id: d.complaint_id,
  stage: d.stage,
  label: d.label,
  message: d.message,
  updated_at: d.updated_at,
  timeline: (d.timeline ?? []).map((t) => ({ stage: t.stage, label: t.label, message: t.message, at: t.at })),
})

export default function TrackComplaint() {
  const [params, setParams] = useSearchParams()
  const asked = (params.get('id') ?? '').trim().toUpperCase()
  const [text, setText] = useState(params.get('id') ?? '')
  const [state, setState] = useState({ phase: 'idle' })

  const load = useCallback(
    async (quiet = false) => {
      if (!asked) return
      if (!quiet) setState({ phase: 'loading' })
      try {
        setState({ phase: 'found', view: pick(await getComplaintStatus(asked)) })
      } catch (e) {
        if (!quiet) setState({ phase: 'error', message: e.message || 'Something went wrong. Please try again.' })
      }
    },
    [asked],
  )

  useEffect(() => {
    if (!asked) {
      setState({ phase: 'idle' })
      return undefined
    }
    load()
    const timer = setInterval(() => load(true), REFRESH_MS)
    return () => clearInterval(timer)
  }, [asked, load])

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Track a complaint</h1>
        <p className="mt-1 text-sm text-muted">Enter the complaint ID you received when you reported the fraud.</p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          const id = text.trim()
          setParams(id ? { id } : {})
        }}
        className="flex gap-2"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. NCRP-2026-123456"
          aria-label="Complaint ID"
          autoComplete="off"
          className="w-full rounded-md border border-line bg-bg px-3 py-2 font-mono text-sm focus:border-accent focus:outline-none"
        />
        <button type="submit" className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg hover:bg-accent/90">
          <Search className="size-4" /> Track
        </button>
      </form>

      {state.phase === 'loading' && (
        <p role="status" className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="size-4 animate-spin" /> Looking up your complaint…
        </p>
      )}
      {state.phase === 'error' && (
        <p role="alert" className="flex items-start gap-2 rounded-md border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {state.message}
        </p>
      )}
      {state.phase === 'found' && (
        <>
          <Result view={state.view} />
          <button
            type="button"
            onClick={() => load()}
            className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-xs text-muted hover:text-ink"
          >
            <RefreshCw className="size-3.5" /> Refresh
          </button>
        </>
      )}
    </div>
  )
}
