import { Link } from 'react-router-dom'
import { RiskBadge } from '../components/Badges'
import PageHeader from '../components/PageHeader'
import { Empty, ErrorState, Loading } from '../components/Status'
import { useFetch } from '../hooks/useFetch'
import { getCases } from '../lib/api'
import { formatDuration, formatUSDT, shortAddr } from '../lib/format'

// B1 stub: recent-cases table only. KPI tiles, charts and alert feed come in B7.
export default function Dashboard() {
  const { data: cases, loading, error, reload } = useFetch(getCases)

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Complaints, attribution and funds at a glance" />
      {loading ? (
        <Loading label="Loading cases…" />
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !cases.length ? (
        <Empty>No cases yet.</Empty>
      ) : (
        <div className="p-6">
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-panel-2 text-xs tracking-wide text-muted uppercase">
                <tr>
                  {['Case', 'Complaint', 'Wallet', 'Lost', 'Fraud type', 'State', 'Risk', 'VASP', 'Time to attribution', 'Status'].map(
                    (h) => (
                      <th key={h} className="px-4 py-2.5 font-medium">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {cases.map((c) => (
                  <tr key={c.case_id} className="hover:bg-panel-2/60">
                    <td className="px-4 py-2.5">
                      <Link to={`/cases/${c.case_id}`} className="font-medium text-accent hover:underline">
                        {c.case_id}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-muted">{c.complaint_id}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{shortAddr(c.wallet)}</td>
                    <td className="px-4 py-2.5">{formatUSDT(c.amount_lost)}</td>
                    <td className="px-4 py-2.5 capitalize">{c.fraud_type}</td>
                    <td className="px-4 py-2.5">{c.state}</td>
                    <td className="px-4 py-2.5">
                      <RiskBadge risk={c.risk} />
                    </td>
                    <td className="px-4 py-2.5">{c.vasp ?? <span className="text-muted">—</span>}</td>
                    <td className="px-4 py-2.5">{formatDuration(c.time_to_attribution_sec)}</td>
                    <td className="px-4 py-2.5 text-muted">{c.status.replaceAll('_', ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
