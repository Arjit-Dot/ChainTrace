import { useParams } from 'react-router-dom'
import { RiskBadge, SourceBadge } from '../components/Badges'
import Legend from '../components/Legend'
import PageHeader from '../components/PageHeader'
import { ErrorState, Loading } from '../components/Status'
import { useFetch } from '../hooks/useFetch'
import { getCase } from '../lib/api'
import { formatDuration, formatPct, formatUSDT, shortAddr } from '../lib/format'

function Stat({ label, value, highlight }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${highlight ? 'text-amber-300' : ''}`}>{value}</p>
    </div>
  )
}

// B1 stub: header + summary. Graph, node panel, Nearest VASP card and recommendations come in B2.
export default function CaseView() {
  const { id } = useParams()
  const { data: t, loading, error, reload } = useFetch(() => getCase(id), [id])

  if (loading) return <Loading label={`Loading ${id}…`} />
  if (error) return <ErrorState error={error} onRetry={reload} />

  const { summary: s, nearest_vasp: v } = t
  return (
    <>
      <PageHeader
        title={`Case ${t.case_id}`}
        subtitle={`${t.complaint_id} · ${t.fraud_type ?? 'unknown'} · wallet ${shortAddr(t.wallet, 8)}`}
      >
        <RiskBadge risk={t.risk} score={t.risk_score} />
        <SourceBadge source={t.source} />
      </PageHeader>

      <div className="space-y-6 p-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Stat label="Amount lost" value={formatUSDT(t.amount_lost)} />
          <Stat label="Total traced" value={formatUSDT(s.total_traced)} />
          <Stat label="Idle funds" value={formatUSDT(s.idle_funds)} highlight={s.idle_funds > 0} />
          <Stat label="Hops / nodes" value={`${s.hops} / ${s.nodes}`} />
          <Stat label="Time to attribution" value={formatDuration(s.time_to_attribution_sec)} />
          <Stat label="Nearest VASP" value={v ? `${v.vasp} · ${formatPct(v.confidence)}` : 'Not found'} />
        </div>

        <section className="rounded-lg border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Fund flow</h2>
            <Legend />
          </div>
          <div className="grid h-80 place-items-center text-sm text-muted">
            Fund-flow graph ({t.graph.nodes.length} nodes, {t.graph.edges.length} transfers) arrives in B2.
          </div>
        </section>
      </div>
    </>
  )
}
