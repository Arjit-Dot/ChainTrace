import { Link, NavLink, Outlet } from 'react-router-dom'
import { ExternalLink, ShieldCheck } from 'lucide-react'
import { R } from '../../lib/routes'

const NAV = [
  { to: R.gateway, label: 'Home', end: true },
  { to: R.file, label: 'File a complaint' },
  { to: R.track, label: 'Track a complaint' },
]

export function TricolorStrip() {
  return (
    <div className="flex h-1.5 w-full" aria-hidden="true">
      <div className="flex-1 bg-orange-500" />
      <div className="flex-1 bg-white" />
      <div className="flex-1 bg-green-600" />
    </div>
  )
}

export function DemoNotice() {
  return (
    <p className="bg-amber-400/10 px-4 py-1.5 text-center text-xs text-amber-200" role="note">
      Demonstration build. This is not an official government website, and all names, wallets and cases are fictional.
    </p>
  )
}

// The public side. No officer navigation, no alert stream: a citizen only files and tracks a complaint.
export default function CitizenLayout() {
  return (
    <div className="flex min-h-full flex-col" data-area="citizen">
      <TricolorStrip />
      <DemoNotice />
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <Link to={R.gateway} className="flex items-center gap-2.5">
            <ShieldCheck className="size-6 text-accent" />
            <span>
              <span className="block text-base leading-tight font-bold tracking-tight">Crypto Fraud Reporting</span>
              <span className="block text-xs text-muted">Report a loss and follow its progress</span>
            </span>
          </Link>
          <nav className="flex flex-wrap items-center gap-1" aria-label="Citizen navigation">
            {NAV.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm ${isActive ? 'bg-accent/15 text-accent' : 'text-muted hover:text-ink'}`
                }
              >
                {label}
              </NavLink>
            ))}
            <a
              href={R.officer}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:border-accent/50 hover:text-ink"
            >
              Officer console <ExternalLink className="size-3.5" />
            </a>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-line px-6 py-4 text-center text-xs text-muted">
        If you have just lost money, also call the National Cyber Crime Helpline 1930 as soon as possible.
      </footer>
    </div>
  )
}
