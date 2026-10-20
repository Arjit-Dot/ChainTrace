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

export const SOURCE_CLASSES = {
  live: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40',
  cached: 'bg-sky-500/15 text-sky-300 ring-sky-500/40',
  simulated: 'bg-fuchsia-500/15 text-fuchsia-300 ring-fuchsia-500/40',
}
