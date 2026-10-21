import { ChevronLeft, ChevronRight, ExternalLink, FileText, Phone, Search, UserCog } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { R } from '../../lib/routes'

const KEY = 'gateway.sidebar'
const row =
  'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-ink/90 transition-colors hover:bg-white/10 hover:text-white'

// The landing page's side panel: always on screen, can be collapsed to a slim rail. Holds the complaint tracker and
// the other doors. Whether it is collapsed is remembered.
export default function GatewaySidebar() {
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(KEY) : null
    return saved ? saved === 'collapsed' : typeof window !== 'undefined' && window.innerWidth < 768
  })
  const [id, setId] = useState('')

  const toggle = () =>
    setCollapsed((c) => {
      localStorage.setItem(KEY, c ? 'expanded' : 'collapsed')
      return !c
    })

  const track = (e) => {
    e.preventDefault()
    navigate(id.trim() ? `${R.track}?id=${encodeURIComponent(id.trim())}` : R.track)
  }

  return (
    <aside
      aria-label="Portal menu"
      data-collapsed={collapsed}
      className={`relative z-10 flex shrink-0 flex-col gap-2 border-r border-white/10 bg-panel/60 p-3 backdrop-blur-md transition-[width] duration-300 ${
        collapsed ? 'w-16' : 'w-72'
      }`}
    >
      <button
        type="button"
        onClick={toggle}
        aria-expanded={!collapsed}
        aria-label={collapsed ? 'Expand menu' : 'Collapse menu'}
        title={collapsed ? 'Expand menu' : 'Collapse menu'}
        className="ml-auto flex size-8 items-center justify-center rounded-md border border-white/10 text-muted hover:border-accent/60 hover:text-white"
      >
        {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
      </button>

      {collapsed ? (
        <Link to={R.track} aria-label="Track a complaint" title="Track a complaint" className={`${row} justify-center`}>
          <Search className="size-5 text-accent" />
        </Link>
      ) : (
        <form onSubmit={track} className="space-y-2 rounded-lg border border-white/10 bg-black/20 p-3" aria-label="Track a complaint">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Search className="size-4 text-accent" /> Track a complaint
          </p>
          <label className="block text-xs text-muted" htmlFor="gw-track-id">
            Complaint ID
          </label>
          <input
            id="gw-track-id"
            value={id}
            onChange={(e) => setId(e.target.value)}
            placeholder="NCRP-2026-1234"
            autoComplete="off"
            className="w-full rounded-md border border-white/15 bg-black/30 px-3 py-2 font-mono text-sm placeholder:text-muted/60 focus:border-accent focus:outline-none"
          />
          <button type="submit" className="w-full rounded-md bg-accent px-3 py-2 text-sm font-semibold text-bg hover:bg-accent/90">
            Track
          </button>
        </form>
      )}

      <nav aria-label="Other services" className="flex flex-col gap-1 pt-1">
        <Link to={R.file} aria-label="File a complaint" title="File a complaint" className={`${row} ${collapsed ? 'justify-center' : ''}`}>
          <FileText className="size-5 text-accent" />
          {!collapsed && <span>File a complaint</span>}
        </Link>
        <a
          href={R.officer}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Officer console"
          title="Officer console (opens in a new tab)"
          className={`${row} ${collapsed ? 'justify-center' : ''}`}
        >
          <UserCog className="size-5 text-accent" />
          {!collapsed && (
            <>
              <span className="flex-1">Officer console</span>
              <ExternalLink className="size-3.5 text-muted" />
            </>
          )}
        </a>
      </nav>

      {!collapsed && (
        <div className="mt-auto space-y-2 rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-muted">
          <p className="flex items-center gap-2 font-semibold text-ink">
            <Phone className="size-4 text-emerald-400" /> Lost money just now?
          </p>
          <p>Call the National Cyber Crime Helpline <span className="font-semibold text-ink">1930</span> straight away, then file here.</p>
        </div>
      )}
    </aside>
  )
}
