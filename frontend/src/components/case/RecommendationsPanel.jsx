import { ListChecks } from 'lucide-react'

const GROUPS = [
  { key: 'urgent', label: 'Urgent', dot: 'bg-red-500', ring: 'border-red-500/40 bg-red-500/5' },
  { key: 'high', label: 'High', dot: 'bg-orange-400', ring: 'border-orange-400/30 bg-orange-400/5' },
  { key: 'normal', label: 'Normal', dot: 'bg-slate-400', ring: 'border-line bg-panel-2/40' },
]

export default function RecommendationsPanel({ items }) {
  return (
    <section className="rounded-lg border border-line bg-panel">
      <h2 className="flex items-center gap-2 border-b border-line px-4 py-2.5 text-sm font-semibold">
        <ListChecks className="size-4 text-accent" /> Recommended actions
      </h2>
      {!items.length ? (
        <p className="p-4 text-sm text-muted">No recommendations for this case.</p>
      ) : (
        <div className="grid gap-4 p-4 md:grid-cols-3">
          {GROUPS.map((g) => {
            const list = items.filter((r) => r.priority === g.key)
            return (
              <div key={g.key}>
                <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide text-muted uppercase">
                  <span className={`size-2 rounded-full ${g.dot}`} /> {g.label} ({list.length})
                </h3>
                <ul className="space-y-2">
                  {list.map((r) => (
                    <li key={r.action} className={`rounded-md border p-3 ${g.ring}`}>
                      <p className="text-sm font-semibold">{r.action}</p>
                      <p className="mt-1 text-xs text-muted">{r.detail}</p>
                    </li>
                  ))}
                  {!list.length && <li className="text-xs text-muted">None</li>}
                </ul>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
