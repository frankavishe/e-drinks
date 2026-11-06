import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { formatDate } from '../../lib/publicApi'
import Calendar from './Calendar'

vi.mock('../../lib/supabase', () => ({ supabase: null }))

const SATURDAY = '2030-01-12'

const BOOKINGS = [
  { id: 7, code: 'ED-2030-0007', status: 'confirmed', is_rush: true, customer_name: 'Asha', start_time: '16:00:00' },
  { id: 8, code: 'ED-2030-0008', status: 'request', is_rush: false, customer_name: 'Juma', start_time: '18:30:00' },
]

const COOLERS = { addon_id: 1, name_sw: 'Kipoza', name_en: 'Cooler', committed: 3, owned: 5 }
const WAITERS = { addon_id: 2, name_sw: 'Mhudumu', name_en: 'Waiter', committed: 4, owned: null }
const GLASSES = { addon_id: 3, name_sw: 'Glasi', name_en: 'Glasses', committed: 5, owned: 5 }

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const t = (key: string) => i18n.t(key)

function datesBetween(from: string, to: string): string[] {
  const dates = []
  const day = new Date(`${from}T00:00:00Z`)
  while (day.toISOString().slice(0, 10) <= to) {
    dates.push(day.toISOString().slice(0, 10))
    day.setUTCDate(day.getUTCDate() + 1)
  }
  return dates
}

let urls: string[]
let failing: boolean
const language = i18n.language

beforeEach(() => {
  urls = []
  failing = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      urls.push(url)
      if (failing) return json({ detail: 'no' }, 500)
      const query = new URL(url, 'http://test').searchParams
      return json({
        days: datesBetween(query.get('from')!, query.get('to')!).map((date) =>
          date === SATURDAY
            ? { date, bookings: BOOKINGS, addons: [COOLERS, WAITERS, GLASSES] }
            : { date, bookings: [], addons: [] },
        ),
      })
    }),
  )
})

afterEach(async () => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  await i18n.changeLanguage(language)
})

function Address() {
  const { search } = useLocation()
  return <output data-testid="address">{search}</output>
}

function renderPage(search = `?date=${SATURDAY}`) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[`/admin/calendar${search}`]}>
        <Calendar />
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const lastQuery = () => new URL(urls[urls.length - 1], 'http://test').searchParams

async function expectRange(from: string, to: string) {
  await waitFor(() => {
    expect(lastQuery().get('from')).toBe(from)
    expect(lastQuery().get('to')).toBe(to)
  })
}

const address = () => new URLSearchParams(screen.getByTestId('address').textContent ?? '')

const day = (date: string) =>
  within(screen.getByRole('listitem', { name: new RegExp(formatDate(date, i18n.language)) }))

const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }))

describe('Calendar range', () => {
  it('asks for the full Monday-to-Sunday weeks that cover the month', async () => {
    renderPage()
    await expectRange('2029-12-31', '2030-02-03')
    await screen.findByRole('link', { name: /ED-2030-0007/ })
  })

  it('asks for Monday to Sunday in week view', async () => {
    renderPage(`?view=week&date=${SATURDAY}`)
    await expectRange('2030-01-07', '2030-01-13')
    await screen.findByRole('link', { name: /ED-2030-0007/ })
  })

  it('treats Sunday as the end of its week', async () => {
    renderPage('?view=week&date=2030-01-13')
    await expectRange('2030-01-07', '2030-01-13')
    await screen.findByRole('link', { name: /ED-2030-0007/ })
  })

  it('switching view keeps the date', async () => {
    renderPage()
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    click(t('admin.calendar.week'))
    await expectRange('2030-01-07', '2030-01-13')
    expect(address().get('view')).toBe('week')
    expect(address().get('date')).toBe(SATURDAY)
  })
})

describe.each(['month', 'week'])('Calendar %s view', (view) => {
  const search = `?view=${view}&date=${SATURDAY}`

  it('shows both bookings of one day with links to them', async () => {
    renderPage(search)
    expect(await screen.findByRole('link', { name: /ED-2030-0007/ })).toHaveAttribute('href', '/admin/bookings/7')
    expect(screen.getByRole('link', { name: /ED-2030-0008/ })).toHaveAttribute('href', '/admin/bookings/8')
    const saturday = day(SATURDAY)
    expect(saturday.getByText('Asha')).toBeInTheDocument()
    expect(saturday.getByText('Juma')).toBeInTheDocument()
    expect(saturday.getByText(/16:00/)).toBeInTheDocument()
  })

  it('shows combined add-on usage against what is owned', async () => {
    renderPage(search)
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(
      day(SATURDAY).getByText(i18n.t('admin.calendar.usage', { committed: 3, owned: 5 })),
    ).toBeInTheDocument()
  })
})

