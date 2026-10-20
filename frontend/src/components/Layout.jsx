import { Bell, FilePlus2, LayoutDashboard, Radar, Share2 } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { health } from '../lib/api'
import { useFetch } from '../hooks/useFetch'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/complaint/new', label: 'New Complaint', icon: FilePlus2 },
  { to: '/network', label: 'Networks', icon: Share2 },
]

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

export default function Layout() {
  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-panel">
        <div className="flex items-center gap-2 px-5 py-4 text-lg font-bold tracking-tight">
          <Radar className="size-5 text-accent" /> ChainTrace
        </div>
        <nav className="flex flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
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
            </NavLink>
          ))}
        </nav>
        <p className="mt-auto px-5 py-4 text-[11px] leading-snug text-muted">
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
          {/* Alerts bell: wired in B6 */}
          <button className="relative text-muted hover:text-ink" title="Alerts arrive in B6">
            <Bell className="size-5" />
          </button>
        </header>
        <main className="min-h-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
