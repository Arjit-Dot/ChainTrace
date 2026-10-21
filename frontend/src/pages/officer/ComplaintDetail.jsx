import { ArrowLeft, Loader2, Play, SearchCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { StageBadge } from '../../components/common/Badges'
import PageHeader from '../../components/common/PageHeader'
import { ErrorState, Loading } from '../../components/common/Status'
import { useFetch } from '../../hooks/useFetch'
import { getComplaint, reviewComplaint, traceComplaint } from '../../lib/api'
import { formatTime, formatUSDT, humanize } from '../../lib/format'
import { R } from '../../lib/routes'

const btn = 'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50'

function Row({ label, children }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="break-words">{children ?? '—'}</dd>
    </>
  )
}

function Body({ complaint, setComplaint }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const c = complaint
  const canReview = c.stage === 'received'
  const canTrace = !c.case_id && (c.stage === 'received' || c.stage === 'under_review')

  async function act(name, fn, after) {
    setBusy(name)
    setError(null)
    try {
      const next = await fn(c.complaint_id)
      setComplaint(next)
      after?.(next)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <PageHeader title={c.complaint_id} subtitle={`Received ${formatTime(c.created_at)}`}>
        <StageBadge stage={c.stage} />
        {canReview && (
          <button onClick={() => act('review', reviewComplaint)} disabled={!!busy} className={`${btn} border-line text-ink hover:bg-panel-2`}>
            {busy === 'review' ? <Loader2 className="size-4 animate-spin" /> : <SearchCheck className="size-4" />} Start review
          </button>
        )}
        {canTrace && (
          <button
            onClick={() => act('trace', traceComplaint, (n) => n.case_id && navigate(R.officerCase(n.case_id)))}
            disabled={!!busy}
            className={`${btn} border-accent/60 bg-accent text-bg hover:bg-accent/90`}
          >
            {busy === 'trace' ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
            {busy === 'trace' ? 'Tracing…' : 'Trigger trace'}
          </button>
        )}
        {c.case_id && (
          <Link to={R.officerCase(c.case_id)} className={`${btn} border-accent/60 text-accent hover:bg-accent/10`}>
            Open case {c.case_id}
          </Link>
        )}
      </PageHeader>

      <div className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="space-y-4">
          {error && (
            <p role="alert" className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
              {error.message}
            </p>
          )}
          <div className="rounded-lg border border-line bg-panel p-5">
            <h2 className="mb-3 text-sm font-semibold">Complaint</h2>
            <dl className="grid grid-cols-[150px_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
              <Row label="Reporter">{c.reporter_name}</Row>
              <Row label="Mobile">{c.reporter_mobile}</Row>
              <Row label="Reported wallet">
                <span className="font-mono text-xs">{c.wallet}</span>
              </Row>
              <Row label="Network">{c.chain ? humanize(c.chain) : null}</Row>
              <Row label="Amount lost">{c.amount == null ? null : formatUSDT(c.amount, c.currency)}</Row>
              <Row label="Fraud type">{c.fraud_type ? humanize(c.fraud_type) : null}</Row>
              <Row label="State">{c.state}</Row>
              <Row label="Transaction ID">{c.tx_hash ? <span className="font-mono text-xs">{c.tx_hash}</span> : null}</Row>
              <Row label="Description">{c.description}</Row>
            </dl>
          </div>
        </section>

        <aside className="rounded-lg border border-line bg-panel p-5 self-start" aria-label="History">
          <h2 className="mb-3 text-sm font-semibold">History (officers only)</h2>
          <ol className="space-y-3">
            {c.history.map((h, i) => (
              <li key={i} className="text-sm">
                <p className="flex items-center gap-2">
                  <StageBadge stage={h.stage} />
                  <span className="text-xs text-muted">{formatTime(h.at)}</span>
                </p>
                <p className="mt-0.5 text-muted">{h.note}</p>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </>
  )
}

export default function ComplaintDetail() {
  const { id } = useParams()
  const { data, loading, error, reload } = useFetch(() => getComplaint(id), [id])
  const [override, setOverride] = useState(null)
  const complaint = override ?? data

  if (loading && !data) return <Loading label={`Loading ${id}…`} />
  if (error && !data) return <ErrorState error={error} onRetry={reload} />
  return (
    <>
      <div className="px-6 pt-4">
        <Link to={R.officerInbox} className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
          <ArrowLeft className="size-3.5" /> Inbox
        </Link>
      </div>
      <Body key={id} complaint={complaint} setComplaint={setOverride} />
    </>
  )
}
