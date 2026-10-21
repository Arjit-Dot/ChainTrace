import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from '../App'
import { R } from '../lib/routes'
import { fail, installBackend } from './setup'

const at = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )

const ID = 'NCRP-2026-482913'
const STATUS_PATH = `/api/complaints/${ID}/status`
const MESSAGES = {
  received: 'Your complaint has been registered.',
  under_review: 'An officer is reviewing your complaint.',
  investigating: 'Your complaint is being investigated.',
  action_initiated: 'Action has been initiated with the relevant institutions.',
  closed: 'Your complaint has been closed. For details, please call the National Cyber Crime Helpline 1930.',
}
const LABELS = { received: 'Received', under_review: 'Under review', investigating: 'Investigation in progress', action_initiated: 'Action initiated', closed: 'Closed' }
const ORDER = Object.keys(LABELS)

const view = (stage = 'received', over = {}) => {
  const upto = ORDER.slice(0, ORDER.indexOf(stage) + 1)
  return {
    complaint_id: ID, stage, label: LABELS[stage], message: MESSAGES[stage], updated_at: 1792579431,
    timeline: upto.map((s, i) => ({ stage: s, label: LABELS[s], message: MESSAGES[s], at: 1792570000 + i * 3600 })), ...over,
  }
}

afterEach(() => vi.useRealTimers())

describe('the tracking page', () => {
  it('shows only the form, and looks nothing up, until an ID is given', () => {
    const { calls } = installBackend()
    at(R.track)
    expect(screen.getByLabelText(/complaint id/i)).toHaveValue('')
    expect(calls).toHaveLength(0)
  })

  it('looks up the ID in the address and shows the status in plain words', async () => {
    const { calls } = installBackend({ [STATUS_PATH]: view('investigating') })
    at(`${R.track}?id=${ID}`)
    expect(await screen.findByRole('heading', { name: 'Investigation in progress' })).toBeInTheDocument()
    const result = within(screen.getByRole('status', { name: /complaint status/i }))
    expect(result.getByTestId('tracked-id')).toHaveTextContent(ID)
    expect(result.getAllByText(MESSAGES.investigating).length).toBeGreaterThan(0)
    expect(result.getByText(/last updated/i)).toBeInTheDocument()
    expect(calls.filter((c) => c.path === STATUS_PATH)).toHaveLength(1)
  })

  it('lists what has happened, oldest first, with generic messages only', async () => {
    installBackend({ [STATUS_PATH]: view('investigating') })
    at(`${R.track}?id=${ID}`)
    const history = await screen.findByText(/what has happened so far/i)
    const items = within(history.parentElement.querySelector('ol')).getAllByRole('listitem')
    expect(items.map((li) => li.querySelector('p').textContent)).toEqual(['Received', 'Under review', 'Investigation in progress'])
  })

  it.each(ORDER)('marks the progress bar correctly at the %s stage', async (stage) => {
    installBackend({ [STATUS_PATH]: view(stage) })
    at(`${R.track}?id=${ID}`)
    const bar = within(await screen.findByRole('list', { name: 'Progress' })).getAllByRole('listitem')
    const state = bar.map((li) => li.dataset.state)
    const at_ = ORDER.indexOf(stage)
    expect(state).toEqual(ORDER.map((_, i) => (i < at_ || (stage === 'closed' && i === at_) ? 'done' : i === at_ ? 'current' : 'todo')))
    const current = bar.filter((li) => li.getAttribute('aria-current') === 'step')
    expect(current).toHaveLength(stage === 'closed' ? 0 : 1)
  })

  it('shows the helpline in the closing message and the not-shown notice', async () => {
    installBackend({ [STATUS_PATH]: view('closed') })
    at(`${R.track}?id=${ID}`)
    expect((await screen.findAllByText(/helpline 1930/i)).length).toBeGreaterThan(0)
    expect(screen.getByText(/details of how a complaint is handled are not shown/i)).toBeInTheDocument()
  })

  it('shows ONLY the permitted fields even if the server sends more by mistake', async () => {
    installBackend({
      [STATUS_PATH]: view('investigating', {
        wallet: 'TLEAKEDWALLETADDRESS', reporter_name: 'Leaked Name', reporter_mobile: '9999900000', case_id: 'C-777', vasp: 'Leaked Exchange',
        amount: 987654, history: [{ note: 'leaked officer note' }],
        timeline: [{ stage: 'received', label: 'Received', message: MESSAGES.received, at: 1792570000, officer: 'Leaked Officer', case_id: 'C-777' }],
      }),
    })
    at(`${R.track}?id=${ID}`)
    await screen.findByRole('heading', { name: 'Investigation in progress' })
    for (const secret of ['LEAKED', 'Leaked', '9999900000', 'C-777', '987654', 'leaked']) {
      expect(document.body.textContent).not.toContain(secret)
    }
  })

  it('only ever asks the public status endpoint', async () => {
    const { calls } = installBackend({ [STATUS_PATH]: view('received') })
    at(`${R.track}?id=${ID}`)
    await screen.findByRole('heading', { name: 'Received' })
    expect(calls.every((c) => c.path === STATUS_PATH && c.method === 'GET')).toBe(true)
    expect(calls.some((c) => c.path.includes('/officer/'))).toBe(false)
  })
})

