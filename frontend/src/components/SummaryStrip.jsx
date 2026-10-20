import { formatDuration, formatUSDT, humanize } from '../lib/format'
import { RiskBadge, SourceBadge } from './Badges'

function Stat({ label, children, highlight }) {
  return (
    <div className={`rounded-lg border bg-panel px-4 py-3 ${highlight ? 'border-amber-400/50' : 'border-line'}`}>
      <p className="text-xs text-muted">{label}</p>
      <div className={`mt-1 text-lg font-semibold ${highlight ? 'animate-pulse text-amber-300' : ''}`}>{children}</div>
    </div>
  )
}

export default function SummaryStrip({ trace }) {
  const s = trace.summary
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
      <Stat label="Amount lost">{formatUSDT(trace.amount_lost)}</Stat>
      <Stat label="Total traced">{formatUSDT(s.total_traced)}</Stat>
      <Stat label="Idle funds" highlight={s.idle_funds > 0}>
        {formatUSDT(s.idle_funds)}
      </Stat>
      <Stat label="Hops · nodes">
        {s.hops} · {s.nodes}
      </Stat>
      <Stat label="Time to attribution">{formatDuration(s.time_to_attribution_sec)}</Stat>
      <Stat label="Case risk">
        <div className="flex flex-col items-start gap-1">
          <RiskBadge risk={trace.risk} score={trace.risk_score} />
          <span className="text-xs font-normal text-muted">{humanize(trace.typology)}</span>
        </div>
      </Stat>
      <Stat label="Data source">
        <SourceBadge source={trace.source} />
      </Stat>
    </div>
  )
}
