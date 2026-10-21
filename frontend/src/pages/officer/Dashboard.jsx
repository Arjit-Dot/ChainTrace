import { Bell, FilePlus2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { UrgencyBadge } from '../../components/common/Badges'
import { AlertLine, SEVERITY } from '../../components/common/AlertFeed'
import PageHeader from '../../components/common/PageHeader'
import { Empty, ErrorState, Loading } from '../../components/common/Status'
import BarBreakdown from '../../components/dashboard/BarBreakdown'
import { useAlertListener, useAlerts } from '../../hooks/useAlerts'
import { useFetch } from '../../hooks/useFetch'
import { getCases, getDashboard } from '../../lib/api'
import { formatDuration, formatUSDT, shortAddr } from '../../lib/format'
import { R } from '../../lib/routes'

function Tile({ label, value, note }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {note && <p className="mt-0.5 text-xs text-muted">{note}</p>}
    </div>
  )
}

function Kpis({ d }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Tile label="Cases" value={d.total_cases} note={`${d.open_cases ?? d.total_cases} open · ${d.closed_cases ?? 0} closed`} />
      <Tile label="Amount lost" value={formatUSDT(d.total_amount_lost)} />
      <Tile label="Amount traced" value={formatUSDT(d.total_amount_traced)} />
      <Tile label="Exchange identified" value={`${Math.round(d.vasp_identified_pct)}%`} note="of cases" />
      <Tile label="Avg time to attribution" value={formatDuration(d.avg_time_to_attribution_sec)} />
      <Tile label="Idle funds flagged" value={formatUSDT(d.idle_funds_flagged)} note="still sitting in wallets" />
    </div>
  )
}

function MetricToggle({ value, onChange }) {
  const opts = [
    ['count', 'Cases'],
    ['amount', 'USDT lost'],
  ]
  return (
    <div className="inline-flex rounded-md border border-line bg-panel p-0.5 text-xs" role="group" aria-label="Chart measure">
      {opts.map(([k, label]) => (
        <button
          key={k}
          onClick={() => onChange(k)}
          aria-pressed={value === k}
          className={`rounded px-3 py-1 font-medium ${value === k ? 'bg-panel-2 text-ink' : 'text-muted hover:text-ink'}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

function RecentCases({ cases }) {
  return (
    <section className="min-w-0 rounded-lg border border-line bg-panel">
      <h2 className="border-b border-line px-4 py-2.5 text-sm font-semibold">Recent cases</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-panel-2 text-xs tracking-wide text-muted uppercase">
            <tr>
              {['Case', 'Open / closed', 'Complaint', 'Wallet', 'Lost', 'Fraud type', 'State', 'Urgency', 'VASP', 'Network', 'Status'].map((h) => (
                <th key={h} className="px-4 py-2.5 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {cases.map((c) => (
              <tr key={c.case_id} className="hover:bg-panel-2/60">
                <td className="px-4 py-2.5">
                  <Link to={R.officerCase(c.case_id)} className="font-medium text-accent hover:underline">
                    {c.case_id}
                  </Link>
                </td>
                <td className="px-4 py-2.5">
                  <span
                    data-testid="case-open"
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${c.open === false ? 'bg-slate-500/15 text-slate-300' : 'bg-emerald-500/15 text-emerald-300'}`}
                  >
                    {c.open === false ? 'Closed' : 'Open'}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-muted">{c.complaint_id}</td>
                <td className="px-4 py-2.5 font-mono text-xs">{shortAddr(c.wallet)}</td>
                <td className="px-4 py-2.5">{formatUSDT(c.amount_lost)}</td>
                <td className="px-4 py-2.5 capitalize">{c.fraud_type}</td>
                <td className="px-4 py-2.5">{c.state}</td>
                <td className="px-4 py-2.5">
                  <UrgencyBadge urgency={c.urgency} reasons={c.urgency_reasons} />
                </td>
                <td className="px-4 py-2.5">{c.vasp ?? <span className="text-muted">—</span>}</td>
                <td className="px-4 py-2.5">
                  {c.network_id ? (
                    <Link to={R.officerNetwork(c.network_id)} className="text-accent hover:underline">
                      {c.network_id}
                    </Link>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-muted">{c.status.replaceAll('_', ' ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function LiveFeed() {
  const { feed, connected } = useAlerts()
  return (
    <section className="self-start rounded-lg border border-line bg-panel">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Bell className="size-4 text-muted" /> Live alerts
        </h2>
        <span className="flex items-center gap-1.5 text-xs text-muted">
          <span className={`size-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
          {connected ? 'Live' : 'Reconnecting…'}
        </span>
      </div>
      {feed.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">No alerts yet.</p>
      ) : (
        <ul className="max-h-[32rem] divide-y divide-line overflow-auto">
          {feed.slice(0, 12).map((a) => (
            <li key={a.id} className={`border-l-2 px-4 py-3 ${(SEVERITY[a.severity] ?? SEVERITY.info).bar}`}>
              <AlertLine alert={a} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function Dashboard() {
  const stats = useFetch(getDashboard)
  const cases = useFetch(getCases)
  const [metric, setMetric] = useState('count')

  // A new complaint or a change on a case shows up straight away.
  useAlertListener(() => {
    stats.reload()
    cases.reload()
  })

  const first = (stats.loading && !stats.data) || (cases.loading && !cases.data)
  const error = (!stats.data && stats.error) || (!cases.data && cases.error)

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Complaints, attribution and funds at a glance" />
      {first ? (
        <Loading label="Loading dashboard…" />
      ) : error ? (
        <ErrorState
          error={error}
          onRetry={() => {
            stats.reload()
            cases.reload()
          }}
        />
      ) : !cases.data.length ? (
        <Empty>No cases yet. Submit a complaint to start.</Empty>
      ) : (
        <div className="space-y-6 p-6">
          <Kpis d={stats.data} />

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-muted">Breakdown</h2>
              <MetricToggle value={metric} onChange={setMetric} />
            </div>
            <div className="grid gap-6 xl:grid-cols-3">
              <BarBreakdown title="By fraud type" items={stats.data.by_fraud_type} metric={metric} humanizeNames />
              <BarBreakdown title="Top receiving exchanges" items={stats.data.top_vasps} metric={metric} />
              <BarBreakdown title="By state" items={stats.data.by_state} metric={metric} />
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
            <RecentCases cases={cases.data} />
            <LiveFeed />
          </div>
        </div>
      )}
    </>
  )
}
