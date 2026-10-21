// The only place the frontend talks HTTP. In dev, /api is proxied to :8000 (vite.config.js).
const BASE = import.meta.env.VITE_API_BASE ?? ''

// FastAPI sends a string for most errors and a list of {loc, msg} for a form that failed validation.
const FIELDS = {
  reporter_name: 'Your name', reporter_mobile: 'Mobile number', wallet: 'Wallet', amount: 'Amount', description: 'Description',
  scammer_phone: "Scammer's phone", paid_to_upi: 'UPI ID', paid_to_bank_account: 'Bank account number', paid_to_ifsc: 'IFSC code',
  scam_website: 'Website', scam_app: 'App', scammer_handle: 'Chat handle', value: 'Value',
}
export function describe(detail) {
  if (!Array.isArray(detail)) return detail
  return detail
    .map((d) => {
      const field = d.loc?.[d.loc.length - 1]
      return `${FIELDS[field] ?? field}: ${d.msg}`
    })
    .join('. ')
}

async function send(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, options)
  if (!res.ok) {
    let detail
    try {
      detail = (await res.json()).detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(describe(detail) || `${res.status} ${res.statusText}`)
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

// Complaints: the citizen side (file, track by ID) and the officer inbox
export const fileComplaint = (body) => post('/complaints', body)
export const getComplaintStatus = (id) => request(`/complaints/${enc(id)}/status`)
export const listComplaints = (stage) => request(`/officer/complaints${stage ? `?stage=${enc(stage)}` : ''}`)
export const getComplaint = (id) => request(`/officer/complaints/${enc(id)}`)
export const reviewComplaint = (id) => post(`/officer/complaints/${enc(id)}/review`)
export const traceComplaint = (id) => post(`/officer/complaints/${enc(id)}/trace`)

// Investigation: the identifier ledger and the leads for a case (officers only)
export const getIdentifiers = (caseId) => request(`/officer/cases/${enc(caseId)}/identifiers`)
export const addIdentifier = (caseId, body) => post(`/officer/cases/${enc(caseId)}/identifiers`, body)
export const getLeads = (caseId) => request(`/officer/cases/${enc(caseId)}/leads`)
export const getRequests = (caseId) => request(`/officer/cases/${enc(caseId)}/requests`)
export const createRequest = (caseId, body) => post(`/officer/cases/${enc(caseId)}/requests`, body)
export const approveRequest = (id) => post(`/officer/requests/${enc(id)}/approve`)
export const sendRequest = (id) => post(`/officer/requests/${enc(id)}/send`)
export const simulateRequest = (id) => post(`/officer/requests/${enc(id)}/simulate`)
export const closeRequest = (id) => post(`/officer/requests/${enc(id)}/close`)
export const getReply = (id) => request(`/officer/requests/${enc(id)}/reply`)
export const getOutcomes = (caseId) => request(`/officer/cases/${enc(caseId)}/outcomes`)
export const getMules = (caseId) => request(`/officer/cases/${enc(caseId)}/mules`)

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
// Next scripted (SIMULATED) alert for a case; the backend defaults to the hero case C-001.
export const simulateAlert = (caseId) => post(`/alerts/simulate${caseId ? `?case_id=${enc(caseId)}` : ''}`)

// Mock integrations (simulated NCRP / SAHYOG)
export const ncrpSubmit = (complaint) => post('/integrations/ncrp/complaints', complaint)
export const sahyogSend = (notice) => post('/integrations/sahyog/notice', notice)
