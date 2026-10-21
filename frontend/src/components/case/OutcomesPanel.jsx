import { useFetch } from '../../hooks/useFetch'
import { getMules, getOutcomes } from '../../lib/api'
import { ENDPOINT_KINDS, ONWARD, OUTCOME_STATUS } from '../../lib/colors'
import { formatUSDT, shortAddr } from '../../lib/format'
import { RiskBadge } from '../common/Badges'

const pill = 'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset'

function OutcomeCard({ o }) {
  const status = OUTCOME_STATUS[o.status]
  return (
    <li className="space-y-2 rounded-lg border border-line bg-panel-2/40 p-4" data-testid="outcome" data-kind={o.kind}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${pill} ${status.classes}`}>{status.label}</span>
        <span className="text-xs text-muted uppercase">{ENDPOINT_KINDS[o.kind]}</span>
      </div>
      <h3 className="text-sm font-semibold">{o.title}</h3>
      <p className="text-xs text-muted">
        <span className="font-mono">{o.kind === 'bank_account' ? o.subject : shortAddr(o.subject, 8)}</span>
        {o.amount != null && <span> · {formatUSDT(o.amount)}</span>}
      </p>
      <ol className="list-decimal space-y-1 pl-5 text-xs">
        {o.handling.map((h) => (
          <li key={h}>{h}</li>
        ))}
      </ol>
      {o.lead_ids.length > 0 && (
        <p className="text-[11px] text-muted">
          {o.lead_ids.length === 1 ? '1 matching lead' : `${o.lead_ids.length} matching leads`} below
        </p>
      )}
    </li>
  )
}

export function OutcomesPanel({ caseId, version = 0 }) {
  const { data, error } = useFetch(() => getOutcomes(caseId), [caseId, version])
  return (
    <section className="space-y-3 rounded-lg border border-line bg-panel p-5" aria-label="Where the money went">
      <div>
        <h2 className="text-sm font-semibold">Where the money went</h2>
        <p className="text-xs text-muted">Each kind of endpoint needs a different response.</p>
      </div>
      {error && !data ? (
        <p role="alert" className="text-sm text-red-300">Could not load this: {error.message}</p>
      ) : !data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {data.map((o) => (
            <OutcomeCard key={o.outcome_id} o={o} />
          ))}
        </ul>
      )}
    </section>
  )
}

export function MulesPanel({ caseId, version = 0 }) {
  const { data, error } = useFetch(() => getMules(caseId), [caseId, version])
  return (
    <section className="space-y-3 rounded-lg border border-line bg-panel p-5" aria-label="Suspected mules">
      <div>
        <h2 className="text-sm font-semibold">Suspected mules</h2>
        <p className="text-xs text-muted">Wallets that passed the money on and accounts the victim paid. Suspected only: a mule account is often held by someone who was tricked.</p>
      </div>
      {error && !data ? (
        <p role="alert" className="text-sm text-red-300">Could not load this: {error.message}</p>
      ) : !data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : data.length === 0 ? (
        <p className="text-sm text-muted">No suspected mules found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-muted uppercase">
              <tr>
                {['Account', 'Type', 'Risk', 'Received', 'Passed on', 'Sent to', 'Why'].map((h) => (
                  <th key={h} className="px-2 py-1.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line align-top">
              {data.map((m) => (
                <tr key={`${m.kind}:${m.value}`} data-testid="mule">
                  <td className="px-2 py-2 font-mono">{m.kind === 'wallet' ? shortAddr(m.value, 8) : m.value}</td>
                  <td className="px-2 py-2">{m.kind === 'wallet' ? 'Wallet' : `Bank account${m.label ? ` · ${m.label}` : ''}`}</td>
                  <td className="px-2 py-2">{m.risk ? <RiskBadge risk={m.risk} score={m.risk_score} /> : <span className="text-muted">Not scored</span>}</td>
                  <td className="px-2 py-2">{m.kind === 'wallet' ? formatUSDT(m.received) : '—'}</td>
                  <td className="px-2 py-2">{m.kind === 'wallet' ? formatUSDT(m.forwarded) : '—'}</td>
                  <td className="px-2 py-2">{m.onward.length ? m.onward.map((k) => ONWARD[k] ?? k).join(', ') : '—'}</td>
                  <td className="px-2 py-2">
                    <ul className="list-disc space-y-0.5 pl-4">
                      {m.reasons.map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
