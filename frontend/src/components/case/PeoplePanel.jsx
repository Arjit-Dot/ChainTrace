import { Download, Link2, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useFetch } from '../../hooks/useFetch'
import { dossierUrl, getPeople, getReferral, referCase } from '../../lib/api'
import { IDENTIFIER_KINDS } from '../../lib/colors'
import { formatTime, formatUSDT } from '../../lib/format'
import { R } from '../../lib/routes'

const STRENGTH = { strong: 'bg-emerald-500/15 text-emerald-300', moderate: 'bg-amber-500/15 text-amber-300', weak: 'bg-slate-500/15 text-slate-300' }

function Person({ p }) {
  const operator = p.role === 'operator_suspected'
  const pct = Math.round(p.confidence * 100)
  return (
    <li className={`space-y-2 rounded-lg border p-3 ${operator ? 'border-amber-400/40 bg-amber-400/5' : 'border-line bg-panel-2/40'}`} data-testid="person" data-role={p.role}>
      <div className="flex flex-wrap items-center gap-2">
        <UserRound className="size-4 text-muted" />
        <span className="text-sm font-semibold">{p.name}</span>
        <span className="rounded-full bg-line/60 px-2 py-0.5 text-[11px]">{operator ? 'Suspected operator' : 'Holder of a mule account'}</span>
        <span className="ml-auto flex items-center gap-2 text-xs" title="How strongly the evidence points to this person (an inference)">
          <span className="h-1.5 w-20 overflow-hidden rounded bg-line"><span className="block h-full bg-amber-400" style={{ width: `${pct}%` }} /></span>
          {pct}%
        </span>
      </div>
      <p className="text-xs text-muted">{p.basis}</p>
      <ul className="list-disc space-y-0.5 pl-5 text-xs">
        {p.evidence.map((e) => (
          <li key={e.request_id}>
            Named by {e.institution} ({e.field}) in <Link to={R.officerCase(e.case_id)} className="text-accent hover:underline">{e.case_id}</Link>
          </li>
        ))}
      </ul>
      {p.identifiers.length > 0 && (
        <p className="flex flex-wrap gap-1.5 text-[11px]">
          {p.identifiers.map((i) => (
            <span key={i} className="rounded bg-line/60 px-1.5 py-0.5 font-mono">{i}</span>
          ))}
        </p>
      )}
    </li>
  )
}

function Referral({ caseId }) {
  const { data, error, reload } = useFetch(() => getReferral(caseId), [caseId])
  const [agency, setAgency] = useState('')
  const [note, setNote] = useState('')
  const [fail, setFail] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    setFail(null)
    try {
      await referCase(caseId, { agency: agency.trim(), note: note.trim() || null })
      reload()
    } catch (err) {
      setFail(err)
    }
  }
  if (data)
    return (
      <p className="rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs" data-testid="referral">
        Referred to <span className="font-semibold">{data.agency}</span> on {formatTime(data.referred_at)}.
        {data.note && <span> {data.note}</span>}
        <span className="mt-1 block font-mono text-[11px] text-muted">Dossier SHA-256 {data.dossier_sha256}</span>
      </p>
    )
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2" aria-label="Refer to an investigating agency">
      <input aria-label="Agency" value={agency} onChange={(e) => setAgency(e.target.value)} placeholder="Investigating agency" className="min-w-52 flex-1 rounded-md border border-line bg-bg px-2 py-1.5 text-sm focus:border-accent focus:outline-none" />
      <input aria-label="Note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional)" className="min-w-52 flex-1 rounded-md border border-line bg-bg px-2 py-1.5 text-sm focus:border-accent focus:outline-none" />
      <button type="submit" disabled={!agency.trim()} className="rounded-md border border-accent/60 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-50">
        Record referral
      </button>
      {(fail || (error && error.message && !/not been referred/i.test(error.message))) && (
        <p role="alert" className="w-full text-xs text-red-300">{(fail ?? error).message}</p>
      )}
    </form>
  )
}

// Which other complaints this one is connected to, who the institutions' replies name, and the dossier for the agency.
// Everything here is an inference for an officer to check; the legal action itself belongs to the agency.
export default function PeoplePanel({ caseId, version = 0 }) {
  const { data, error } = useFetch(() => getPeople(caseId), [caseId, version])
  const cluster = data?.cluster
  return (
    <section className="space-y-4 rounded-lg border border-line bg-panel p-5" aria-label="Linked cases and suspected people">
      <div>
        <h2 className="text-sm font-semibold">Linked cases and suspected people</h2>
        <p className="text-xs text-muted">
          Cases are linked by shared identifiers; people are named only by institutions&apos; replies. These are inferences to check, not findings, and a holder of a
          mule account is often a victim too.
        </p>
      </div>
      {error && !data ? (
        <p role="alert" className="text-sm text-red-300">Could not load this: {error.message}</p>
      ) : !data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          {cluster ? (
            <div className="space-y-3" data-testid="cluster">
              <p className="flex items-start gap-2 text-sm">
                <Link2 className="mt-0.5 size-4 shrink-0 text-accent" /> {cluster.summary}
              </p>
              <p className="text-xs text-muted">
                Linked cases:{' '}
                {cluster.case_ids.map((c, i) => (
                  <span key={c}>
                    {i > 0 && ', '}
                    {c === caseId ? <span className="font-semibold text-ink">{c} (this case)</span> : <Link to={R.officerCase(c)} className="text-accent hover:underline">{c}</Link>}
                  </span>
                ))}
                {' · '}
                {formatUSDT(cluster.total_lost)} lost{cluster.states.length ? ` · ${cluster.states.join(', ')}` : ''}
              </p>
              <ul className="grid gap-1.5 text-xs sm:grid-cols-2" aria-label="Shared identifiers">
                {cluster.shared.map((s) => (
                  <li key={`${s.kind}:${s.value}`} className="flex items-center gap-2 rounded border border-line px-2 py-1">
                    <span className={`rounded px-1.5 text-[10px] uppercase ${STRENGTH[s.strength]}`}>{s.strength}</span>
                    <span className="text-muted">{IDENTIFIER_KINDS[s.kind]}</span>
                    <span className="truncate font-mono" title={s.value}>{s.value}</span>
                    <span className="ml-auto text-muted">{s.case_ids.join(', ')}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-muted">This case shares no identifier with another case.</p>
          )}
          {data.people.length ? (
            <ul className="space-y-3">
              {data.people.map((p) => (
                <Person key={`${p.role}:${p.name}`} p={p} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No institution has named a person yet. Send the requests under Leads, or run the demo investigation.</p>
          )}
        </>
      )}
      <div className="space-y-3 border-t border-line pt-4">
        <h3 className="text-sm font-semibold">Referral dossier</h3>
        <p className="text-xs text-muted">
          One PDF for the investigating agency: the money trail, mules, identifiers, requests and replies, linked cases, and a checklist of records, inferences and gaps.
          It leaves out the victim&apos;s personal details. Any arrest or legal action is for the agency.
        </p>
        <a
          href={dossierUrl(caseId)}
          download
          className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-sm hover:bg-panel-2"
        >
          <Download className="size-4" /> Download referral dossier (PDF)
        </a>
        <Referral caseId={caseId} />
      </div>
    </section>
  )
}
