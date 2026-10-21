import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// The pages call the API through fetch and the alert stream through EventSource; the tests answer both locally.
export function installBackend(routes = {}) {
  const defaults = {
    '/api/health': { status: 'ok', contract_version: '1.2.0', engine_mode: 'fixture' },
    '/api/alerts': [],
    '/api/cases': [],
    '/api/dashboard': {
      total_cases: 0, total_amount_lost: 0, total_amount_traced: 0, vasp_identified_pct: 0, avg_time_to_attribution_sec: 0,
      idle_funds_flagged: 0, by_fraud_type: [], top_vasps: [], by_state: [],
    },
    '/api/networks': [],
  }
  const table = { ...defaults, ...routes }
  globalThis.fetch = vi.fn(async (url) => {
    const path = String(url).split('?')[0]
    const body = table[path]
    return body === undefined
      ? { ok: false, status: 404, statusText: 'Not Found', json: async () => ({ detail: 'not found' }) }
      : { ok: true, status: 200, json: async () => body }
  })
  globalThis.EventSource = vi.fn(function EventSource() {
    this.addEventListener = () => {}
    this.close = () => {}
  })
}
