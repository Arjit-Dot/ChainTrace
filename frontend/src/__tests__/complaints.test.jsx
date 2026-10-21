import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppRoutes } from '../App'
import { describe as describeDetail } from '../lib/api'
import { R } from '../lib/routes'
import { fail, installBackend } from './setup'

const at = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )

const complaint = (over = {}) => ({
  complaint_id: 'NCRP-2026-104317', wallet: 'TDongf8XirZvCUFazHwM2FG7cukpnF9h9D', chain: 'tron', amount: 5000, currency: 'USDT',
  tx_hash: null, fraud_type: 'investment', state: 'Karnataka', description: 'Paid a fake app', reporter_name: 'Asha Verma',
  reporter_mobile: '9876543210', stage: 'received', case_id: null, created_at: 1792540000, updated_at: 1792540000,
  history: [{ at: 1792540000, stage: 'received', note: 'Complaint registered (Citizen portal)' }], ...over,
})

describe('filing a complaint (citizen)', () => {
  it('asks for contact details and the wallet, but never for a complaint ID', () => {
    installBackend()
    at(R.file)
    expect(screen.getByLabelText(/your name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/mobile number/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/wallet you sent the money to/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/complaint id/i)).toBeNull()
  })

  it('keeps Submit disabled until name, a 10 digit mobile and a wallet are given', async () => {
    installBackend()
    const user = userEvent.setup()
    at(R.file)
    const submit = screen.getByRole('button', { name: /submit complaint/i })
    expect(submit).toBeDisabled()
    await user.type(screen.getByLabelText(/your name/i), 'Asha')
    await user.type(screen.getByLabelText(/mobile number/i), '98765')
    await user.type(screen.getByLabelText(/wallet you sent/i), 'TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo')
    expect(submit).toBeDisabled()
    expect(screen.getByText(/enter a 10 digit mobile number/i)).toBeInTheDocument()
    await user.type(screen.getByLabelText(/mobile number/i), '43210')
    expect(submit).toBeEnabled()
  })

  it('files the complaint without tracing and shows the ID the server issued', async () => {
    const { calls } = installBackend({ 'POST /api/complaints': { complaint_id: 'NCRP-2026-482913', stage: 'received', message: 'ok' } })
    const user = userEvent.setup()
    at(R.file)
    await user.click(screen.getByRole('button', { name: /fill demo example/i }))
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))
    expect(await screen.findByTestId('complaint-id')).toHaveTextContent('NCRP-2026-482913')
    const post = calls.find((c) => c.method === 'POST')
    expect(post.path).toBe('/api/complaints')
    expect(post.body).toMatchObject({ reporter_name: 'Asha Verma', reporter_mobile: '9876543210', wallet: 'TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo', chain: 'tron', amount: 12000 })
    expect(post.body).not.toHaveProperty('complaint_id')
    expect(calls.some((c) => c.path === '/api/trace')).toBe(false)                       // nothing is traced from the citizen side
  })

  it('shows the server message when the complaint is refused', async () => {
    installBackend({ 'POST /api/complaints': fail(422, [{ loc: ['body', 'reporter_mobile'], msg: 'String should match pattern' }]) })
    const user = userEvent.setup()
    at(R.file)
    await user.click(screen.getByRole('button', { name: /fill demo example/i }))
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Mobile number: String should match pattern/)
    expect(screen.getByRole('button', { name: /submit complaint/i })).toBeEnabled()
  })

  it('turns a validation error list into one readable sentence', () => {
    expect(describeDetail([{ loc: ['body', 'amount'], msg: 'must be >= 0' }, { loc: ['body', 'wallet'], msg: 'too short' }])).toBe(
      'Amount: must be >= 0. Wallet: too short',
    )
    expect(describeDetail('plain text')).toBe('plain text')
  })
})

