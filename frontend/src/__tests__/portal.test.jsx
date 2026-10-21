import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppRoutes } from '../App'
import { R } from '../lib/routes'
import { installBackend } from './setup'

const at = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )

beforeEach(() => installBackend())

describe('gateway', () => {
  it('puts the message in the middle with the simulated hand-off and a demo notice', () => {
    at('/')
    const main = screen.getByRole('main')
    expect(within(main).getByRole('heading', { name: /crypto fraud reporting and response/i })).toBeInTheDocument()
    expect(within(main).getByText(/simulated hand-off from an official cybercrime reporting website/i)).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent(/not an official government website/i)
  })

  it('offers filing and tracking as the main actions', () => {
    at('/')
    const main = within(screen.getByRole('main'))
    expect(main.getByRole('link', { name: /file a complaint/i })).toHaveAttribute('href', R.file)
    expect(main.getByRole('link', { name: /track a complaint/i })).toHaveAttribute('href', R.track)
  })

  it('shows a three-step overview with no technical detail', () => {
    at('/')
    const steps = within(screen.getByRole('list', { name: /what happens after you report/i })).getAllByRole('listitem')
    expect(steps.map((s) => s.textContent)).toEqual([expect.stringMatching(/Register/), expect.stringMatching(/Review/), expect.stringMatching(/Action/)])
    expect(document.body.textContent).toMatch(/details of how a complaint is handled are not shown/i)
    expect(document.body.textContent).not.toMatch(/trace|wallet graph|exchange|blockchain analysis|VASP/i)
  })

  it('has a moving graph behind it, hidden from assistive technology', () => {
    at('/')
    expect(screen.getByTestId('network-background')).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('gateway side panel', () => {
  const sidebar = () => screen.getByRole('complementary', { name: /portal menu/i })

  it('is open by default, with the complaint tracker and the other doors', () => {
    at('/')
    expect(screen.getByRole('button', { name: /collapse menu/i })).toHaveAttribute('aria-expanded', 'true')
    const panel = within(sidebar())
    expect(panel.getByLabelText(/complaint id/i)).toBeInTheDocument()
    expect(panel.getByRole('button', { name: /^track$/i })).toBeInTheDocument()
    expect(panel.getByRole('link', { name: /file a complaint/i })).toHaveAttribute('href', R.file)
    expect(panel.getByText(/1930/)).toBeInTheDocument()
  })

  it('opens the officer console in a separate tab', () => {
    at('/')
    const link = within(sidebar()).getByRole('link', { name: /officer console/i })
    expect(link).toHaveAttribute('href', R.officer)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('collapses to a slim rail that keeps every door reachable', async () => {
    const user = userEvent.setup()
    at('/')
    await user.click(screen.getByRole('button', { name: /collapse menu/i }))
    expect(sidebar()).toHaveAttribute('data-collapsed', 'true')
    expect(screen.getByRole('button', { name: /expand menu/i })).toHaveAttribute('aria-expanded', 'false')
    const rail = within(sidebar())
    expect(rail.queryByLabelText(/complaint id/i)).toBeNull()
    expect(rail.getByRole('link', { name: /track a complaint/i })).toHaveAttribute('href', R.track)
    expect(rail.getByRole('link', { name: /file a complaint/i })).toHaveAttribute('href', R.file)
    expect(rail.getByRole('link', { name: /officer console/i })).toHaveAttribute('target', '_blank')
  })

  it('opens again and remembers the choice', async () => {
    const user = userEvent.setup()
    const first = at('/')
    await user.click(screen.getByRole('button', { name: /collapse menu/i }))
    first.unmount()
    at('/')
    expect(sidebar()).toHaveAttribute('data-collapsed', 'true')              // remembered
    await user.click(screen.getByRole('button', { name: /expand menu/i }))
    expect(sidebar()).toHaveAttribute('data-collapsed', 'false')
    expect(localStorage.getItem('gateway.sidebar')).toBe('expanded')
  })

  it('starts collapsed on a narrow screen unless the visitor chose otherwise', () => {
    const width = window.innerWidth
    window.innerWidth = 500
    at('/')
    expect(sidebar()).toHaveAttribute('data-collapsed', 'true')
    window.innerWidth = width
  })

  it('takes a complaint ID to the tracking page', async () => {
    const user = userEvent.setup()
    at('/')
    await user.type(within(sidebar()).getByLabelText(/complaint id/i), '  NCRP-2026-1234 ')
    await user.click(within(sidebar()).getByRole('button', { name: /^track$/i }))
    expect(await screen.findByRole('heading', { name: /track a complaint/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/complaint id/i)).toHaveValue('NCRP-2026-1234')
  })

  it('takes an empty submit to the tracking page without an ID', async () => {
    const user = userEvent.setup()
    at('/')
    await user.click(within(sidebar()).getByRole('button', { name: /^track$/i }))
    expect(await screen.findByRole('heading', { name: /track a complaint/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/complaint id/i)).toHaveValue('')
  })
})

describe('citizen side', () => {
  it('has its own layout with no officer navigation', () => {
    at(R.file)
    const nav = screen.getByRole('navigation', { name: /citizen navigation/i })
    expect(within(nav).getByRole('link', { name: /file a complaint/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /track a complaint/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^dashboard$/i })).toBeNull()
    expect(screen.queryByText(/officer console$/i, { selector: 'p' })).toBeNull()
    expect(document.querySelector('[data-area="citizen"]')).not.toBeNull()
    expect(document.querySelector('[data-area="officer"]')).toBeNull()
  })

  it('offers the officer console only as a separate-tab link', () => {
    at(R.file)
    const link = screen.getByRole('link', { name: /officer console/i })
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('does not open the officer alert stream', () => {
    at(R.file)
    expect(globalThis.EventSource).not.toHaveBeenCalled()
  })

  it('shows a filing form without asking for a complaint ID', () => {
    at(R.file)
    expect(screen.getByRole('heading', { name: /report a crypto fraud/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /submit complaint/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/complaint id/i)).toBeNull()
  })

  it('confirms a filed complaint with only its ID and a track link', () => {
    at(R.submitted('NCRP-2026-4321'))
    expect(screen.getByTestId('complaint-id')).toHaveTextContent('NCRP-2026-4321')
    expect(screen.getByRole('link', { name: /track this complaint/i })).toHaveAttribute('href', `${R.track}?id=NCRP-2026-4321`)
  })

  it('has a tracking form', () => {
    at(R.track)
    expect(screen.getByLabelText(/complaint id/i)).toBeInTheDocument()
  })

  it('sends /citizen to the filing page', () => {
    at(R.citizen)
    expect(screen.getByRole('heading', { name: /report a crypto fraud/i })).toBeInTheDocument()
  })
})

describe('officer console', () => {
  it('has its own layout with the officer navigation and a way back', async () => {
    at(R.officer)
    expect(document.querySelector('[data-area="officer"]')).not.toBeNull()
    expect(document.querySelector('[data-area="citizen"]')).toBeNull()
    const nav = screen.getByRole('navigation')
    expect(within(nav).getByRole('link', { name: /dashboard/i })).toHaveAttribute('href', R.officer)
    expect(within(nav).getByRole('link', { name: /networks/i })).toHaveAttribute('href', R.officerNetworks)
    expect(screen.getByRole('link', { name: /back to the portal/i })).toHaveAttribute('href', R.gateway)
    expect(screen.queryByRole('link', { name: /new complaint/i })).toBeNull()
    expect(await screen.findByRole('heading', { name: /dashboard/i })).toBeInTheDocument()
  })

  it('opens the alert stream', () => {
    at(R.officer)
    expect(globalThis.EventSource).toHaveBeenCalled()
  })
})

describe('older links and unknown pages', () => {
  it.each([
    ['/complaint/new', /report a crypto fraud/i],
    ['/network', /networks/i],
  ])('%s still works', async (path, heading) => {
    at(path)
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
  })

  it('sends an old case link to the officer console', async () => {
    installBackend({ '/api/cases/C-001': { case_id: 'C-001' } })
    at('/cases/C-001')
    expect(document.querySelector('[data-area="officer"]')).not.toBeNull()
  })

  it('has a not-found page that leads back to the start', () => {
    at('/nowhere')
    expect(screen.getByRole('link', { name: /back to the start/i })).toHaveAttribute('href', R.gateway)
  })
})

describe('route helpers', () => {
  it('build paths and escape ids', () => {
    expect(R.officerCase('C-001')).toBe('/officer/cases/C-001')
    expect(R.submitted('A B/C')).toBe('/citizen/submitted/A%20B%2FC')
    expect(R.officerNetwork('NET-1')).toBe('/officer/networks?id=NET-1')
  })
})
