import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useFetch } from '../../hooks/useFetch'
import { addIdentifier, getIdentifiers, getLeads } from '../../lib/api'
import { CHOKE_POINTS, IDENTIFIER_KINDS, PRIORITY_CLASSES, REQUESTS, ROLES } from '../../lib/colors'
import { formatTime } from '../../lib/format'

const pill = 'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset'

function LeadCard({ lead, identifier }) {
  return (
    <li className="space-y-2 rounded-lg border border-line bg-panel-2/40 p-3" data-testid="lead">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${pill} ${PRIORITY_CLASSES[lead.priority]}`}>{lead.priority}</span>
        <span className="text-sm font-semibold">{CHOKE_POINTS[lead.choke_point] ?? lead.choke_point}</span>
        <span className="text-sm text-muted">· {lead.holder}</span>
      </div>
      <p className="text-xs text-muted">
        <span className="text-ink/80">For </span>
        <span className="font-mono">{identifier ? `${IDENTIFIER_KINDS[identifier.kind]} ${identifier.value}` : lead.identifier_id}</span>
        <span> · {lead.rationale}</span>
      </p>
      <p className="text-xs">
        <span className="text-muted">Can tell us: </span>
        {lead.what_it_identifies}
      </p>
      <p className="flex flex-wrap gap-1.5">
        {lead.requests.map((r) => (
          <span key={r} className="rounded bg-line/60 px-1.5 py-0.5 text-[11px] text-ink/90">
            {REQUESTS[r] ?? r}
          </span>
        ))}
      </p>
    </li>
  )
}

function AddForm({ caseId, onAdded }) {
  const [kind, setKind] = useState('phone')
  const [value, setValue] = useState('')
  const [error, setError] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await addIdentifier(caseId, { kind, value })
      setValue('')
      onAdded()
    } catch (err) {
      setError(err)
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2" aria-label="Add an identifier">
      <select aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value)} className="rounded-md border border-line bg-bg px-2 py-1.5 text-sm">
        {Object.entries(IDENTIFIER_KINDS).map(([k, label]) => (
          <option key={k} value={k}>
            {label}
          </option>
        ))}
      </select>
      <input
        aria-label="Value"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Value"
        className="min-w-48 flex-1 rounded-md border border-line bg-bg px-2 py-1.5 font-mono text-sm focus:border-accent focus:outline-none"
      />
      <button type="submit" disabled={!value.trim()} className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 text-sm hover:bg-panel-2 disabled:opacity-50">
        <Plus className="size-4" /> Add
      </button>
      {error && (
        <p role="alert" className="w-full text-xs text-red-300">
          {error.message}
        </p>
      )}
    </form>
  )
}

// Who and what is involved in a case, and which institution to ask next. Suggestions only: nothing is sent from here.
export default function LeadsPanel({ caseId }) {
  const ids = useFetch(() => getIdentifiers(caseId), [caseId])
  const leads = useFetch(() => getLeads(caseId), [caseId])
  const reload = () => {
    ids.reload()
    leads.reload()
  }
  const byId = Object.fromEntries((ids.data ?? []).map((i) => [i.identifier_id, i]))

  return (
    <section className="space-y-5 rounded-lg border border-line bg-panel p-5" aria-label="Identifiers and leads">
      <div>
        <h2 className="text-sm font-semibold">Leads</h2>
        <p className="text-xs text-muted">Where the identity behind each identifier is held, and what to ask. Suspected until an officer confirms.</p>
      </div>
      {leads.error && !leads.data ? (
        <p role="alert" className="text-sm text-red-300">Could not load leads: {leads.error.message}</p>
      ) : !leads.data ? (
        <p className="text-sm text-muted">Loading leads…</p>
      ) : leads.data.length === 0 ? (
        <p className="text-sm text-muted">No leads yet. Add an identifier below, or send a request to get more.</p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {leads.data.map((l) => (
            <LeadCard key={l.lead_id} lead={l} identifier={byId[l.identifier_id]} />
          ))}
        </ul>
      )}

      <div className="space-y-3">
        <h2 className="text-sm font-semibold">Identifiers</h2>
        {ids.data?.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted uppercase">
                <tr>
                  {['Kind', 'Value', 'Role', 'Source', 'Confidence', 'Added'].map((h) => (
                    <th key={h} className="px-2 py-1.5 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {ids.data.map((i) => (
                  <tr key={i.identifier_id}>
                    <td className="px-2 py-1.5">{IDENTIFIER_KINDS[i.kind]}</td>
                    <td className="max-w-64 truncate px-2 py-1.5 font-mono" title={i.value}>
                      {i.value}
                      {i.label && <span className="ml-2 font-sans text-muted">{i.label}</span>}
                    </td>
                    <td className="px-2 py-1.5">{ROLES[i.role]}</td>
                    <td className="px-2 py-1.5 capitalize">{i.source}</td>
                    <td className="px-2 py-1.5">{Math.round(i.confidence * 100)}%</td>
                    <td className="px-2 py-1.5 text-muted">{formatTime(i.added_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <AddForm caseId={caseId} onAdded={reload} />
      </div>
    </section>
  )
}
