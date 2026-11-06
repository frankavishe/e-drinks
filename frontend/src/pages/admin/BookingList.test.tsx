import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import BookingList from './BookingList'
import Dashboard from './Dashboard'

vi.mock('../../lib/supabase', () => ({ supabase: null }))

const ROW = {
  id: 7, code: 'ED-2030-0007', status: 'confirmed', is_rush: true, rush_approved: false, provisional: true,
  event_type: 'wedding', event_date: '2030-01-12', start_time: '18:00:00', guests: 300,
  customer_name: 'Asha', customer_phone: '255712345678', venue_name: 'Ukumbi', total: 245000,
  amount_paid: 122500, amount_pending: 50000,
}

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })

const t = (key: string) => i18n.t(key)

let urls: string[]
let list: { total: number; items: unknown[] }

beforeEach(() => {
  urls = []
  list = { total: 1, items: [ROW] }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      urls.push(url)
      if (url.includes('/admin/overview')) return json({ today: [ROW], upcoming: [{ ...ROW, id: 8, code: 'ED-2030-0008' }] })
      return json(list)
    }),
  )
})

afterEach(() => vi.unstubAllGlobals())

function renderPage(page: ReactElement, entry = '/admin/bookings') {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[entry]}>{page}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const lastQuery = () => new URL(urls[urls.length - 1], 'http://test').searchParams

describe('BookingList', () => {
  it('shows stage, flags and a link to the booking on each row', async () => {
    renderPage(<BookingList />)
    const link = await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(link).toHaveAttribute('href', '/admin/bookings/7')
    const row = within(link)
    expect(row.getByText('Asha')).toBeInTheDocument()
    expect(row.getByText(t('status.confirmed'))).toBeInTheDocument()
    expect(row.getByText(t('admin.flag.rush'))).toBeInTheDocument()
    expect(row.getByText(t('admin.flag.provisional'))).toBeInTheDocument()
  })

  it('leaves out a rush flag on an ordinary booking', async () => {
    list = { total: 1, items: [{ ...ROW, is_rush: false, provisional: false }] }
    renderPage(<BookingList />)
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(screen.queryByText(t('admin.flag.rush'))).not.toBeInTheDocument()
    expect(screen.queryByText(t('admin.flag.provisional'))).not.toBeInTheDocument()
  })

  it('sends only the filters that are set', async () => {
    renderPage(<BookingList />)
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect([...lastQuery().keys()].sort()).toEqual(['limit', 'offset'])
  })

  it('sends the search only when submitted', async () => {
    renderPage(<BookingList />)
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    const before = urls.length
    fireEvent.change(screen.getByLabelText(t('admin.list.search')), { target: { value: '0712 345 678' } })
    expect(urls.length).toBe(before)
    fireEvent.click(screen.getByRole('button', { name: t('admin.list.searchButton') }))
    await waitFor(() => expect(lastQuery().get('q')).toBe('0712 345 678'))
  })

  it('sends stage, date range and rush filters to the API', async () => {
    renderPage(<BookingList />)
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    fireEvent.change(screen.getByLabelText(t('admin.list.stage')), { target: { value: 'quoted' } })
    await waitFor(() => expect(lastQuery().get('status')).toBe('quoted'))
    fireEvent.change(screen.getByLabelText(t('admin.list.from')), { target: { value: '2030-01-01' } })
    await waitFor(() => expect(lastQuery().get('date_from')).toBe('2030-01-01'))
    fireEvent.change(screen.getByLabelText(t('admin.list.to')), { target: { value: '2030-01-31' } })
    await waitFor(() => expect(lastQuery().get('date_to')).toBe('2030-01-31'))
    fireEvent.click(screen.getByLabelText(t('admin.list.rushOnly')))
    await waitFor(() => expect(lastQuery().get('rush')).toBe('true'))
  })

  it('restores filters from the address, so Back from a booking keeps them', async () => {
    renderPage(<BookingList />, '/admin/bookings?q=asha&status=quoted')
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(lastQuery().get('q')).toBe('asha')
    expect(lastQuery().get('status')).toBe('quoted')
    expect(screen.getByLabelText(t('admin.list.search'))).toHaveValue('asha')
    expect(screen.getByLabelText(t('admin.list.stage'))).toHaveValue('quoted')
  })

  it('pages through results and returns to the first page when a filter changes', async () => {
    list = { total: 120, items: [ROW] }
    renderPage(<BookingList />)
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(screen.getByRole('button', { name: t('admin.list.previous') })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: t('admin.list.next') }))
    await waitFor(() => expect(lastQuery().get('offset')).toBe('50'))

    fireEvent.change(screen.getByLabelText(t('admin.list.stage')), { target: { value: 'quoted' } })
    await waitFor(() => expect(lastQuery().get('status')).toBe('quoted'))
    expect(lastQuery().get('offset')).toBe('0')
  })

  it('stops at the last page', async () => {
    list = { total: 1, items: [ROW] }
    renderPage(<BookingList />)
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(screen.getByRole('button', { name: t('admin.list.next') })).toBeDisabled()
  })

  it('says when nothing matches', async () => {
    list = { total: 0, items: [] }
    renderPage(<BookingList />)
    expect(await screen.findByText(t('admin.list.empty'))).toBeInTheDocument()
  })
})

describe('Dashboard', () => {
  it('lists today and upcoming separately', async () => {
    renderPage(<Dashboard />, '/admin')
    expect(await screen.findByRole('link', { name: /ED-2030-0007/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /ED-2030-0008/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: t('admin.dashboard.today') })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: t('admin.dashboard.upcoming') })).toBeInTheDocument()
  })
})
