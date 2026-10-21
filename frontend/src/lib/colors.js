// Single source of node-type colors: used by the trace graph, legend and network view.
export const NODE_COLORS = {
  victim: '#9ca3af',
  scam_wallet: '#ef4444',
  intermediary: '#f97316',
  bridge: '#3b82f6',
  mixer: '#a855f7',
  exchange: '#22c55e',
  dex: '#14b8a6',
  bank_account: '#eab308',
  unknown: '#f8fafc',
}

export const NODE_LABELS = {
  victim: 'Victim',
  scam_wallet: 'Scam wallet',
  intermediary: 'Intermediary',
  bridge: 'Bridge',
  mixer: 'Mixer',
  exchange: 'Exchange',
  dex: 'DEX (swap)',
  bank_account: 'Bank account',
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

// Investigation: the institutions that hold the identity behind an identifier, and the requests we can send them.
export const CHOKE_POINTS = {
  exchange: 'Crypto exchange', bank: 'Bank', payment_app: 'UPI / payment app', p2p_desk: 'P2P or OTC desk', telecom: 'Telecom operator',
  messaging_platform: 'Messaging or social platform', domain_host: 'Domain and hosting', app_store: 'App store', issuer: 'Token issuer',
}
export const REQUESTS = {
  kyc_request: 'KYC request', account_details_request: 'Account details', freeze_request: 'Freeze request', subscriber_request: 'Subscriber details',
  platform_data_request: 'Platform data', registrant_request: 'Registrant details', developer_request: 'Developer details',
  takedown_request: 'Takedown', preservation_notice: 'Preservation notice', issuer_hold: 'Issuer hold',
}
// Where the money ended up, and how urgent each outcome is.
export const ENDPOINT_KINDS = {
  vasp: 'Exchange (VASP)', dex: 'DEX swap', bank_account: 'Bank account', mixer: 'Mixer', bridge: 'Bridge', idle_wallet: 'Funds still in a wallet', dead_end: 'Dead end',
}
export const OUTCOME_STATUS = {
  action_needed: { label: 'Action needed', classes: 'bg-red-500/15 text-red-300 ring-red-500/40' },
  in_progress: { label: 'In progress', classes: 'bg-violet-500/15 text-violet-300 ring-violet-500/40' },
  info: { label: 'For information', classes: 'bg-sky-500/15 text-sky-300 ring-sky-500/40' },
}
export const ONWARD = { vasp: 'an exchange', dex: 'a DEX', mixer: 'a mixer', bridge: 'a bridge', bank_account: 'a bank account', wallet: 'another wallet' }

export const IDENTIFIER_KINDS = {
  wallet: 'Wallet', bank_account: 'Bank account', upi_id: 'UPI ID', phone: 'Phone', email: 'Email', device: 'Device', ip_address: 'IP address',
  social_handle: 'Social handle', domain: 'Domain', app: 'App',
}
export const ROLES = {
  reported: 'Reported wallet', mule_suspect: 'Suspected mule', vasp_deposit: 'Exchange deposit', lure: 'How they were reached', payment: 'Where they paid', other: 'Other',
}
export const PRIORITY_CLASSES = {
  urgent: 'bg-red-500/15 text-red-300 ring-red-500/40', high: 'bg-amber-500/15 text-amber-300 ring-amber-500/40', normal: 'bg-sky-500/15 text-sky-300 ring-sky-500/40',
}

// A complaint's stage (the citizen sees the same five, in plainer words).
export const STAGES = {
  received: { label: 'Received', classes: 'bg-sky-500/15 text-sky-300 ring-sky-500/40' },
  under_review: { label: 'Under review', classes: 'bg-amber-500/15 text-amber-300 ring-amber-500/40' },
  investigating: { label: 'Investigating', classes: 'bg-violet-500/15 text-violet-300 ring-violet-500/40' },
  action_initiated: { label: 'Action initiated', classes: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40' },
  closed: { label: 'Closed', classes: 'bg-slate-500/15 text-slate-300 ring-slate-500/40' },
}

// The five stages in order, as the citizen's progress bar shows them.
export const STAGE_ORDER = ['received', 'under_review', 'investigating', 'action_initiated', 'closed']

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
