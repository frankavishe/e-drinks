import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import BookingWizard from './BookingWizard'

vi.mock('../../lib/supabase', () => ({ supabase: null }))

const QUOTE = {
  lines: [
    {
      product_id: 1, name_sw: 'Soda', name_en: 'Soda pop', unit: 'kreti', packs: 10,
      unit_price: 16000, line_total: 160000, empties_deposit: 60000, source: 'package',
    },
  ],
  addon_lines: [],
  subtotal: 400000,
  addons_total: 0,
  delivery_fee: 25000,
  delivery_custom: false,
  empties_deposit: 60000,
  total: 485000,
  deposit_due: 242500,
  balance_due_date: '2030-01-09',
  flags: { is_rush: false, below_minimum: false, min_order: 300000, provisional: false, addons_unavailable: [] },
}

const ROUTES: Record<string, unknown> = {
  '/public/settings': {
    business_name: 'e-drinks',
    whatsapp_number: '255700000000',
    policy_text_sw: 'Sera ya oda',
    policy_text_en: 'Booking policy',
    payment_instructions: { mpesa_till: '123456', tigopesa_lipa: '', airtel_lipa: '', bank_details: '' },
  },
  '/public/catalog': [
    { id: 1, name_sw: 'Soda', name_en: 'Soda pop', category: 'soft', unit: 'kreti', tiers: [] },
  ],
  '/public/packages': [
    {
      id: 2, slug: 'silver', name_sw: 'Fedha', name_en: 'Silver', description_sw: 'Soda na bia',
      description_en: 'Soda and beer', rules: [{ product_id: 1 }],
    },
  ],
  '/public/addons': [{ id: 3, name_sw: 'Jokofu', name_en: 'Cooler', kind: 'cooler', price: 15000 }],
  '/public/areas': {
    zones: [
      { id: 1, name: 'A', delivery_fee: 25000, areas: [{ id: 5, name: 'Masaki' }, { id: 6, name: 'Sinza' }] },
    ],
    venues: [{ id: 9, name: 'Ukumbi Masaki', area_id: 5, address: 'Barabara 1' }],
  },
  '/public/quote': QUOTE,
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

let bookingResponse: () => Response
let bookingBodies: Record<string, unknown>[]

beforeEach(() => {
  bookingBodies = []
  bookingResponse = () =>
    json(201, {
      code: 'ED-2030-0001', status: 'request', is_rush: false, provisional: false,
      total: 485000, deposit_due: 242500, balance_due_date: '2030-01-09',
      payment_instructions: { mpesa_till: '123456', tigopesa_lipa: '', airtel_lipa: '', bank_details: '' },
      whatsapp_number: '255700000000',
    })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.slice(url.indexOf('/public/')) // independent of VITE_API_URL
      if (path === '/public/bookings') {
        bookingBodies.push(JSON.parse(init!.body as string))
        return bookingResponse()
      }
      return json(200, ROUTES[path])
    }),
  )
})

afterEach(async () => {
  vi.unstubAllGlobals()
  await act(() => i18n.changeLanguage('sw'))
})

function renderWizard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BookingWizard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const t = (key: string) => i18n.t(key)
const next = () => fireEvent.click(screen.getByRole('button', { name: t('book.next') }))

async function fillEvent() {
  fireEvent.change(await screen.findByLabelText(t('book.event.date')), { target: { value: '2030-01-12' } })
  await screen.findByRole('option', { name: 'Ukumbi Masaki' })
  fireEvent.change(screen.getByLabelText(t('book.event.venue')), { target: { value: '9' } })
}

async function toContact() {
  await fillEvent()
  next()
  fireEvent.click(await screen.findByRole('radio', { name: /Fedha/ }))
  await screen.findByText(t('book.order.subtotal'))
  await waitFor(() => expect(screen.getByRole('button', { name: t('book.next') })).toBeEnabled())
  next()
  await screen.findByText('Jokofu')
  await waitFor(() => expect(screen.getByRole('button', { name: t('book.next') })).toBeEnabled())
  next()
  await screen.findByRole('heading', { name: t('book.review.title') })
  await screen.findByText('TSh 485,000')
  await waitFor(() => expect(screen.getByRole('button', { name: t('book.next') })).toBeEnabled())
  next()
  await screen.findByText('Sera ya oda')
}