describe('officer inbox', () => {
  const list = [
    complaint(),
    complaint({ complaint_id: 'NCRP-2026-258846', reporter_name: 'Rohit Nair', stage: 'under_review' }),
    complaint({ complaint_id: 'NCRP-2026-000001', reporter_name: 'Old Case', stage: 'investigating', case_id: 'C-001' }),
    complaint({ complaint_id: 'NCRP-2026-000003', reporter_name: 'Sent One', stage: 'action_initiated', case_id: 'C-003' }),
  ]

  it('opens on the new complaints, with counts per tab', async () => {
    installBackend({ '/api/officer/complaints': list })
    at(R.officerInbox)
    expect(await screen.findByText('NCRP-2026-104317')).toBeInTheDocument()
    expect(screen.queryByText('NCRP-2026-258846')).toBeNull()
    const tabs = within(screen.getByRole('tablist'))
    expect(tabs.getByRole('tab', { name: /new\s*1/i })).toHaveAttribute('aria-selected', 'true')
    expect(tabs.getByRole('tab', { name: /in progress\s*2/i })).toBeInTheDocument()
    expect(tabs.getByRole('tab', { name: /action taken\s*1/i })).toBeInTheDocument()
    expect(tabs.getByRole('tab', { name: /all\s*4/i })).toBeInTheDocument()
  })

  it('switches tabs', async () => {
    installBackend({ '/api/officer/complaints': list })
    const user = userEvent.setup()
    at(R.officerInbox)
    await screen.findByText('NCRP-2026-104317')
    await user.click(screen.getByRole('tab', { name: /in progress/i }))
    expect(screen.getByText('NCRP-2026-258846')).toBeInTheDocument()
    expect(screen.queryByText('NCRP-2026-104317')).toBeNull()
    await user.click(screen.getByRole('tab', { name: /all/i }))
    expect(screen.getAllByRole('row')).toHaveLength(5)                                    // header + 4
  })

  it('links each complaint to its page and shows who and how much', async () => {
    installBackend({ '/api/officer/complaints': list })
    at(R.officerInbox)
    const link = await screen.findByRole('link', { name: 'NCRP-2026-104317' })
    expect(link).toHaveAttribute('href', R.officerComplaint('NCRP-2026-104317'))
    const row = link.closest('tr')
    expect(row).toHaveTextContent('Asha Verma')
    expect(row).toHaveTextContent('Karnataka')
    expect(row).toHaveTextContent(/Received/)
  })

  it('says so when nothing is waiting', async () => {
    installBackend({ '/api/officer/complaints': [] })
    at(R.officerInbox)
    expect(await screen.findByText(/no new complaints/i)).toBeInTheDocument()
  })

  it('shows a new complaint the moment its alert arrives', async () => {
    let items = []
    const { emitAlert } = installBackend({ '/api/officer/complaints': () => items })
    at(R.officerInbox)
    expect(await screen.findByText(/no new complaints/i)).toBeInTheDocument()
    items = [complaint()]
    act(() => emitAlert({ id: 'L-1', type: 'COMPLAINT_RECEIVED', severity: 'info', case_id: null, complaint_id: 'NCRP-2026-104317', message: 'New complaint', timestamp: 1 }))
    expect(await screen.findByText('NCRP-2026-104317')).toBeInTheDocument()
  })

  it('shows a count of waiting complaints on the Inbox link', async () => {
    installBackend({ '/api/officer/complaints': [complaint(), complaint({ complaint_id: 'NCRP-2026-2' })] })
    at(R.officerInbox)
    expect(await screen.findByLabelText('2 new complaints')).toBeInTheDocument()
  })

  it('reports a failed load with a retry', async () => {
    installBackend({ '/api/officer/complaints': fail(500, 'database error') })
    at(R.officerInbox)
    expect(await screen.findByText(/database error/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

describe('officer complaint page', () => {
  const route = (cid = 'NCRP-2026-104317') => R.officerComplaint(cid)

  it('shows everything the citizen reported, and the officers-only history', async () => {
    installBackend({ '/api/officer/complaints/NCRP-2026-104317': complaint() })
    at(route())
    expect(await screen.findByRole('heading', { name: 'NCRP-2026-104317' })).toBeInTheDocument()
    for (const text of ['Asha Verma', '9876543210', 'TDongf8XirZvCUFazHwM2FG7cukpnF9h9D', '5,000', 'Karnataka', 'Paid a fake app']) {
      expect(screen.getAllByText(new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))).length).toBeGreaterThan(0)
    }
    expect(screen.getByRole('complementary', { name: /history/i })).toHaveTextContent(/Complaint registered/)
    expect(within(screen.getByRole('main')).getByRole('link', { name: /inbox/i })).toHaveAttribute('href', R.officerInbox)
  })

  it('offers review and trace on a new complaint', async () => {
    installBackend({ '/api/officer/complaints/NCRP-2026-104317': complaint() })
    at(route())
    expect(await screen.findByRole('button', { name: /start review/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /trigger trace/i })).toBeInTheDocument()
  })

  it('moves a complaint under review', async () => {
    const { calls } = installBackend({
      '/api/officer/complaints/NCRP-2026-104317': complaint(),
      'POST /api/officer/complaints/NCRP-2026-104317/review': complaint({ stage: 'under_review', history: [{ at: 1, stage: 'received', note: 'Complaint registered' }, { at: 2, stage: 'under_review', note: 'Opened for review by an officer' }] }),
    })
    const user = userEvent.setup()
    at(route())
    await user.click(await screen.findByRole('button', { name: /start review/i }))
    expect(await screen.findByText(/opened for review by an officer/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /start review/i })).toBeNull()               // review is done
    expect(screen.getByRole('button', { name: /trigger trace/i })).toBeInTheDocument()       // but tracing is still open
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
  })

  it('triggers the trace and opens the case it created', async () => {
    const { calls } = installBackend({
      '/api/officer/complaints/NCRP-2026-104317': complaint(),
      'POST /api/officer/complaints/NCRP-2026-104317/trace': complaint({ stage: 'investigating', case_id: 'C-009' }),
      '/api/cases/C-009': fail(404, 'not needed here'),            // only the navigation is under test
    })
    const user = userEvent.setup()
    at(route())
    await user.click(await screen.findByRole('button', { name: /trigger trace/i }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/cases/C-009')).toBe(true))      // landed on the case page
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/api/officer/complaints/NCRP-2026-104317/trace'])
  })

  it('shows the server message when the trace is refused', async () => {
    installBackend({
      '/api/officer/complaints/NCRP-2026-104317': complaint(),
      'POST /api/officer/complaints/NCRP-2026-104317/trace': fail(409, 'A trace has already been run for this complaint.'),
    })
    const user = userEvent.setup()
    at(route())
    await user.click(await screen.findByRole('button', { name: /trigger trace/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already been run/i)
    expect(screen.getByRole('button', { name: /trigger trace/i })).toBeEnabled()
  })

  it('links to the case, and offers no actions, once the trace has run', async () => {
    installBackend({ '/api/officer/complaints/NCRP-2026-000001': complaint({ complaint_id: 'NCRP-2026-000001', stage: 'investigating', case_id: 'C-001' }) })
    at(route('NCRP-2026-000001'))
    const open = await screen.findByRole('link', { name: /open case c-001/i })
    expect(open).toHaveAttribute('href', R.officerCase('C-001'))
    expect(screen.queryByRole('button', { name: /trigger trace/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /start review/i })).toBeNull()
  })

  it('reports an unknown complaint', async () => {
    installBackend({ '/api/officer/complaints/NCRP-NOPE': fail(404, 'Complaint not found') })
    at(route('NCRP-NOPE'))
    expect(await screen.findByText(/complaint not found/i)).toBeInTheDocument()
  })
})

describe('the officer navigation', () => {
  it('leads with the inbox', async () => {
    installBackend()
    at(R.officerInbox)
    const nav = screen.getByRole('navigation')
    const links = within(nav).getAllByRole('link').map((l) => l.textContent.replace(/\d+$/, '').trim())
    expect(links.slice(0, 3)).toEqual(['Inbox', 'Dashboard', 'Networks'])
  })
})
