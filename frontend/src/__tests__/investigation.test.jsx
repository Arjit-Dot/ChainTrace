import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppRoutes } from '../App'
import Legend from '../components/case/Legend'
import LeadsPanel from '../components/case/LeadsPanel'
import { describe as describeDetail } from '../lib/api'
import { NODE_COLORS, NODE_LABELS } from '../lib/colors'
import { R } from '../lib/routes'
import { fail, installBackend } from './setup'

const at = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )

const ident = (over = {}) => ({
  identifier_id: 'I-C-009-001', case_id: 'C-009', kind: 'wallet', value: 'TJgNArE5dkoiDgHUjimdizwNaTZZwLh1Lg', label: 'Reported wallet',
  role: 'reported', source: 'complaint', source_ref: 'NCRP-2026-258846', confidence: 0.9, added_at: 1792540000, ...over,
})
const lead = (over = {}) => ({
  lead_id: 'L-I-C-009-004-bank', case_id: 'C-009', identifier_id: 'I-C-009-004', choke_point: 'bank', holder: 'HDFC Bank',
  what_it_identifies: 'Account holder, KYC documents and statements', requests: ['account_details_request', 'freeze_request', 'preservation_notice'],
  priority: 'urgent', rationale: 'The victim paid into this account.', ...over,
})
const IDS = [ident(), ident({ identifier_id: 'I-C-009-004', kind: 'bank_account', value: '000123450001', label: 'HDFC Bank', role: 'payment', confidence: 0.5 })]
const LEADS = [
  lead(),
  lead({ lead_id: 'L-2', identifier_id: 'I-C-009-002', choke_point: 'messaging_platform', holder: 'Telegram', priority: 'high', requests: ['preservation_notice', 'takedown_request'] }),
]

const panel = (routes = {}) => {
  const backend = installBackend({ '/api/officer/cases/C-009/identifiers': IDS, '/api/officer/cases/C-009/leads': LEADS, ...routes })
  render(<LeadsPanel caseId="C-009" />)
  return backend
}

