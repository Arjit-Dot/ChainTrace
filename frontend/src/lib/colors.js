// Single source of node-type colors: used by the trace graph, legend and network view.
export const NODE_COLORS = {
  victim: '#9ca3af',
  scam_wallet: '#ef4444',
  intermediary: '#f97316',
  bridge: '#3b82f6',
  mixer: '#a855f7',
  exchange: '#22c55e',
  unknown: '#f8fafc',
}

export const NODE_LABELS = {
  victim: 'Victim',
  scam_wallet: 'Scam wallet',
  intermediary: 'Intermediary',
  bridge: 'Bridge',
  mixer: 'Mixer',
  exchange: 'Exchange',
  unknown: 'Unknown',
}

export const nodeColor = (type) => NODE_COLORS[type] ?? NODE_COLORS.unknown

// Tailwind classes for risk levels (badge background / text / ring).
export const RISK_CLASSES = {
  Low: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40',
  Medium: 'bg-amber-500/15 text-amber-300 ring-amber-500/40',
  High: 'bg-orange-500/15 text-orange-300 ring-orange-500/40',
  Critical: 'bg-red-500/15 text-red-300 ring-red-500/40',
}

// Case urgency: what an officer should do about the case, and how soon.
export const URGENCY = {
  act_now: { label: 'Act now', classes: 'bg-red-500/15 text-red-300 ring-red-500/40' },
  act_soon: { label: 'Act soon', classes: 'bg-amber-500/15 text-amber-300 ring-amber-500/40' },
  preserve: { label: 'Preserve', classes: 'bg-sky-500/15 text-sky-300 ring-sky-500/40' },
}

export const SOURCE_CLASSES = {
  live: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40',
  cached: 'bg-sky-500/15 text-sky-300 ring-sky-500/40',
  simulated: 'bg-fuchsia-500/15 text-fuchsia-300 ring-fuchsia-500/40',
}

// Dashboard charts: one hue (sequential blue, dark step) for single-series magnitude bars, text in ink tokens.
// Validated with the dataviz palette checker against the panel surface #111827 (all checks pass).
export const CHART = {
  bar: '#3987e5',
  barHover: '#5598e7',
  ink: '#e5e9f0',
  muted: '#8b95a7',
  line: '#243049',
}
