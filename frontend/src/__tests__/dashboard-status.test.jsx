import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AlertsProvider } from '../hooks/useAlerts'
import Dashboard from '../pages/officer/Dashboard'
import { installBackend } from './setup'

const caseRow = (id, open) => ({
  case_id: id, complaint_id: `NCRP-${id}`, wallet: 'TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo', amount_lost: 100, fraud_type: 'investment', state: 'Kerala',
  risk: null, urgency: null, urgency_reasons: [], status: 'attributed', vasp: null, network_id: null, reported_at: 1, open,
})
const stats = { total_cases: 2, open_cases: 1, closed_cases: 1, total_amount_lost: 200, total_amount_traced: 0, vasp_identified_pct: 0, avg_time_to_attribution_sec: 0,
  idle_funds_flagged: 0, by_fraud_type: [], top_vasps: [], by_state: [] }

describe('the dashboard shows whether a case is open or closed', () => {
  it('marks each case and counts them', async () => {
    installBackend({ '/api/cases': [caseRow('C-1', true), caseRow('C-2', false)], '/api/dashboard': stats })
    render(<MemoryRouter><AlertsProvider><Dashboard /></AlertsProvider></MemoryRouter>)
    const flags = await screen.findAllByTestId('case-open')
    expect(flags.map((f) => f.textContent)).toEqual(['Open', 'Closed'])
    expect(screen.getByText('1 open · 1 closed')).toBeInTheDocument()
    expect(within(screen.getByRole('table')).getByText('Open / closed')).toBeInTheDocument()
  })
})
