import { NODE_COLORS, NODE_LABELS } from '../lib/colors'

export default function Legend({ types = Object.keys(NODE_COLORS), className = '' }) {
  return (
    <ul className={`flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted ${className}`}>
      {types.map((t) => (
        <li key={t} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full ring-1 ring-black/40" style={{ background: NODE_COLORS[t] }} />
          {NODE_LABELS[t]}
        </li>
      ))}
    </ul>
  )
}
