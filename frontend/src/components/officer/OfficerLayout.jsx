import { ArrowLeft, Inbox, LayoutDashboard, Radar, Share2 } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { health } from '../../lib/api'
import { useFetch } from '../../hooks/useFetch'
import { AlertsProvider, useAlertListener } from '../../hooks/useAlerts'
import { useEffect, useState } from 'react'
import { listComplaints } from '../../lib/api'
import { R } from '../../lib/routes'
import AlertBell from '../common/AlertFeed'
import Toasts from '../common/Toasts'

const NAV = [
  { to: R.officerInbox, label: 'Inbox', icon: Inbox, badge: true },
  { to: R.officer, label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: R.officerNetworks, label: 'Networks', icon: Share2 },
]

// How many complaints are still waiting for an officer. Refreshes when a new one arrives.
function NewCount() {
  const [n, setN] = useState(0)
  const load = () => listComplaints('received').then((c) => setN(c.length), () => {})
  useEffect(() => {
    load()
  }, [])
  useAlertListener((a) => a.type === 'COMPLAINT_RECEIVED' && load())
  return n ? (
    <span aria-label={`${n} new complaints`} className="ml-auto rounded-full bg-accent px-1.5 text-[11px] font-semibold text-bg">
      {n}
    </span>
  ) : null
}

function ApiStatus() {
  const { data, error, loading } = useFetch(health)
  const ok = data?.status === 'ok'
  const color = loading ? 'bg-amber-400' : ok ? 'bg-emerald-400' : 'bg-red-500'
  const text = loading ? 'API…' : ok ? `API ok · v${data.contract_version}` : 'API offline'
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted" title={error?.message}>
      <span className={`size-2 rounded-full ${color}`} /> {text}
    </span>
  )
}

export default function OfficerLayout() {
  return (
    <AlertsProvider>
      <div className="flex h-full" data-area="officer">
        <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-panel">
          <div className="flex items-center gap-2 px-5 py-4 text-lg font-bold tracking-tight">
            <Radar className="size-5 text-accent" /> ChainTrace
          </div>
          <p className="-mt-3 px-5 pb-3 text-[11px] tracking-wide text-muted uppercase">Officer console</p>
          <nav className="flex flex-col gap-1 px-3">
            {NAV.map(({ to, label, icon: Icon, end, badge }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                    isActive ? 'bg-accent/15 text-accent' : 'text-muted hover:bg-panel-2 hover:text-ink'
                  }`
                }
              >
                <Icon className="size-4" /> {label}
                {badge && <NewCount />}
              </NavLink>
            ))}
          </nav>
          <Link to={R.gateway} className="mt-auto mx-3 mb-1 flex items-center gap-2 rounded-md px-3 py-2 text-xs text-muted hover:bg-panel-2 hover:text-ink">
            <ArrowLeft className="size-3.5" /> Back to the portal
          </Link>
          <p className="px-5 pb-4 text-[11px] leading-snug text-muted">
            Demo build. All names and addresses are fictional; NCRP / SAHYOG links are simulated.
          </p>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-end gap-5 border-b border-line bg-panel/60 px-6">
            <ApiStatus />
            {/* Demo Mode toggle: wired in B8 */}
            <label className="flex cursor-not-allowed items-center gap-2 text-xs text-muted" title="Demo Mode arrives in B8">
              <span className="relative inline-flex h-4 w-7 rounded-full bg-line">
                <span className="absolute top-0.5 left-0.5 size-3 rounded-full bg-muted" />
              </span>
              Demo Mode
            </label>
            <AlertBell />
          </header>
          <main className="min-h-0 flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>
      <Toasts />
    </AlertsProvider>
  )
}
