import { useState } from 'react'
import { Link } from 'react-router-dom'
import { StageBadge } from '../../components/common/Badges'
import PageHeader from '../../components/common/PageHeader'
import { Empty, ErrorState, Loading } from '../../components/common/Status'
import { useAlertListener } from '../../hooks/useAlerts'
import { useFetch } from '../../hooks/useFetch'
import { listComplaints } from '../../lib/api'
import { formatTime, formatUSDT, humanize, shortAddr } from '../../lib/format'
import { R } from '../../lib/routes'

const TABS = [
  { key: 'new', label: 'New', match: (c) => c.stage === 'received' },
  { key: 'progress', label: 'In progress', match: (c) => c.stage === 'under_review' || c.stage === 'investigating' },
  { key: 'actioned', label: 'Action taken', match: (c) => c.stage === 'action_initiated' || c.stage === 'closed' },
  { key: 'all', label: 'All', match: () => true },
]

// Complaints arrive here; an officer opens one, reviews it and triggers the trace.
export default function Inbox() {
  const [tab, setTab] = useState('new')
  const { data, loading, error, reload } = useFetch(() => listComplaints(), [])
  useAlertListener((alert) => alert.type === 'COMPLAINT_RECEIVED' && reload())

  const counts = Object.fromEntries(TABS.map((t) => [t.key, (data ?? []).filter(t.match).length]))
  const shown = (data ?? []).filter(TABS.find((t) => t.key === tab).match)

  return (
    <>
      <PageHeader title="Complaint inbox" subtitle="New complaints wait here until an officer reviews them and triggers the trace" />
      <div className="space-y-4 p-6">
        <div role="tablist" aria-label="Complaint stages" className="flex flex-wrap gap-2">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                tab === t.key ? 'border-accent/60 bg-accent/15 text-accent' : 'border-line text-muted hover:text-ink'
              }`}
            >
              {t.label} <span className="ml-1 text-xs opacity-80">{counts[t.key]}</span>
            </button>
          ))}
        </div>

        {loading && !data ? (
          <Loading label="Loading complaints…" />
        ) : error && !data ? (
          <ErrorState error={error} onRetry={reload} />
        ) : shown.length === 0 ? (
          <Empty>{tab === 'new' ? 'No new complaints. Everything has been picked up.' : 'Nothing here.'}</Empty>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs text-muted uppercase">
                <tr>
                  {['Complaint', 'Received', 'Reporter', 'Wallet', 'Lost', 'Fraud type', 'State', 'Stage'].map((h) => (
                    <th key={h} className="px-4 py-2.5 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {shown.map((c) => (
                  <tr key={c.complaint_id} className="hover:bg-panel-2/60">
                    <td className="px-4 py-2.5">
                      <Link to={R.officerComplaint(c.complaint_id)} className="font-medium text-accent hover:underline">
                        {c.complaint_id}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-muted">{formatTime(c.created_at)}</td>
                    <td className="px-4 py-2.5">{c.reporter_name}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{shortAddr(c.wallet)}</td>
                    <td className="px-4 py-2.5">{c.amount == null ? '—' : formatUSDT(c.amount)}</td>
                    <td className="px-4 py-2.5">{c.fraud_type ? humanize(c.fraud_type) : '—'}</td>
                    <td className="px-4 py-2.5">{c.state ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      <StageBadge stage={c.stage} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
