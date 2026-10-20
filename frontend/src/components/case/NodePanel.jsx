import { ArrowDownLeft, ArrowUpRight, X } from 'lucide-react'
import { NODE_LABELS, nodeColor } from '../../lib/colors'
import { formatTime, formatUSDT, humanize, shortAddr } from '../../lib/format'
import { ReportedBadge, RiskBadge } from '../common/Badges'
import CopyButton from '../common/CopyButton'

function TxRow({ tx, other, dir }) {
  const Icon = dir === 'in' ? ArrowDownLeft : ArrowUpRight
  return (
    <li className="flex items-start gap-2 py-2 text-xs">
      <Icon className={`mt-0.5 size-3.5 shrink-0 ${dir === 'in' ? 'text-emerald-400' : 'text-orange-400'}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold">{formatUSDT(tx.amount, tx.token)}</span>
          <span className="text-muted">{formatTime(tx.timestamp)}</span>
        </div>
        <div className="mt-0.5 flex items-center gap-1.5 text-muted">
          {dir === 'in' ? 'from' : 'to'} <span className="font-mono text-ink">{shortAddr(other)}</span>
          {tx.edge_type !== 'transfer' && (
            <span className="rounded bg-panel-2 px-1 py-px text-[10px] uppercase">{tx.edge_type.replace('_', ' ')}</span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-1 font-mono text-[10px] text-muted">
          tx {shortAddr(tx.tx_hash, 10)} <CopyButton text={tx.tx_hash} />
        </div>
      </div>
    </li>
  )
}

export default function NodePanel({ node, graph, onClose }) {
  const incoming = graph.edges.filter((e) => e.target === node.id)
  const outgoing = graph.edges.filter((e) => e.source === node.id)

  return (
    <section className="rounded-lg border border-line bg-panel">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <span className="size-2.5 rounded-full" style={{ background: nodeColor(node.type) }} />
          {node.label ?? NODE_LABELS[node.type]}
        </h2>
        <button onClick={onClose} title="Close" className="text-muted hover:text-ink">
          <X className="size-4" />
        </button>
      </div>

      <div className="space-y-4 p-4 text-sm">
        <div className="flex items-center gap-2 rounded-md bg-panel-2 px-2.5 py-2 font-mono text-xs break-all">
          <span className="flex-1">{node.id}</span>
          <CopyButton text={node.id} />
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <dt className="text-muted">Type</dt>
          <dd>{NODE_LABELS[node.type]}</dd>
          <dt className="text-muted">Chain</dt>
          <dd className="uppercase">{node.chain}</dd>
          <dt className="text-muted">Hop</dt>
          <dd>{node.hop === -1 ? 'Victim (−1)' : node.hop}</dd>
          <dt className="text-muted">Typology</dt>
          <dd>{humanize(node.typology)}</dd>
          <dt className="text-muted">Risk</dt>
          <dd>
            {node.risk ? <RiskBadge risk={node.risk} score={node.risk_score} /> : <ReportedBadge />}
          </dd>
        </dl>

        {node.idle_balance > 0 && (
          <div className="animate-pulse rounded-md border border-amber-400/50 bg-amber-400/10 px-3 py-2 text-amber-200">
            <p className="text-xs">Idle funds still here</p>
            <p className="text-lg font-semibold">{formatUSDT(node.idle_balance)}</p>
          </div>
        )}

        {node.reasons.length > 0 && (
          <div>
            <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">
              {node.risk ? 'Why this risk' : 'Why it matters'}
            </h3>
            <ul className="list-disc space-y-1 pl-4 text-xs">
              {node.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
            Transactions ({incoming.length} in · {outgoing.length} out)
          </h3>
          <ul className="divide-y divide-line">
            {incoming.map((tx) => (
              <TxRow key={tx.tx_hash} tx={tx} other={tx.source} dir="in" />
            ))}
            {outgoing.map((tx) => (
              <TxRow key={tx.tx_hash} tx={tx} other={tx.target} dir="out" />
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
