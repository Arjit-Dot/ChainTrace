import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MulesPanel, OutcomesPanel } from '../components/case/OutcomesPanel'
import { fail, installBackend } from './setup'

const outcome = (over = {}) => ({
  outcome_id: 'O-C-009-01', case_id: 'C-009', kind: 'vasp', title: 'Funds reached Example Exchange B', subject: 'TBoQtXFBhBwQwyazeNVhajEBR2umNMLUps',
  subject_label: 'Example Exchange B (deposit address)', amount: 4950, status: 'action_needed',
  handling: ['Send the KYC and freeze request to Example Exchange B', "Ask for the account holder's KYC", 'Record the reply'], lead_ids: ['L-1'], ...over,
})
const DEX = outcome({
  outcome_id: 'O-C-009-02', kind: 'dex', title: 'Funds were swapped on SunSwap V2', status: 'info', lead_ids: [],
  handling: ['A DEX pool has no account holder or custodian: it cannot be asked for KYC or told to freeze', 'Record the swap and follow the wallet that received the swapped tokens'],
})
const BANK = outcome({
  outcome_id: 'O-C-009-03', kind: 'bank_account', title: 'The victim paid a bank account at HDFC Bank', subject: '000123450001', subject_label: 'HDFC Bank', amount: null,
  handling: ['Send a freeze or lien request to HDFC Bank', 'Ask the bank to preserve its records'], lead_ids: ['L-2', 'L-3'],
})

const mule = (over = {}) => ({
  case_id: 'C-009', kind: 'wallet', value: 'TYjHqaFMvnejU1xN8Xz3AqzWk7Qb4ePGQa', label: null, hop: 1, risk: 'Critical', risk_score: 0.99,
  reasons: ['Forwards funds within 7 minutes (median)', 'Wallet was under a day old when funds arrived'], received: 5000, forwarded: 4950, onward: ['vasp'], identifier_id: 'I-1', ...over,
})
const BANK_MULE = mule({
  kind: 'bank_account', value: '000123450001', label: 'HDFC Bank', hop: null, risk: null, risk_score: null, received: 0, forwarded: 0, onward: [],
  reasons: ['The victim reported paying into this account', 'Not yet checked: the holder may be a victim too'],
})

const outcomes = (items) => {
  installBackend({ '/api/officer/cases/C-009/outcomes': items })
  render(<OutcomesPanel caseId="C-009" />)
}
const mules = (items) => {
  installBackend({ '/api/officer/cases/C-009/mules': items })
  render(<MulesPanel caseId="C-009" />)
}

describe('where the money went', () => {
  it('shows an exchange as action needed, with the steps in order', async () => {
    outcomes([outcome()])
    const card = within(await screen.findByTestId('outcome'))
    expect(card.getByText('Action needed')).toBeInTheDocument()
    expect(card.getByText('Exchange (VASP)')).toBeInTheDocument()
    expect(card.getByText('Funds reached Example Exchange B')).toBeInTheDocument()
    expect(card.getAllByRole('listitem').map((li) => li.textContent)).toEqual(outcome().handling)
    expect(card.getByText(/1 matching lead below/)).toBeInTheDocument()
    expect(card.getByText(/4,950/)).toBeInTheDocument()
  })

  it('shows a DEX as information only, saying it has no account holder', async () => {
    outcomes([DEX])
    const card = within(await screen.findByTestId('outcome'))
    expect(card.getByText('For information')).toBeInTheDocument()
    expect(card.getByText('DEX swap')).toBeInTheDocument()
    expect(card.getByText(/no account holder or custodian/i)).toBeInTheDocument()
    expect(card.queryByText(/matching lead/)).toBeNull()                                  // nobody to ask
  })

  it('shows a bank account by its number, with the bank and the freeze step', async () => {
    outcomes([BANK])
    const card = within(await screen.findByTestId('outcome'))
    expect(card.getByText('000123450001')).toBeInTheDocument()
    expect(card.getByText('Send a freeze or lien request to HDFC Bank')).toBeInTheDocument()
    expect(card.getByText(/2 matching leads below/)).toBeInTheDocument()
  })

  it('lists every outcome of a case, each marked with its kind', async () => {
    outcomes([outcome(), DEX, BANK])
    const cards = await screen.findAllByTestId('outcome')
    expect(cards.map((c) => c.dataset.kind)).toEqual(['vasp', 'dex', 'bank_account'])
  })

  it('reports a load failure', async () => {
    installBackend({ '/api/officer/cases/C-009/outcomes': fail(500, 'engine down') })
    render(<OutcomesPanel caseId="C-009" />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/engine down/)
  })
})

describe('suspected mules', () => {
  it('says plainly that these are suspected, and may be victims too', async () => {
    mules([mule()])
    await screen.findByTestId('mule')
    expect(screen.getByText(/suspected only/i)).toBeInTheDocument()
    expect(screen.getByText(/often held by someone who was tricked/i)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/confirmed|guilty|convicted/i)
  })

  it('shows a mule wallet with its risk, what it received and passed on, and where', async () => {
    mules([mule()])
    const row = within(await screen.findByTestId('mule'))
    expect(row.getByText('Wallet')).toBeInTheDocument()
    expect(row.getByText('Critical')).toBeInTheDocument()
    expect(row.getByText(/5,000/)).toBeInTheDocument()
    expect(row.getByText(/4,950/)).toBeInTheDocument()
    expect(row.getByText('an exchange')).toBeInTheDocument()
    expect(row.getByText(/forwards funds within 7 minutes/i)).toBeInTheDocument()
  })

  it('shows a mule bank account with its bank and no score', async () => {
    mules([BANK_MULE])
    const row = within(await screen.findByTestId('mule'))
    expect(row.getByText('000123450001')).toBeInTheDocument()
    expect(row.getByText(/HDFC Bank/)).toBeInTheDocument()
    expect(row.getByText('Not scored')).toBeInTheDocument()
    expect(row.getByText(/may be a victim too/i)).toBeInTheDocument()
  })

  it('names every kind of onward endpoint in words', async () => {
    mules([mule({ onward: ['vasp', 'dex', 'mixer', 'bridge', 'wallet'] })])
    const row = within(await screen.findByTestId('mule'))
    expect(row.getByText('an exchange, a DEX, a mixer, a bridge, another wallet')).toBeInTheDocument()
  })

  it('has an empty state and an error state', async () => {
    mules([])
    expect(await screen.findByText(/no suspected mules found/i)).toBeInTheDocument()
  })

  it('reports a load failure', async () => {
    installBackend({ '/api/officer/cases/C-009/mules': fail(500, 'boom') })
    render(<MulesPanel caseId="C-009" />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/boom/)
  })
})
