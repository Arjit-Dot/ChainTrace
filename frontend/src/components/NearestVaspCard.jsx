import { Building2, Crosshair, Mail, SearchX } from 'lucide-react'
import { formatPct, formatTime, formatUSDT, shortAddr } from '../lib/format'
import CopyButton from './CopyButton'

const barColor = (c) => (c >= 0.9 ? 'bg-emerald-400' : c >= 0.6 ? 'bg-amber-400' : 'bg-red-400')

function NoVasp({ graph }) {
  const mixer = graph.nodes.some((n) => n.type === 'mixer')
  const bridge = graph.nodes.find((n) => n.type === 'bridge')
  const reason = mixer
    ? 'Funds entered a mixer. Exits cannot be followed reliably.'
    : bridge
      ? `Funds crossed ${bridge.label ?? 'a bridge'}. The trace continues on the destination chain.`
      : 'No labeled exchange was reached within the traced hops.'
  return (
    <section className="rounded-lg border border-line bg-panel p-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <SearchX className="size-4 text-muted" /> Nearest VASP
      </h2>
      <p className="mt-3 text-lg font-semibold text-muted">No exchange reached</p>
      <p className="mt-1 text-sm text-muted">{reason}</p>
      <p className="mt-3 text-xs text-muted">Monitor the wallet and re-trace when funds move.</p>
    </section>
  )
}

// The answer judges remember: which exchange got the money, and how sure we are.
export default function NearestVaspCard({ vasp, graph, onLocate }) {
  if (!vasp) return <NoVasp graph={graph} />
  const sure = vasp.method === 'deterministic'

  return (
    <section className="rounded-lg border border-emerald-500/40 bg-panel shadow-[0_0_30px_-12px] shadow-emerald-500/40">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Building2 className="size-4 text-emerald-400" /> Nearest VASP
        </h2>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wider uppercase ring-1 ring-inset ${
            sure ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40' : 'bg-amber-500/15 text-amber-300 ring-amber-500/40'
          }`}
          title={sure ? 'Matched a labeled address' : 'Inferred from deposit/sweep behaviour'}
        >
          {vasp.method}
        </span>
      </div>

      <div className="space-y-4 p-4 text-sm">
        <div>
          <p className="text-2xl font-bold tracking-tight">{vasp.vasp}</p>
          <div className="mt-1 flex items-center gap-1.5 font-mono text-xs text-muted">
            deposit {shortAddr(vasp.deposit_address, 8)}
            <CopyButton text={vasp.deposit_address} />
            {onLocate && (
              <button onClick={onLocate} title="Show on graph" className="text-muted hover:text-ink">
                <Crosshair className="size-3.5" />
              </button>
            )}
          </div>
        </div>

        <div>
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-muted">Confidence</span>
            <span className="font-semibold">{formatPct(vasp.confidence)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-panel-2">
            <div className={`h-full rounded-full ${barColor(vasp.confidence)}`} style={{ width: formatPct(vasp.confidence) }} />
          </div>
        </div>

        <dl className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <dt className="text-muted">Amount</dt>
            <dd className="font-semibold">{formatUSDT(vasp.amount)}</dd>
          </div>
          <div>
            <dt className="text-muted">Hops</dt>
            <dd className="font-semibold">{vasp.hops}</dd>
          </div>
          <div>
            <dt className="text-muted">Reached</dt>
            <dd className="font-semibold">{formatTime(vasp.timestamp)}</dd>
          </div>
        </dl>

        <div>
          <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">Evidence</h3>
          <ul className="list-disc space-y-1 pl-4 text-xs">
            {vasp.evidence.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>

        {vasp.contact && (
          <a href={`mailto:${vasp.contact}`} className="flex items-center gap-2 text-xs text-accent hover:underline">
            <Mail className="size-3.5" /> {vasp.contact}
          </a>
        )}
      </div>
    </section>
  )
}