describe('Calendar day', () => {
  it('says "in use" for an add-on with no limit', async () => {
    renderPage()
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(day(SATURDAY).getByText(i18n.t('admin.calendar.inUse', { committed: 4 }))).toBeInTheDocument()
  })

  it('marks only the add-on at capacity as full', async () => {
    renderPage()
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    const saturday = day(SATURDAY)
    expect(saturday.getAllByText(t('admin.calendar.full'))).toHaveLength(1)
    const glasses = saturday.getByText('Glasi', { exact: false }).closest('li')!
    expect(within(glasses).getByText(t('admin.calendar.full'))).toBeInTheDocument()
  })

  it('shows the stage on each booking and a rush flag only on a rush booking', async () => {
    renderPage()
    const rush = within(await screen.findByRole('link', { name: /ED-2030-0007/ }))
    const plain = within(screen.getByRole('link', { name: /ED-2030-0008/ }))
    expect(rush.getByText(t('status.confirmed'))).toBeInTheDocument()
    expect(rush.getByText(t('admin.flag.rush'))).toBeInTheDocument()
    expect(plain.getByText(t('status.request'))).toBeInTheDocument()
    expect(plain.queryByText(t('admin.flag.rush'))).not.toBeInTheDocument()
  })

  it('names add-ons in the current language', async () => {
    await i18n.changeLanguage('en')
    renderPage()
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(day(SATURDAY).getByText('Cooler', { exact: false })).toBeInTheDocument()
    expect(day(SATURDAY).queryByText('Kipoza', { exact: false })).not.toBeInTheDocument()
  })
})

describe('Calendar navigation', () => {
  it('moves by a month in month view, and across a year end', async () => {
    renderPage('?date=2029-12-15')
    await expectRange('2029-11-26', '2030-01-06')
    click(t('admin.calendar.next'))
    await expectRange('2029-12-31', '2030-02-03')
    expect(address().get('date')).toBe('2030-01-01')
    click(t('admin.calendar.previous'))
    await expectRange('2029-11-26', '2030-01-06')
  })

  it('does not skip a short month from the 31st', async () => {
    renderPage('?date=2030-01-31')
    await expectRange('2029-12-31', '2030-02-03')
    click(t('admin.calendar.next'))
    await expectRange('2030-01-28', '2030-03-03')
    expect(address().get('date')).toBe('2030-02-01')
  })

  it('moves by seven days in week view', async () => {
    renderPage(`?view=week&date=${SATURDAY}`)
    await expectRange('2030-01-07', '2030-01-13')
    click(t('admin.calendar.next'))
    await expectRange('2030-01-14', '2030-01-20')
    click(t('admin.calendar.previous'))
    click(t('admin.calendar.previous'))
    await expectRange('2029-12-31', '2030-01-06')
  })

  it('returns to today', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2030-03-15T09:00:00Z'))
    renderPage()
    await expectRange('2029-12-31', '2030-02-03')
    click(t('admin.calendar.today'))
    await expectRange('2030-02-25', '2030-03-31')
    expect(address().get('date')).toBe('2030-03-15')
  })

  it('restores the view and date from the address, so Back from a booking keeps them', async () => {
    renderPage('?view=week&date=2030-01-08')
    await expectRange('2030-01-07', '2030-01-13')
    expect(screen.getByRole('button', { name: t('admin.calendar.week') })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: t('admin.calendar.month') })).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('Calendar defaults', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    // Already 13 January in Dar es Salaam, still the 12th in UTC.
    vi.setSystemTime(new Date('2030-01-12T22:00:00Z'))
  })

  it('opens on the current month in Dar es Salaam', async () => {
    renderPage('')
    await expectRange('2029-12-31', '2030-02-03')
    await screen.findByRole('link', { name: /ED-2030-0007/ })
    expect(screen.getByRole('listitem', { name: new RegExp(formatDate('2030-01-13', i18n.language)) })).toHaveAttribute(
      'aria-current',
      'date',
    )
    expect(
      screen.getByRole('listitem', { name: new RegExp(formatDate(SATURDAY, i18n.language)) }),
    ).not.toHaveAttribute('aria-current')
  })

  it.each(['2030-02-31', 'soon', '2030-1-1'])('ignores the invalid date %s', async (date) => {
    renderPage(`?view=week&date=${date}`)
    await expectRange('2030-01-07', '2030-01-13')
  })

  it('ignores an unknown view', async () => {
    renderPage(`?view=year&date=${SATURDAY}`)
    await expectRange('2029-12-31', '2030-02-03')
  })
})

describe('Calendar load', () => {
  it('says so when the calendar cannot load', async () => {
    failing = true
    renderPage()
    expect(await screen.findByText(t('admin.loadFailed'))).toBeInTheDocument()
  })
})
