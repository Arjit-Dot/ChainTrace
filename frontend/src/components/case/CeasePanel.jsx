import { FileText, Loader2, ShieldOff } from 'lucide-react'
import { useState } from 'react'
import { StageBadge } from '../common/Badges'
import { useFetch } from '../../hooks/useFetch'
import { closeComplaint, getCease, reportUrl, startCease } from '../../lib/api'
import { CHOKE_POINTS, REQUESTS, REQUEST_STATUS } from '../../lib/colors'

const btn = 'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50'
const CHIP = {
  not_drafted: 'bg-slate-500/15 text-slate-300', draft: 'bg-amber-500/15 text-amber-300', approved: 'bg-sky-500/15 text-sky-300',
  sent: 'bg-emerald-500/15 text-emerald-300', acknowledged: 'bg-emerald-500/15 text-emerald-300', replied: 'bg-emerald-500/15 text-emerald-300',
  closed: 'bg-slate-500/15 text-slate-300',
}

// The officer's last step: the evidence report, then a freeze, hold or takedown request for every endpoint that needs one.
// Drafting is one click; approving and sending stay with the officer in the Requests panel. The first one sent moves the
// complaint to "Action initiated", and the citizen's tracker changes to a fixed generic sentence (shown here so the officer knows).
export default function CeasePanel({ caseId, version = 0, onChange = () => {} }) {
  const { data, error, reload } = useFetch(() => getCease(caseId), [caseId, version])
  const [busy, setBusy] = useState(null)
  const [fail, setFail] = useState(null)
  const [drafted, setDrafted] = useState(null)

  const act = async (name, fn, after) => {
    setBusy(name)
    setFail(null)
    try {
      const out = await fn()
      after?.(out)
      reload()
      onChange()
    } catch (e) {
      setFail(e)
    } finally {
      setBusy(null)
    }
  }
  const closable = data && (data.stage === 'investigating' || data.stage === 'action_initiated')
  const missing = data ? data.items.filter((i) => i.status === 'not_drafted').length : 0

  return (
    <section className="space-y-4 rounded-lg border border-line bg-panel p-5" aria-label="Report and cease">
      <div>
        <h2 className="text-sm font-semibold">Report and cease</h2>
        <p className="text-xs text-muted">
          The last step: the evidence report, then a freeze, hold or takedown request for every endpoint that needs one. Drafting is one click; you approve and send each
          request under Requests above. Nothing is transmitted in this demo.
        </p>
      </div>
      {error && !data ? (
        <p role="alert" className="text-sm text-red-300">Could not load this: {error.message}</p>
      ) : !data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <a href={reportUrl(caseId)} download className={`${btn} border-line hover:bg-panel-2`}>
              <FileText className="size-4" /> Download evidence report (PDF)
            </a>
            <button
              type="button"
              onClick={() => act('draft', () => startCease(caseId), (out) => setDrafted(out.drafts_created))}
              disabled={!!busy || (data.items.length > 0 && missing === 0)}
              className={`${btn} border-accent/60 text-accent hover:bg-accent/10`}
            >
              {busy === 'draft' ? <Loader2 className="size-4 animate-spin" /> : <ShieldOff className="size-4" />} Draft the freeze, hold and takedown requests
            </button>
            {drafted != null && (
              <span role="status" className="text-xs text-emerald-300">
                {drafted ? `${drafted} request${drafted === 1 ? '' : 's'} drafted.` : 'Nothing new to draft.'}
              </span>
            )}
          </div>

          {data.items.length === 0 ? (
            <p className="text-sm text-muted">Nothing on this case can be frozen, held or taken down yet. Any new identifier a reply adds may change that.</p>
          ) : (
            <ul className="space-y-2" aria-label="Freeze, hold and takedown requests">
              {data.items.map((i) => (
                <li key={`${i.lead_id}:${i.kind}`} className="flex flex-wrap items-center gap-2 rounded-md border border-line px-3 py-2 text-sm" data-testid="cease-item">
                  <span className="font-medium">{REQUESTS[i.kind] ?? i.kind}</span>
                  <span className="text-muted">to {i.holder}</span>
                  <span className="rounded bg-line/60 px-1.5 py-0.5 text-[11px]">{CHOKE_POINTS[i.choke_point] ?? i.choke_point}</span>
                  <span className="truncate font-mono text-xs text-muted" title={i.subject}>{i.subject}</span>
                  <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] ${CHIP[i.status] ?? CHIP.draft}`}>
                    {i.status === 'not_drafted' ? 'Not drafted' : REQUEST_STATUS[i.status] ?? i.status}
                  </span>
                  {i.note && <p className="w-full text-xs text-amber-300">{i.note}</p>}
                </li>
              ))}
            </ul>
          )}

          {data.complaint_id && (
            <div className="space-y-2 border-t border-line pt-4" data-testid="cease-complaint">
              <p className="flex flex-wrap items-center gap-2 text-sm">
                Complaint {data.complaint_id} <StageBadge stage={data.stage} />
                {data.started ? <span className="text-xs text-emerald-300">Action has started.</span> : <span className="text-xs text-muted">Moves to Action initiated when the first request is sent.</span>}
              </p>
              <p className="text-xs text-muted">
                The citizen&apos;s tracker says only: <span className="text-ink">&ldquo;{data.citizen_sees}&rdquo;</span>
              </p>
              {closable && (
                <button
                  type="button"
                  onClick={() => act('close', () => closeComplaint(data.complaint_id))}
                  disabled={!!busy}
                  className={`${btn} border-line hover:bg-panel-2`}
                >
                  {busy === 'close' && <Loader2 className="size-4 animate-spin" />} Close the complaint
                </button>
              )}
              {closable && <p className="text-xs text-muted">Closing does not close any open request. The citizen is pointed to the helpline.</p>}
            </div>
          )}
        </>
      )}
      {fail && <p role="alert" className="text-sm text-red-300">{fail.message}</p>}
    </section>
  )
}
