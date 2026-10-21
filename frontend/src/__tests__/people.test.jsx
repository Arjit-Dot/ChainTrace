import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import PeoplePanel from '../components/case/PeoplePanel'
import { fail, installBackend } from './setup'

const PEOPLE = {
  case_id: 'C-001',
  cluster: {
    cluster_id: 'CL-C-001', case_ids: ['C-001', 'C-002'], complaint_ids: ['NCRP-1', 'NCRP-2'], total_lost: 5200, states: ['Kerala', 'Karnataka'],
    summary: '2 complaints share a domain and a payment handle, so they may be one operation.', caution: 'Links are inferences.',
    shared: [{ kind: 'domain', value: 'hero-invest.example', strength: 'strong', case_ids: ['C-001', 'C-002'] }],
    people: [],
  },
  people: [
    { name: 'Anil Varkey (demo)', role: 'operator_suspected', confidence: 0.85, basis: 'Named by 3 institutions in 2 cases.', identifiers: ['9000000513'],
      case_ids: ['C-001', 'C-002'], evidence: [{ institution: 'Example Exchange B', case_id: 'C-001', request_id: 'R-1', field: 'Account holder', value: 'Anil Varkey (demo)' }] },
    { name: 'Sita Nair (demo)', role: 'mule_holder', confidence: 0.3, basis: 'Holds an account that received funds; often a victim.', identifiers: [],
      case_ids: ['C-001'], evidence: [{ institution: 'Example Bank', case_id: 'C-001', request_id: 'R-2', field: 'Account holder', value: 'Sita Nair (demo)' }] },
  ],
}
const NONE = { case_id: 'C-009', cluster: null, people: [] }
const show = (id = 'C-001') => render(<MemoryRouter><PeoplePanel caseId={id} /></MemoryRouter>)
const NOT_REFERRED = fail(404, 'This case has not been referred.')

describe('the people panel', () => {
  it('shows the linked cases, shared identifiers with strength, and the suspected people', async () => {
    installBackend({ '/api/officer/cases/C-001/people': PEOPLE, '/api/officer/cases/C-001/referral': NOT_REFERRED })
    show()
    const cluster = within(await screen.findByTestId('cluster'))
    expect(cluster.getByText(/may be one operation/)).toBeInTheDocument()
    expect(cluster.getByText('strong')).toBeInTheDocument()
    expect(cluster.getByText('hero-invest.example')).toBeInTheDocument()
    expect(cluster.getByText(/C-001 \(this case\)/)).toBeInTheDocument()
    const people = screen.getAllByTestId('person')
    expect(people).toHaveLength(2)
    expect(within(people[0]).getByText('85%')).toBeInTheDocument()
    expect(within(people[1]).getByText(/Holder of a mule account/)).toBeInTheDocument()
    expect(within(people[1]).getByText(/often a victim/)).toBeInTheDocument()
  })

  it('says so when there is no link and nobody has been named', async () => {
    installBackend({ '/api/officer/cases/C-009/people': NONE, '/api/officer/cases/C-009/referral': NOT_REFERRED })
    show('C-009')
    expect(await screen.findByText(/shares no identifier/i)).toBeInTheDocument()
    expect(screen.getByText(/No institution has named a person yet/i)).toBeInTheDocument()
  })

  it('reports a load failure instead of an empty panel', async () => {
    installBackend({ '/api/officer/cases/C-001/people': fail(500, 'boom'), '/api/officer/cases/C-001/referral': NOT_REFERRED })
    show()
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i)
  })

  it('offers the dossier download without victim details or claims of arrest', async () => {
    installBackend({ '/api/officer/cases/C-001/people': PEOPLE, '/api/officer/cases/C-001/referral': NOT_REFERRED })
    show()
    const link = await screen.findByRole('link', { name: /download referral dossier/i })
    expect(link.getAttribute('href')).toMatch(/\/api\/officer\/cases\/C-001\/dossier$/)
    expect(screen.getByText(/arrest or legal action is for the agency/i)).toBeInTheDocument()
  })

  it('records a referral and then shows it with the dossier hash', async () => {
    let referred = null
    const backend = installBackend({
      '/api/officer/cases/C-001/people': PEOPLE,
      '/api/officer/cases/C-001/referral': () => referred ?? NOT_REFERRED,
      'POST /api/officer/cases/C-001/referral': (init) => {
        referred = { case_id: 'C-001', ...JSON.parse(init.body), referred_at: 1792540000, dossier_sha256: 'ab12'.repeat(16), status: 'referred' }
        return referred
      },
    })
    show()
    const button = await screen.findByRole('button', { name: /record referral/i })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Agency'), 'State cyber cell ')
    await userEvent.type(screen.getByLabelText('Note'), 'Linked to C-002')
    await userEvent.click(button)
    const done = within(await screen.findByTestId('referral'))
    expect(done.getByText('State cyber cell')).toBeInTheDocument()
    expect(done.getByText(/ab12ab12/)).toBeInTheDocument()
    expect(backend.calls.find((c) => c.method === 'POST').body).toEqual({ agency: 'State cyber cell', note: 'Linked to C-002' })
    expect(screen.queryByRole('button', { name: /record referral/i })).toBeNull()
  })

  it('shows the server message when the referral is refused', async () => {
    installBackend({
      '/api/officer/cases/C-001/people': PEOPLE,
      '/api/officer/cases/C-001/referral': NOT_REFERRED,
      'POST /api/officer/cases/C-001/referral': fail(409, 'This case has already been referred.'),
    })
    show()
    await userEvent.type(await screen.findByLabelText('Agency'), 'CBI')
    await userEvent.click(screen.getByRole('button', { name: /record referral/i }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/already been referred/))
  })
})
