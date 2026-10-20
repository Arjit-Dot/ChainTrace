// Formatters. Contract timestamps are Unix epoch SECONDS; amounts are token-unit floats.

const numberFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

export const formatAmount = (n) => (n == null ? '—' : numberFmt.format(n))

export const formatUSDT = (n, token = 'USDT') => (n == null ? '—' : `${formatAmount(n)} ${token}`)

// "investment_scam" -> "Investment scam"
export const humanize = (s) => (!s ? '—' : (s.charAt(0).toUpperCase() + s.slice(1)).replaceAll('_', ' '))

export const formatPct = (x) => (x == null ? '—' : `${Math.round(x * 100)}%`)

export const shortAddr = (addr, n = 6) =>
  !addr ? '—' : addr.length <= n * 2 + 1 ? addr : `${addr.slice(0, n)}…${addr.slice(-4)}`

export const formatTime = (sec) =>
  sec == null
    ? '—'
    : new Date(sec * 1000).toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        dateStyle: 'medium',
        timeStyle: 'short',
      }) + ' IST'

export const formatDuration = (sec) => {
  if (sec == null) return '—'
  if (sec < 60) return `${Math.round(sec)} s`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m} min ${Math.round(sec % 60)} s`
  return `${Math.floor(m / 60)} h ${m % 60} min`
}

export const timeAgo = (sec) => {
  if (sec == null) return '—'
  const diff = Math.max(0, Date.now() / 1000 - sec)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  return `${Math.floor(diff / 86400)} d ago`
}
