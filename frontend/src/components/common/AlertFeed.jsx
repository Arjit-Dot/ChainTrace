import { ArrowRightLeft, Bell, Landmark, Link2, ShieldAlert, Shuffle, Siren } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAlerts } from '../../hooks/useAlerts'
import { humanize, timeAgo } from '../../lib/format'

export const ALERT_ICONS = {
  FUNDS_MOVED: ArrowRightLeft,
  REACHED_VASP: Landmark,
  ENTERED_MIXER: Shuffle,
  NEW_COMPLAINT_LINKED: Link2,
  HIGH_RISK_WALLET: ShieldAlert,
  URGENCY_CHANGED: Siren,
}

export const SEVERITY = {
  critical: { text: 'text-red-300', bar: 'border-l-red-500', dot: 'bg-red-500' },
  warning: { text: 'text-amber-300', bar: 'border-l-amber-400', dot: 'bg-amber-400' },
  info: { text: 'text-sky-300', bar: 'border-l-sky-400', dot: 'bg-sky-400' },
}

export function AlertLine({ alert, onOpen }) {
  const Icon = ALERT_ICONS[alert.type] ?? Bell
  const sev = SEVERITY[alert.severity] ?? SEVERITY.info
  return (
    <div className="flex gap-2.5">
      <Icon className={`mt-0.5 size-4 shrink-0 ${sev.text}`} />
      <div className="min-w-0 space-y-0.5">
        <p className={`text-[11px] font-semibold tracking-wide uppercase ${sev.text}`}>{humanize(alert.type.toLowerCase())}</p>
        <p className="text-sm text-ink">{alert.message}</p>
        <p className="text-xs text-muted">
          <Link to={`/cases/${alert.case_id}`} onClick={onOpen} className="text-accent hover:underline">
            {alert.case_id}
          </Link>{' '}
          · {timeAgo(alert.timestamp)}
        </p>
      </div>
    </div>
  )
}

// Header bell: unread count, and a dropdown with the latest alerts (history + live).
export default function AlertBell() {
  const { feed, unread, connected, markRead } = useAlerts()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    markRead()
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    const esc = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open, unread, markRead])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        title={connected ? 'Alerts (live)' : 'Alerts (reconnecting…)'}
        className="relative text-muted hover:text-ink"
      >
        <Bell className="size-5" />
        {unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 grid min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[10px] leading-4 font-bold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute top-8 right-0 z-40 w-96 overflow-hidden rounded-lg border border-line bg-panel shadow-2xl">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Alerts</h2>
            <span className="flex items-center gap-1.5 text-xs text-muted">
              <span className={`size-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              {connected ? 'Live' : 'Reconnecting…'}
            </span>
          </div>
          {feed.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">No alerts yet.</p>
          ) : (
            <ul className="max-h-[28rem] divide-y divide-line overflow-auto">
              {feed.map((a) => (
                <li key={a.id} className={`border-l-2 px-4 py-3 ${(SEVERITY[a.severity] ?? SEVERITY.info).bar}`}>
                  <AlertLine alert={a} onOpen={() => setOpen(false)} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
