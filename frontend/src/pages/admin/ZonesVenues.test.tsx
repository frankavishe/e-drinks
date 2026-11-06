import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { formatTzs } from '../../lib/publicApi'
import ZonesVenues from './ZonesVenues'

vi.mock('../../lib/supabase', () => ({ supabase: null }))

const ZONES = [
  { id: 1, name: 'Kati', delivery_fee: 30000, areas: [{ id: 10, name: 'Masaki', zone_id: 1 }] },
  { id: 2, name: 'Mbali', delivery_fee: 80000, areas: [] },
]
const VENUES = [{ id: 5, name: 'Serena', area_id: 10, address: 'Ohio St' }]

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const t = (key: string, options?: Record<string, unknown>) => i18n.t(key, options ?? {})

let role: string
let writes: { method: string; url: string; body: unknown }[]
let writeResponse: () => Response

beforeEach(() => {
  role = 'owner'
  writes = []
  writeResponse = () => json({})
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      if (init.method) {
        writes.push({ method: init.method, url, body: init.body ? JSON.parse(String(init.body)) : undefined })
        return writeResponse()
      }
      if (url.endsWith('/admin/me')) return json({ id: 'a', role, name: 'Amina' })
      if (url.endsWith('/admin/zones')) return json(ZONES)
      return json(VENUES)
    }),
  )
})

afterEach(() => vi.unstubAllGlobals())

/** The role is already known, as it is once AdminLayout has loaded, so a missing control means something. */
function renderScreen() {
  const client = new QueryClient()
  client.setQueryData(['admin', 'me'], { id: 'a', role, name: 'Amina' })
  render(
    <QueryClientProvider client={client}>
      <ZonesVenues />
    </QueryClientProvider>,
  )
}

const edit = (name: string) => `${t('admin.manage.edit')}: ${name}`
const remove = (name: string) => `${t('admin.manage.delete')}: ${name}`

describe('ZonesVenues', () => {
  it('lets staff read zones, fees, areas and venues with no edit controls', async () => {
    role = 'staff'
    renderScreen()
    expect(await screen.findByText('Serena')).toBeInTheDocument()
    expect(screen.getByText('Kati')).toBeInTheDocument()
    expect(screen.getByText(formatTzs(30000))).toBeInTheDocument()
    expect(screen.getAllByText('Masaki').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('asks before deleting, and sends nothing if the owner goes back', async () => {
    renderScreen()
    fireEvent.click(await screen.findByRole('button', { name: remove('Mbali') }))
    expect(screen.getByText(t('admin.manage.deleteSure', { name: 'Mbali' }))).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: t('admin.keep') }))
    expect(writes).toEqual([])
    expect(screen.getByRole('button', { name: remove('Mbali') })).toBeInTheDocument()
  })

  it('shows why a zone with areas cannot be deleted', async () => {
    writeResponse = () => json({ detail: { code: 'in_use' } }, 409)
    renderScreen()
    fireEvent.click(await screen.findByRole('button', { name: remove('Kati') }))
    fireEvent.click(screen.getByRole('button', { name: t('admin.manage.deleteYes') }))
    expect(await screen.findByText(t('admin.refusal.in_use'))).toBeInTheDocument()
    expect(writes[0]).toMatchObject({ method: 'DELETE' })
    expect(writes[0].url).toMatch(/\/admin\/zones\/1$/)
  })

  it('shows why a repeated area name is refused and keeps what was typed', async () => {
    writeResponse = () => json({ detail: { code: 'already_exists' } }, 409)
    renderScreen()
    const form = (await screen.findAllByRole('form', { name: t('admin.zones.addArea') }))[0]
    fireEvent.change(within(form).getByLabelText(t('admin.zones.areaName')), { target: { value: 'Masaki' } })
    fireEvent.click(within(form).getByRole('button', { name: t('admin.zones.addArea') }))
    expect(await screen.findByText(t('admin.refusal.already_exists'))).toBeInTheDocument()
    expect(writes[0]).toMatchObject({ method: 'POST', body: { name: 'Masaki', zone_id: 1 } })
    expect(within(form).getByLabelText(t('admin.zones.areaName'))).toHaveValue('Masaki')
  })

  it('sends a changed delivery fee as a whole number', async () => {
    renderScreen()
    fireEvent.click(await screen.findByRole('button', { name: edit('Kati') }))
    const form = screen.getByRole('form', { name: edit('Kati') })
    fireEvent.change(within(form).getByLabelText(t('admin.zones.fee')), { target: { value: '35000' } })
    fireEvent.click(within(form).getByRole('button', { name: t('admin.manage.save') }))
    await waitFor(() => expect(writes).toHaveLength(1))
    expect(writes[0]).toMatchObject({ method: 'PATCH', body: { name: 'Kati', delivery_fee: 35000 } })
    expect(writes[0].url).toMatch(/\/admin\/zones\/1$/)
  })

  it('adds a venue in the chosen area', async () => {
    renderScreen()
    const form = await screen.findByRole('form', { name: t('admin.zones.addVenue') })
    fireEvent.change(within(form).getByLabelText(t('admin.zones.venueName')), { target: { value: 'Golden Tulip' } })
    fireEvent.change(within(form).getByLabelText(t('admin.zones.area')), { target: { value: '10' } })
    fireEvent.change(within(form).getByLabelText(t('admin.zones.address')), { target: { value: 'Toure Dr' } })
    fireEvent.click(within(form).getByRole('button', { name: t('admin.zones.addVenue') }))
    await waitFor(() => expect(writes).toHaveLength(1))
    expect(writes[0]).toMatchObject({
      method: 'POST',
      body: { name: 'Golden Tulip', area_id: 10, address: 'Toure Dr' },
    })
  })
})
