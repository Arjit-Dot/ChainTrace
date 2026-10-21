import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import LeadsPanel from '../components/case/LeadsPanel'
import RequestsPanel from '../components/case/RequestsPanel'
import { fail, installBackend } from './setup'

const req = (over = {}) => ({
  request_id: 'R-C-009-001', case_id: 'C-009', lead_id: 'L-1', identifier_id: 'I-1', choke_point: 'exchange', holder: 'Example Exchange B',
  kind: 'kyc_request', subject: 'TW6WFmfMNjLtRZVuXh4wvCL9s9WuKwe2Fw', status: 'draft', letter_subject: 'KYC request: Example Exchange B',
  letter_body: 'DRAFT FOR OFFICER REVIEW. Legal references are placeholders.\n\nTo: Example Exchange B', created_at: 1792540000,
  updated_at: 1792540000, reference: null, history: [], ...over,
})
const REPLY = {
  reply_id: 'P-R-C-009-001', request_id: 'R-C-009-001', case_id: 'C-009', received_at: 1792541000, summary: 'Example Exchange B supplies the account holder\'s KYC (fictional).',
  fields: [{ label: 'Account holder', value: 'Meena Rathore (demo)' }, { label: 'Registered mobile', value: '9000000503' }], new_identifier_ids: ['I-8', 'I-9', 'I-10'], fictional: true,
}
const P = '/api/officer/requests/R-C-009-001'

// A request list that changes as the officer acts, like the real server.
function live(status, extra = {}) {
  let current = status
  const routes = {
    '/api/officer/cases/C-009/requests': () => [req({ status: current, reference: ['draft', 'approved'].includes(current) ? null : 'SIM-E06CE33C' })],
    [`POST ${P}/approve`]: () => (current = 'approved', req({ status: current })),
    [`POST ${P}/send`]: () => (current = 'sent', req({ status: current, reference: 'SIM-E06CE33C' })),
    [`POST ${P}/simulate`]: () => (current = current === 'sent' ? 'acknowledged' : 'replied', req({ status: current })),
    [`POST ${P}/close`]: () => (current = 'closed', req({ status: current })),
    [`${P}/reply`]: REPLY,
    ...extra,
  }
  return routes
}

function Harness({ onBump }) {
  const [v, setV] = useState(0)
  const bump = () => {
    onBump?.()
    setV((n) => n + 1)
  }
  return <RequestsPanel caseId="C-009" version={v} onChange={bump} />
}

const setup = (status = 'draft', extra) => {
  const backend = installBackend(live(status, extra))
  render(<Harness />)
  return backend
}
const card = async () => within(await screen.findByTestId('request'))

