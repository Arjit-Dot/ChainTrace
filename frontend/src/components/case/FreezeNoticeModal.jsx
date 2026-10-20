import { Check, Copy, Download, FileWarning, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useFetch } from '../../hooks/useFetch'
import { getFreezeNotice } from '../../lib/api'
import { ErrorState, Loading } from '../common/Status'

const STATUS = {
  draft: 'bg-amber-500/15 text-amber-300 ring-amber-500/40',
  approved: 'bg-sky-500/15 text-sky-300 ring-sky-500/40',
  sent: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40',
}

const btn =
  'inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-panel-2'

const fullText = (n) => `To: ${n.to_vasp}${n.to_email ? ` <${n.to_email}>` : ''}\nSubject: ${n.subject}\n\n${n.body}`

function download(n) {
  const url = URL.createObjectURL(new Blob([fullText(n)], { type: 'text/plain' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: `${n.case_id}_freeze_notice.txt` })
  a.click()
  URL.revokeObjectURL(url)
}

function NoticeBody({ notice }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(fullText(notice))
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <>
      <dl className="grid grid-cols-[80px_1fr] gap-x-3 gap-y-1.5 border-b border-line px-5 py-3 text-sm">
        <dt className="text-muted">To</dt>
        <dd>
          {notice.to_vasp}
          {notice.to_email && <span className="text-accent"> &lt;{notice.to_email}&gt;</span>}
        </dd>
        <dt className="text-muted">Subject</dt>
        <dd>{notice.subject}</dd>
        <dt className="text-muted">Requests</dt>
        <dd className="flex flex-wrap gap-1.5">
          {notice.requested_actions.map((a) => (
            <span key={a} className="rounded bg-panel-2 px-2 py-0.5 text-xs">
              {a}
            </span>
          ))}
        </dd>
      </dl>
      <pre className="min-h-0 flex-1 overflow-auto bg-bg/60 px-5 py-4 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink/90">
        {notice.body}
      </pre>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3">
        <p className="text-xs text-muted">Fill in the [LEGAL SECTION] and officer placeholders before sending.</p>
        <div className="flex gap-2">
          <button onClick={copy} className={btn}>
            {copied ? <Check className="size-4 text-emerald-400" /> : <Copy className="size-4" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button onClick={() => download(notice)} className={btn}>
            <Download className="size-4" /> Download .txt
          </button>
        </div>
      </div>
    </>
  )
}

export default function FreezeNoticeModal({ caseId, onClose }) {
  const { data, loading, error, reload } = useFetch(() => getFreezeNotice(caseId), [caseId])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-line bg-panel shadow-2xl"
      >
        <div className="flex items-center gap-3 border-b border-line px-5 py-3">
          <FileWarning className="size-5 text-emerald-400" />
          <h2 className="font-semibold">Freeze notice · {caseId}</h2>
          {data && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold tracking-wider uppercase ring-1 ring-inset ${STATUS[data.status]}`}
            >
              {data.status}
            </span>
          )}
          <button onClick={onClose} title="Close" className="ml-auto text-muted hover:text-ink">
            <X className="size-5" />
          </button>
        </div>
        {loading ? (
          <Loading label="Drafting notice…" />
        ) : error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : (
          <NoticeBody notice={data} />
        )}
      </div>
    </div>
  )
}
