import { Landmark, MapPin, Share2, Users, Wallet } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import PageHeader from '../components/common/PageHeader'
import { Empty, ErrorState, Loading } from '../components/common/Status'
import NetworkGraph, { NETWORK_TYPES } from '../components/network/NetworkGraph'
import { useAlertListener } from '../hooks/useAlerts'
import { useFetch } from '../hooks/useFetch'
import { getNetworks } from '../lib/api'
import { formatUSDT } from '../lib/format'

function NetworkLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {Object.entries(NETWORK_TYPES).map(([k, t]) => (
        <li key={k} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full ring-1 ring-black/40" style={{ background: t.color }} />
          {t.label}
        </li>
      ))}
    </ul>
  )
}

function Fact({ icon: Icon, label, children }) {
  return (
    <div className="flex gap-3">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted" />
      <div>
        <p className="text-xs text-muted">{label}</p>
        <div className="text-sm">{children}</div>
      </div>
    </div>
  )
}

function NetworkCard({ net }) {
  const shared = net.nodes.filter((n) => n.type === 'wallet')
  return (
    <section className="space-y-4 self-start rounded-lg border border-line bg-panel p-4">
      <div>
        <p className="text-xs tracking-wide text-muted uppercase">Organised network</p>
        <h2 className="text-xl font-semibold">{net.network_id}</h2>
      </div>
      <Fact icon={Users} label="Victims">
        {net.victim_count} complaints
      </Fact>
      <Fact icon={Wallet} label="Total lost">
        {formatUSDT(net.total_amount)}
      </Fact>
      <Fact icon={MapPin} label="States">
        {net.states.join(', ')}
      </Fact>
      <Fact icon={Landmark} label="Receiving exchange">
        {net.vasp ?? <span className="text-muted">Not identified</span>}
      </Fact>
      <Fact icon={Share2} label="Linked by">
        <ul className="space-y-0.5">
          {shared.map((w) => (
            <li key={w.id}>
              {w.label}
              <span className="block font-mono text-xs break-all text-muted">{w.id}</span>
            </li>
          ))}
        </ul>
      </Fact>
      <div>
        <p className="mb-1.5 text-xs text-muted">Complaints</p>
        <div className="flex flex-wrap gap-1.5">
          {net.complaint_ids.map((id) => (
            <Link
              key={id}
              to={`/cases/${id}`}
              className="rounded border border-line px-2 py-0.5 text-xs text-accent hover:bg-panel-2"
            >
              {id}
            </Link>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted">
        Complaints are linked when their traces share a wallet the scammers control (reported wallet, pass-through, or
        exchange deposit address). Exchange hot wallets, bridges and mixers never link cases on their own.
      </p>
    </section>
  )
}

export default function NetworkView() {
  const { data, loading, error, reload } = useFetch(getNetworks)
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  useAlertListener((a) => a.type === 'NEW_COMPLAINT_LINKED' && reload())

  const nets = data ?? []
  const net = nets.find((n) => n.network_id === params.get('id')) ?? nets[0]

  return (
    <>
      <PageHeader title="Networks" subtitle="Complaints linked by shared scammer wallets" />
      {loading && !data ? (
        <Loading label="Finding linked complaints…" />
      ) : error && !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !nets.length ? (
        <Empty>No linked complaints yet: every case so far stands alone.</Empty>
      ) : (
        <div className="space-y-4 p-6">
          <div className="flex flex-wrap gap-2" role="tablist">
            {nets.map((n) => (
              <button
                key={n.network_id}
                role="tab"
                aria-selected={n.network_id === net.network_id}
                onClick={() => setParams({ id: n.network_id })}
                className={`rounded-lg border px-3 py-2 text-left text-sm ${
                  n.network_id === net.network_id
                    ? 'border-accent/60 bg-accent/10'
                    : 'border-line bg-panel hover:bg-panel-2'
                }`}
              >
                <span className="font-semibold">{n.network_id}</span>
                <span className="block text-xs text-muted">
                  {n.victim_count} complaints · {formatUSDT(n.total_amount)}
                  {n.vasp ? ` · ${n.vasp}` : ''}
                </span>
              </button>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
            <section className="flex flex-col rounded-lg border border-line bg-panel">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
                <h2 className="text-sm font-semibold">{net.network_id}: how the complaints connect</h2>
                <NetworkLegend />
              </div>
              <div className="h-[460px]">
                <NetworkGraph network={net} onOpenCase={(id) => navigate(`/cases/${id}`)} />
              </div>
              <p className="border-t border-line px-4 py-2 text-xs text-muted">
                Click a complaint to open its case.
              </p>
            </section>
            <NetworkCard net={net} />
          </div>
        </div>
      )}
    </>
  )
}
