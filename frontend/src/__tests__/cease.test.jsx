import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import CeasePanel from '../components/case/CeasePanel'
import { fail, installBackend } from './setup'

const item = (over = {}) => ({
  lead_id: 'L-1', choke_point: 'exchange', holder: 'Example Exchange B', kind: 'freeze_request', subject: 'TW6WFmfMNjLtRZVuXh4wvCL9s9WuKwe2Fw',
  request_id: null, status: 'not_drafted', note: null, ...over,
})
const status = (over = {}) => ({
  case_id: 'C-009', complaint_id: 'NCRP-2026-104317', stage: 'investigating', citizen_sees: 'Your complaint is being investigated.',
  report_url: '/api/cases/C-009/report', items: [item(), item({ lead_id: 'L-2', choke_point: 'messaging_platform', holder: 'Telegram', kind: 'takedown_request', subject: '@x', note: 'Send the preservation notice first: a takedown can destroy the records.' })],
  drafts_created: 0, started: false, ...over,
})
const GET = '/api/officer/cases/C-009/cease'

// A server whose state changes as the officer acts.
function live(initial = status()) {
  let current = initial
  return {
    [GET]: () => current,
    [`POST ${GET}`]: () => (current = status({
      items: current.items.map((i) => ({ ...i, request_id: `R-${i.lead_id}`, status: 'draft' })), drafts_created: current.items.filter((i) => !i.request_id).length,
    })),
    'POST /api/officer/complaints/NCRP-2026-104317/close': () => (current = status({ ...current, stage: 'closed', citizen_sees: 'Your complaint has been closed.' })),
  }
}

describe('the report and cease panel', () => {
  it('offers the evidence report and lists each freeze, hold or takedown with its status', async () => {
    installBackend(live())
    render(<CeasePanel caseId="C-009" />)
    const rows = await screen.findAllByTestId('cease-item')
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText('Freeze request')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Not drafted')).toBeInTheDocument()
    expect(within(rows[1]).getByText(/preservation notice first/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /download evidence report/i }).getAttribute('href')).toMatch(/\/api\/cases\/C-009\/report$/)
    expect(screen.getByText(/nothing is transmitted in this demo/i)).toBeInTheDocument()
  })

  it('drafts every request in one click and says how many, without approving any', async () => {
    const backend = installBackend(live())
    render(<CeasePanel caseId="C-009" />)
    await userEvent.click(await screen.findByRole('button', { name: /draft the freeze, hold and takedown/i }))
    expect(await screen.findByRole('status')).toHaveTextContent('2 requests drafted.')
    await waitFor(() => expect(screen.getAllByText('Draft')).toHaveLength(2))
    expect(backend.calls.filter((c) => c.method === 'POST')).toHaveLength(1)
    expect(screen.getByRole('button', { name: /draft the freeze, hold and takedown/i })).toBeDisabled()
  })

  it('shows the stage and the exact sentence the citizen sees', async () => {
    installBackend(live(status({ stage: 'action_initiated', citizen_sees: 'Action has been initiated with the relevant institutions.', started: true })))
    render(<CeasePanel caseId="C-009" />)
    const box = within(await screen.findByTestId('cease-complaint'))
    expect(box.getByText('Action initiated')).toBeInTheDocument()
    expect(box.getByText(/Action has started/)).toBeInTheDocument()
    expect(box.getByText(/Action has been initiated with the relevant institutions/)).toBeInTheDocument()
  })

  it('closes the complaint and then offers no second close', async () => {
    installBackend(live())
    render(<CeasePanel caseId="C-009" />)
    await userEvent.click(await screen.findByRole('button', { name: /close the complaint/i }))
    await waitFor(() => expect(screen.queryByRole('button', { name: /close the complaint/i })).toBeNull())
    expect(screen.getByText(/Your complaint has been closed/)).toBeInTheDocument()
  })

  it('does not offer to close before the trace has started the investigation', async () => {
    installBackend(live(status({ stage: 'under_review' })))
    render(<CeasePanel caseId="C-009" />)
    await screen.findByTestId('cease-complaint')
    expect(screen.queryByRole('button', { name: /close the complaint/i })).toBeNull()
  })

  it('says so when nothing can be frozen', async () => {
    installBackend(live(status({ items: [] })))
    render(<CeasePanel caseId="C-009" />)
    expect(await screen.findByText(/nothing on this case can be frozen/i)).toBeInTheDocument()
  })

  it('shows the server message when closing is refused', async () => {
    installBackend({ ...live(), 'POST /api/officer/complaints/NCRP-2026-104317/close': fail(409, 'This complaint is already closed.') })
    render(<CeasePanel caseId="C-009" />)
    await userEvent.click(await screen.findByRole('button', { name: /close the complaint/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already closed/)
  })

  it('reports a load failure', async () => {
    installBackend({ [GET]: fail(500, 'boom') })
    render(<CeasePanel caseId="C-009" />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i)
  })
})