describe('the requests panel', () => {
  it('says nothing is transmitted and every reply is fictional', async () => {
    setup()
    await card()
    expect(screen.getByText(/nothing is transmitted in this demo/i)).toBeInTheDocument()
    expect(screen.getByText(/every reply is fictional/i)).toBeInTheDocument()
  })

  it('shows a draft with its holder, subject and progress', async () => {
    setup()
    const c = await card()
    expect(c.getByText('KYC request')).toBeInTheDocument()
    expect(c.getByText(/Example Exchange B/)).toBeInTheDocument()
    expect(c.getByText('TW6WFmfMNjLtRZVuXh4wvCL9s9WuKwe2Fw')).toBeInTheDocument()
    const stages = within(c.getByRole('list', { name: /request progress/i })).getAllByRole('listitem')
    expect(stages.map((s) => s.dataset.state)).toEqual(['current', 'todo', 'todo', 'todo', 'todo', 'todo'])
  })

  it('lets an officer read the draft letter, with its placeholders', async () => {
    const user = userEvent.setup()
    setup()
    await user.click((await card()).getByRole('button', { name: /view letter/i }))
    expect(screen.getByText(/DRAFT FOR OFFICER REVIEW/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /hide letter/i }))
    expect(screen.queryByText(/DRAFT FOR OFFICER REVIEW/)).toBeNull()
  })

  it('offers only the next step: approve, then send, then the demo buttons', async () => {
    const user = userEvent.setup()
    setup()
    let c = await card()
    expect(c.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
    expect(c.queryByRole('button', { name: 'Send' })).toBeNull()                            // cannot send an unapproved letter
    await user.click(c.getByRole('button', { name: 'Approve' }))
    await waitFor(async () => expect((await card()).getByRole('button', { name: 'Send' })).toBeInTheDocument())
    c = await card()
    expect(c.queryByRole('button', { name: 'Approve' })).toBeNull()
    await user.click(c.getByRole('button', { name: 'Send' }))
    await waitFor(async () => expect((await card()).getByRole('button', { name: /simulate acknowledgement/i })).toBeInTheDocument())
    expect((await card()).getByText(/ref SIM-E06CE33C/)).toBeInTheDocument()
  })

  it('walks a request all the way to a reply and shows the fictional reply', async () => {
    const user = userEvent.setup()
    const { calls } = setup('sent')
    await user.click((await card()).getByRole('button', { name: /simulate acknowledgement/i }))
    await waitFor(async () => expect((await card()).getByRole('button', { name: /simulate reply/i })).toBeInTheDocument())
    await user.click((await card()).getByRole('button', { name: /simulate reply/i }))
    await user.click(await waitForButton(/view reply/i))
    const reply = within(await screen.findByLabelText('Reply'))
    expect(reply.getByText('FICTIONAL DEMO DATA')).toBeInTheDocument()
    expect(reply.getByText('Meena Rathore (demo)')).toBeInTheDocument()
    expect(reply.getByText(/3 new identifiers added to this case, opening new leads/i)).toBeInTheDocument()
    expect(calls.filter((c) => c.path === `${P}/simulate`)).toHaveLength(2)
  })

  it('refreshes the rest of the investigation after every step', async () => {
    const user = userEvent.setup()
    let bumps = 0
    installBackend(live('draft'))
    render(<Harness onBump={() => bumps++} />)
    await user.click((await card()).getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(bumps).toBe(1))
  })

  it('can close a request that was sent', async () => {
    const user = userEvent.setup()
    setup('sent')
    await user.click((await card()).getByRole('button', { name: 'Close' }))
    await waitFor(async () => expect((await card()).getByRole('list', { name: /request progress/i })).toBeInTheDocument())
    expect((await screen.findByTestId('request')).dataset.status).toBe('closed')
  })

  it('has no Close button on a draft', async () => {
    setup('draft')
    expect((await card()).queryByRole('button', { name: 'Close' })).toBeNull()
  })

  it('shows the server message when a step is refused', async () => {
    const user = userEvent.setup()
    setup('draft', { [`POST ${P}/approve`]: fail(409, 'This request is approved: it cannot go to approved.') })
    await user.click((await card()).getByRole('button', { name: 'Approve' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot go to approved/i)
  })

  it('has an empty state and a failure state', async () => {
    installBackend({ '/api/officer/cases/C-009/requests': [] })
    render(<RequestsPanel caseId="C-009" />)
    expect(await screen.findByText(/no requests yet/i)).toBeInTheDocument()
  })

  it('reports a failed load', async () => {
    installBackend({ '/api/officer/cases/C-009/requests': fail(500, 'store offline') })
    render(<RequestsPanel caseId="C-009" />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/store offline/)
  })
})

async function waitForButton(name) {
  return await screen.findByRole('button', { name })
}

describe('drafting from a lead', () => {
  const lead = {
    lead_id: 'L-1', case_id: 'C-009', identifier_id: 'I-1', choke_point: 'exchange', holder: 'Example Exchange B',
    what_it_identifies: 'Verified identity of the account holder', requests: ['kyc_request', 'freeze_request'], priority: 'urgent', rationale: 'Funds reached an account.',
  }
  const ident = { identifier_id: 'I-1', case_id: 'C-009', kind: 'wallet', value: 'TW6WFmfM', label: 'Example Exchange B', role: 'vasp_deposit', source: 'trace', source_ref: null, confidence: 0.76, added_at: 1 }

  it('turns a request chip into a draft and then marks it as drafted', async () => {
    let drafted = []
    const { calls } = installBackend({
      '/api/officer/cases/C-009/identifiers': [ident], '/api/officer/cases/C-009/leads': [lead], '/api/officer/cases/C-009/requests': () => drafted,
      'POST /api/officer/cases/C-009/requests': () => (drafted = [req()], req()),
    })
    const user = userEvent.setup()
    render(<LeadsPanel caseId="C-009" />)
    const lc = within(await screen.findByTestId('lead'))
    await user.click(lc.getByRole('button', { name: 'Draft: KYC request' }))
    await waitFor(() => expect(within(screen.getByTestId('lead')).queryByRole('button', { name: 'Draft: KYC request' })).toBeNull())
    expect(within(screen.getByTestId('lead')).getByText(/KYC request · Draft/)).toBeInTheDocument()
    expect(within(screen.getByTestId('lead')).getByRole('button', { name: 'Draft: Freeze request' })).toBeInTheDocument()   // the other one is still open
    expect(calls.find((c) => c.method === 'POST').body).toEqual({ lead_id: 'L-1', kind: 'kyc_request' })
  })

  it('tells the officer when the draft is refused', async () => {
    installBackend({
      '/api/officer/cases/C-009/identifiers': [ident], '/api/officer/cases/C-009/leads': [lead], '/api/officer/cases/C-009/requests': [],
      'POST /api/officer/cases/C-009/requests': fail(409, 'A request of this kind already exists for this lead.'),
    })
    const user = userEvent.setup()
    render(<LeadsPanel caseId="C-009" />)
    await user.click(await screen.findByRole('button', { name: 'Draft: KYC request' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists for this lead/)
  })

  it('refetches the leads when the investigation changes', async () => {
    const { calls } = installBackend({ '/api/officer/cases/C-009/identifiers': [ident], '/api/officer/cases/C-009/leads': [lead], '/api/officer/cases/C-009/requests': [] })
    const { rerender } = render(<LeadsPanel caseId="C-009" version={0} />)
    await screen.findByTestId('lead')
    const n = calls.filter((c) => c.path.endsWith('/leads')).length
    rerender(<LeadsPanel caseId="C-009" version={1} />)
    await waitFor(() => expect(calls.filter((c) => c.path.endsWith('/leads')).length).toBe(n + 1))
  })
})