describe('looking up by typing', () => {
  it('tidies the ID (spaces, lower case) and shows the result', async () => {
    const { calls } = installBackend({ [STATUS_PATH]: view('received') })
    const user = userEvent.setup()
    at(R.track)
    await user.type(screen.getByLabelText(/complaint id/i), `  ${ID.toLowerCase()}  `)
    await user.click(screen.getByRole('button', { name: /^track$/i }))
    expect(await screen.findByTestId('tracked-id')).toHaveTextContent(ID)
    expect(calls.map((c) => c.path)).toContain(STATUS_PATH)
  })

  it('does nothing on an empty submit', async () => {
    const { calls } = installBackend()
    const user = userEvent.setup()
    at(R.track)
    await user.click(screen.getByRole('button', { name: /^track$/i }))
    expect(calls).toHaveLength(0)
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('goes from the confirmation page straight to the status', async () => {
    installBackend({ [STATUS_PATH]: view('received') })
    const user = userEvent.setup()
    at(R.submitted(ID))
    await user.click(screen.getByRole('link', { name: /track this complaint/i }))
    expect(await screen.findByRole('heading', { name: 'Received' })).toBeInTheDocument()
  })

  it('works from the landing page tracker too', async () => {
    installBackend({ [STATUS_PATH]: view('under_review') })
    const user = userEvent.setup()
    at('/')
    await user.type(screen.getByLabelText(/complaint id/i), ID)
    await user.click(screen.getByRole('button', { name: /^track$/i }))
    expect(await screen.findByRole('heading', { name: 'Under review' })).toBeInTheDocument()
  })
})

describe('when something goes wrong', () => {
  it('says plainly that no complaint was found, without hints', async () => {
    installBackend({ [STATUS_PATH]: fail(404, 'No complaint was found for that ID. Check the ID and try again.') })
    at(`${R.track}?id=${ID}`)
    expect(await screen.findByRole('alert')).toHaveTextContent('No complaint was found for that ID. Check the ID and try again.')
    expect(screen.queryByRole('status', { name: /complaint status/i })).toBeNull()
  })

  it('asks the citizen to wait when there have been too many lookups', async () => {
    installBackend({ [STATUS_PATH]: fail(429, 'Too many lookups. Please wait a minute and try again.') })
    at(`${R.track}?id=${ID}`)
    expect(await screen.findByRole('alert')).toHaveTextContent(/too many lookups/i)
  })

  it('shows a friendly message when the server is down', async () => {
    installBackend({ [STATUS_PATH]: fail(500, '') })
    at(`${R.track}?id=${ID}`)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('clears an old result when a new, unknown ID is looked up', async () => {
    installBackend({ [STATUS_PATH]: view('received'), '/api/complaints/NCRP-2026-000000/status': fail(404, 'No complaint was found for that ID. Check the ID and try again.') })
    const user = userEvent.setup()
    at(`${R.track}?id=${ID}`)
    await screen.findByTestId('tracked-id')
    await user.clear(screen.getByLabelText(/complaint id/i))
    await user.type(screen.getByLabelText(/complaint id/i), 'NCRP-2026-000000')
    await user.click(screen.getByRole('button', { name: /^track$/i }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByTestId('tracked-id')).toBeNull()
  })
})

describe('keeping the status fresh', () => {
  it('refreshes on request', async () => {
    let stage = 'received'
    const { calls } = installBackend({ [STATUS_PATH]: () => view(stage) })
    const user = userEvent.setup()
    at(`${R.track}?id=${ID}`)
    await screen.findByRole('heading', { name: 'Received' })
    stage = 'investigating'
    await user.click(screen.getByRole('button', { name: /refresh/i }))
    expect(await screen.findByRole('heading', { name: 'Investigation in progress' })).toBeInTheDocument()
    expect(calls.filter((c) => c.path === STATUS_PATH)).toHaveLength(2)
  })

  it('checks again on its own every 30 seconds and stops when the page is left', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let stage = 'received'
    const { calls } = installBackend({ [STATUS_PATH]: () => view(stage) })
    const { unmount } = at(`${R.track}?id=${ID}`)
    await screen.findByRole('heading', { name: 'Received' })
    stage = 'action_initiated'
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000)
    })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Action initiated' })).toBeInTheDocument())
    const n = calls.length
    unmount()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(90000)
    })
    expect(calls).toHaveLength(n)
  })

  it('keeps showing the last status if a background check fails', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let answer = view('received')
    installBackend({ [STATUS_PATH]: () => answer })
    at(`${R.track}?id=${ID}`)
    await screen.findByRole('heading', { name: 'Received' })
    answer = fail(500, 'boom')
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000)
    })
    expect(screen.getByRole('heading', { name: 'Received' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