function fillContact() {
  fireEvent.change(screen.getByLabelText(t('book.contact.name')), { target: { value: 'Asha' } })
  fireEvent.change(screen.getByLabelText(t('book.contact.phone')), { target: { value: '0712345678' } })
}

describe('BookingWizard', () => {
  it('fills area and address from a saved venue', async () => {
    renderWizard()
    await fillEvent()
    expect(screen.getByLabelText(t('book.event.area'))).toHaveValue('5')
    expect(screen.getByLabelText(t('book.event.venueAddress'))).toHaveValue('Barabara 1')
  })

  it('keeps entered data when the language changes', async () => {
    renderWizard()
    await fillEvent()
    fireEvent.change(screen.getByLabelText(t('book.event.guests')), { target: { value: '300' } })

    await act(() => i18n.changeLanguage('en'))

    expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    expect(screen.getByLabelText('Number of guests')).toHaveValue(300)
    expect(screen.getByLabelText('Event date')).toHaveValue('2030-01-12')
    expect(screen.getByLabelText('Area')).toHaveValue('5')
  })

  it('blocks moving on until the event is complete', async () => {
    renderWizard()
    await screen.findByLabelText(t('book.event.date'))
    expect(screen.getByRole('button', { name: t('book.next') })).toBeDisabled()
    await fillEvent()
    expect(screen.getByRole('button', { name: t('book.next') })).toBeEnabled()
  })

  it('blocks submit until the policy and 18+ boxes are both ticked', async () => {
    renderWizard()
    await toContact()
    fillContact()
    const submit = screen.getByRole('button', { name: t('book.contact.submit') })
    expect(submit).toBeDisabled()
    fireEvent.click(screen.getByLabelText(t('book.contact.acceptPolicy')))
    expect(submit).toBeDisabled()
    fireEvent.click(screen.getByLabelText(t('book.contact.ageConfirmed')))
    expect(submit).toBeEnabled()
  })

  it('submits the reviewed total and shows the booking number', async () => {
    renderWizard()
    await toContact()
    fillContact()
    fireEvent.click(screen.getByLabelText(t('book.contact.acceptPolicy')))
    fireEvent.click(screen.getByLabelText(t('book.contact.ageConfirmed')))
    fireEvent.click(screen.getByRole('button', { name: t('book.contact.submit') }))

    expect(await screen.findByText('ED-2030-0001')).toBeInTheDocument()
    expect(bookingBodies[0]).toMatchObject({
      expected_total: 485000, venue_id: 9, area_id: 5, package_id: 2, phone: '0712345678', lang: 'sw',
      setup_at: '2030-01-12T15:00:00+03:00', collect_at: '2030-01-13T09:00:00+03:00',
    })
    const whatsapp = screen.getByRole('link', { name: t('book.confirm.whatsapp') })
    expect(whatsapp.getAttribute('href')).toContain('https://wa.me/255700000000')
    expect(decodeURIComponent(whatsapp.getAttribute('href')!)).toContain('ED-2030-0001')
    expect(screen.getByText('123456')).toBeInTheDocument()
  })

  it('returns to review with the new quote when the total changed', async () => {
    bookingResponse = () =>
      json(409, { detail: { code: 'quote_changed', quote: { ...QUOTE, total: 490000 } } })
    renderWizard()
    await toContact()
    fillContact()
    fireEvent.click(screen.getByLabelText(t('book.contact.acceptPolicy')))
    fireEvent.click(screen.getByLabelText(t('book.contact.ageConfirmed')))
    fireEvent.click(screen.getByRole('button', { name: t('book.contact.submit') }))

    expect(await screen.findByText(t('book.conflict.quote_changed'))).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: t('book.review.title') })).toBeInTheDocument()
  })

  it('keeps the customer on contact details when the server refuses the phone', async () => {
    bookingResponse = () => json(422, { detail: [{ msg: 'bad phone' }] })
    renderWizard()
    await toContact()
    fillContact()
    fireEvent.click(screen.getByLabelText(t('book.contact.acceptPolicy')))
    fireEvent.click(screen.getByLabelText(t('book.contact.ageConfirmed')))
    fireEvent.click(screen.getByRole('button', { name: t('book.contact.submit') }))

    expect(await screen.findByText(t('book.contact.invalid'))).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText(t('book.contact.name'))).toHaveValue('Asha'))
  })
})
