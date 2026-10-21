import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom has no canvas or matchMedia: answer "no canvas" and "no reduced-motion preference".
HTMLCanvasElement.prototype.getContext = () => null
if (!window.matchMedia) window.matchMedia = (q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
beforeEach(() => localStorage.clear())

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// The pages call the API through fetch and the alert stream through EventSource; the tests answer both locally.
// routes: "/api/x" for a GET, "POST /api/x" for a POST; a value is the JSON to return, a function gets (init, url).
// fail(409, "text") makes a route answer with an error. Returns the recorded calls and a way to push a live alert.
export const fail = (status, detail) => ({ __status: status, detail })

export function installBackend(routes = {}) {
  const defaults = {
    '/api/health': { status: 'ok', contract_version: '1.2.0', engine_mode: 'fixture' },
    '/api/alerts': [],
    '/api/cases': [],
    '/api/officer/complaints': [],
    '/api/dashboard': {
      total_cases: 0, total_amount_lost: 0, total_amount_traced: 0, vasp_identified_pct: 0, avg_time_to_attribution_sec: 0,
      idle_funds_flagged: 0, by_fraud_type: [], top_vasps: [], by_state: [],
    },
    '/api/networks': [],
  }
  const calls = []
  const listeners = []
  globalThis.fetch = vi.fn(async (url, init = {}) => {
    const path = String(url).split('?')[0]
    const method = init.method ?? 'GET'
    calls.push({ method, path, url: String(url), body: init.body ? JSON.parse(init.body) : undefined })
    const handler = routes[`${method} ${path}`] ?? (method === 'GET' ? routes[path] ?? defaults[path] : undefined)
    const body = typeof handler === 'function' ? handler(init, String(url)) : handler
    if (body === undefined) return { ok: false, status: 404, statusText: 'Not Found', json: async () => ({ detail: 'not found' }) }
    if (body?.__status) return { ok: false, status: body.__status, statusText: 'Error', json: async () => ({ detail: body.detail }) }
    return { ok: true, status: 200, json: async () => body }
  })
  globalThis.EventSource = vi.fn(function EventSource() {
    this.addEventListener = (type, fn) => type === 'alert' && listeners.push(fn)
    this.close = () => {}
  })
  const emitAlert = (alert) => listeners.forEach((fn) => fn({ data: JSON.stringify(alert) }))
  return { calls, emitAlert }
}