describe('the leads panel', () => {
  it('lists each lead with who holds the data, what it can tell us and the requests', async () => {
    panel()
    const leads = await screen.findAllByTestId('lead')
    expect(leads).toHaveLength(2)
    const first = within(leads[0])
    expect(first.getByText('urgent')).toBeInTheDocument()
    expect(first.getByText('Bank')).toBeInTheDocument()
    expect(first.getByText(/HDFC Bank/)).toBeInTheDocument()
    expect(first.getByText(/account holder, kyc documents and statements/i)).toBeInTheDocument()
    for (const label of ['Account details', 'Freeze request', 'Preservation notice']) expect(first.getByText(label)).toBeInTheDocument()
    expect(first.getByText(/bank account 000123450001/i)).toBeInTheDocument()          // names the identifier it is about
    expect(within(leads[1]).getByText('Messaging or social platform')).toBeInTheDocument()
  })

  it('says it only suggests: nothing is sent from here', async () => {
    panel()
    expect(await screen.findByText(/suspected until an officer confirms/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /send/i })).toBeNull()
  })

  it('shows the identifiers with their role, source and confidence', async () => {
    panel()
    const row = (await screen.findByText('000123450001')).closest('tr')
    expect(row).toHaveTextContent('Bank account')
    expect(row).toHaveTextContent('HDFC Bank')
    expect(row).toHaveTextContent('Where they paid')
    expect(row).toHaveTextContent('complaint')
    expect(row).toHaveTextContent('50%')
  })

  it('has an empty state', async () => {
    panel({ '/api/officer/cases/C-009/leads': [], '/api/officer/cases/C-009/identifiers': [] })
    expect(await screen.findByText(/no leads yet/i)).toBeInTheDocument()
  })

  it('reports a failed load', async () => {
    panel({ '/api/officer/cases/C-009/leads': fail(500, 'ledger offline') })
    expect(await screen.findByRole('alert')).toHaveTextContent(/ledger offline/)
  })

  it('adds an identifier by hand and refreshes the leads', async () => {
    let leads = LEADS
    const { calls } = panel({
      '/api/officer/cases/C-009/leads': () => leads,
      'POST /api/officer/cases/C-009/identifiers': ident({ identifier_id: 'I-C-009-007', kind: 'phone', value: '9800012345' }),
    })
    const user = userEvent.setup()
    await screen.findAllByTestId('lead')
    leads = [...LEADS, lead({ lead_id: 'L-3', identifier_id: 'I-C-009-007', choke_point: 'telecom', holder: 'Telecom operator', priority: 'high' })]
    const form = within(screen.getByRole('form', { name: /add an identifier/i }))
    expect(form.getByRole('button', { name: /add/i })).toBeDisabled()
    await user.selectOptions(form.getByLabelText('Kind'), 'phone')
    await user.type(form.getByLabelText('Value'), '+91 98000 12345')
    await user.click(form.getByRole('button', { name: /add/i }))
    expect(await screen.findAllByTestId('lead')).toHaveLength(3)
    expect(calls.find((c) => c.method === 'POST').body).toEqual({ kind: 'phone', value: '+91 98000 12345' })
    expect(form.getByLabelText('Value')).toHaveValue('')
  })

  it('shows why an identifier was refused', async () => {
    panel({ 'POST /api/officer/cases/C-009/identifiers': fail(409, "That is already in this case's ledger.") })
    const user = userEvent.setup()
    await screen.findAllByTestId('lead')
    const form = within(screen.getByRole('form', { name: /add an identifier/i }))
    await user.type(form.getByLabelText('Value'), '9800012345')
    await user.click(form.getByRole('button', { name: /add/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already in this case's ledger/i)
  })
})

describe('new node types', () => {
  it('have colours and names, and appear in the legend', () => {
    expect(NODE_COLORS.dex).toMatch(/^#/)
    expect(NODE_COLORS.bank_account).toMatch(/^#/)
    expect(NODE_LABELS).toMatchObject({ dex: 'DEX (swap)', bank_account: 'Bank account' })
    render(<Legend />)
    expect(screen.getByText('DEX (swap)')).toBeInTheDocument()
    expect(screen.getByText('Bank account')).toBeInTheDocument()
    expect(new Set(Object.values(NODE_COLORS)).size).toBe(Object.keys(NODE_COLORS).length)         // every type is distinguishable
  })
})

describe('the optional lure-channel questions when filing', () => {
  const file = async (user, { demo = false, fill = async () => {} } = {}) => {
    const { calls } = installBackend({ 'POST /api/complaints': { complaint_id: 'NCRP-2026-111111', stage: 'received', message: 'ok' } })
    at(R.file)
    if (demo) await user.click(screen.getByRole('button', { name: /fill demo example/i }))
    else {
      await user.type(screen.getByLabelText(/your name/i), 'Asha')
      await user.type(screen.getByLabelText(/mobile number/i), '9876543210')
      await user.type(screen.getByLabelText(/wallet you sent/i), 'TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo')
    }
    await fill()
    await user.click(screen.getByRole('button', { name: /submit complaint/i }))
    await screen.findByTestId('complaint-id')
    return calls.find((c) => c.method === 'POST').body
  }

  it('are optional: a complaint without them sends nothing extra', async () => {
    const body = await file(userEvent.setup())
    for (const k of ['scammer_phone', 'scammer_handle', 'scam_website', 'scam_app', 'paid_to_upi', 'paid_to_bank_account', 'paid_to_ifsc']) {
      expect(body[k]).toBeNull()
    }
    expect(body.scammer_handle_platform).toBeNull()
  })

  it('carry what the citizen filled in, tidied', async () => {
    const user = userEvent.setup()
    const body = await file(user, {
      fill: async () => {
        await user.type(screen.getByLabelText(/scammer's phone number/i), ' +91 90000 00101 ')
        await user.type(screen.getByLabelText(/chat or social handle/i), '@alpha_demo')
        await user.selectOptions(screen.getByLabelText(/which app was it on/i), 'telegram')
        await user.type(screen.getByLabelText(/website the scammer used/i), 'alpha.example')
        await user.type(screen.getByLabelText(/upi id you paid/i), 'alpha@ybl')
        await user.type(screen.getByLabelText(/bank account you paid/i), '0001 2345 0001')
        await user.type(screen.getByLabelText(/ifsc code/i), 'HDFC0000001')
      },
    })
    expect(body).toMatchObject({
      scammer_phone: '+91 90000 00101', scammer_handle: '@alpha_demo', scammer_handle_platform: 'telegram', scam_website: 'alpha.example',
      paid_to_upi: 'alpha@ybl', paid_to_bank_account: '000123450001', paid_to_ifsc: 'HDFC0000001',
    })
  })

  it('call the platform "other" when a handle is given but the app is not', async () => {
    const user = userEvent.setup()
    const body = await file(user, { fill: async () => user.type(screen.getByLabelText(/chat or social handle/i), 'someone') })
    expect(body.scammer_handle_platform).toBe('other')
  })

  it('are filled by the demo example', async () => {
    const body = await file(userEvent.setup(), { demo: true })
    expect(body).toMatchObject({ scammer_phone: '+91 90000 00101', paid_to_upi: 'alpha.returns@ybl', scammer_handle_platform: 'telegram' })
  })

  it('show readable names when the server refuses one', () => {
    expect(describeDetail([{ loc: ['body', 'paid_to_upi'], msg: 'String should match pattern' }, { loc: ['body', 'paid_to_ifsc'], msg: 'bad' }])).toBe(
      'UPI ID: String should match pattern. IFSC code: bad',
    )
  })
})

describe('the officer complaint page', () => {
  const complaint = (over = {}) => ({
    complaint_id: 'NCRP-2026-104317', wallet: 'TDongf8XirZvCUFazHwM2FG7cukpnF9h9D', chain: 'tron', amount: 5000, currency: 'USDT', tx_hash: null,
    fraud_type: 'investment', state: 'Karnataka', description: null, reporter_name: 'Asha Verma', reporter_mobile: '9876543210', stage: 'received',
    case_id: null, created_at: 1792540000, updated_at: 1792540000, history: [{ at: 1792540000, stage: 'received', note: 'Complaint registered' }], ...over,
  })

  it('shows how the scammer reached the victim and where they paid', async () => {
    installBackend({
      '/api/officer/complaints/NCRP-2026-104317': complaint({
        scammer_phone: '+91 90000 00101', scammer_handle: '@alpha_returns_demo', scammer_handle_platform: 'telegram', scam_website: 'alpha-returns.example',
        paid_to_upi: 'alpha.returns@ybl', paid_to_bank_account: '000123450001', paid_to_ifsc: 'HDFC0000001',
      }),
    })
    at(R.officerComplaint('NCRP-2026-104317'))
    const box = within(await screen.findByLabelText(/how they were reached and where they paid/i))
    for (const text of ['+91 90000 00101', '@alpha_returns_demo', 'Telegram', 'alpha-returns.example', 'alpha.returns@ybl', '000123450001', 'HDFC0000001']) {
      expect(box.getByText(text)).toBeInTheDocument()
    }
  })

  it('leaves the section out when the citizen gave none', async () => {
    installBackend({ '/api/officer/complaints/NCRP-2026-104317': complaint() })
    at(R.officerComplaint('NCRP-2026-104317'))
    await screen.findByRole('heading', { name: 'NCRP-2026-104317' })
    expect(screen.queryByLabelText(/how they were reached and where they paid/i)).toBeNull()
  })
})
