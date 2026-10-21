// The only place the frontend talks HTTP. In dev, /api is proxied to :8000 (vite.config.js).
const BASE = import.meta.env.VITE_API_BASE ?? ''

async function send(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, options)
  if (!res.ok) {
    let detail
    try {
      detail = (await res.json()).detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res
}

const request = async (path, options) => (await send(path, options)).json()

const post = (path, body) =>
  request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

const enc = encodeURIComponent

export const health = () => request('/health')

// Core (engine)
export const trace = (req) => post('/trace', req)
export const getRisk = (address) => request(`/wallets/${enc(address)}/risk`)

// Cases
export const getCases = () => request('/cases')
export const getCase = (id) => request(`/cases/${enc(id)}`)
export const getFreezeNotice = (id) => request(`/cases/${enc(id)}/freeze-notice`)
export const simulateMovement = (id) => post(`/cases/${enc(id)}/simulate-movement`)
export const reportUrl = (id) => `${BASE}/api/cases/${enc(id)}/report`
// The PDF plus the SHA-256 of the case data it was built from (also printed in the PDF footer).
export async function getReport(id) {
  const res = await send(`/cases/${enc(id)}/report`)
  return { blob: await res.blob(), sha256: res.headers.get('X-Evidence-SHA256') }
}

// Analytics
export const getDashboard = () => request('/dashboard')
export const getNetworks = () => request('/networks')

// Alerts
export const getAlerts = () => request('/alerts')
export const alertStreamUrl = () => `${BASE}/api/alerts/stream`
export const simulateAlert = () => post('/alerts/simulate')

// Mock integrations (simulated NCRP / SAHYOG)
export const ncrpSubmit = (complaint) => post('/integrations/ncrp/complaints', complaint)
export const sahyogSend = (notice) => post('/integrations/sahyog/notice', notice)
