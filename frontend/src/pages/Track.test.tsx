import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import Track from './Track'

vi.mock('../lib/supabase', () => ({ supabase: null }))

const BOOKING = {
  code: 'ED-2030-0001', status: 'request', is_rush: false, provisional: false,
  event_type: 'wedding', event_date: '2030-01-12', start_time: '18:00:00', hours: 5, guests: 300,
  venue_name: 'Ukumbi Masaki', venue_address: 'Barabara 1',
  items: [{ name_sw: 'Soda', name_en: 'Soda pop', unit: 'kreti', qty: 10, unit_price: 16000, line_total: 160000 }],
  addons: [],
  subtotal: 160000, addons_total: 0, delivery_fee: 25000, empties_deposit: 60000, total: 245000,
  deposit_due: 122500, balance_due_date: '2030-01-09',
  amount_paid: 0, amount_pending: 0, balance_due: 245000,
  payments: [] as unknown[],
  payment_instructions: { mpesa_till: '123456', tigopesa_lipa: '', airtel_lipa: '', bank_details: '' },
}

const PENDING = {
  kind: 'deposit', amount: 122500, method: 'mpesa', reference: 'ABC123', status: 'pending',
  created_at: '2030-01-01T10:00:00Z',
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

let trackResponse: () => Response
let paymentResponse: () => Response
let paymentBodies: Record<string, unknown>[]

beforeEach(() => {
  paymentBodies = []
  trackResponse = () => json(200, BOOKING)
  paymentResponse = () => json(201, PENDING)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/public/track')) return trackResponse()
      paymentBodies.push(JSON.parse(init!.body as string))
      return paymentResponse()
    }),
  )
})

afterEach(() => vi.unstubAllGlobals())

const t = (key: string) => i18n.t(key)

function renderTrack() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <Track />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function lookUp() {
  fireEvent.change(screen.getByLabelText(t('track.code')), { target: { value: 'ed-2030-0001' } })
  fireEvent.change(screen.getByLabelText(t('track.phone')), { target: { value: '0712345678' } })
  fireEvent.click(screen.getByRole('button', { name: t('track.submit') }))
}

describe('Track', () => {
  it('shows the not-found message', async () => {
    trackResponse = () => json(404, { detail: 'Booking not found' })
    renderTrack()
    await lookUp()
    expect(await screen.findByText(t('track.notFound'))).toBeInTheDocument()
  })

  it('shows the too-many-attempts message', async () => {
    trackResponse = () => json(429, { detail: 'Too many attempts, try again later' })
    renderTrack()
    await lookUp()
    expect(await screen.findByText(t('track.tooMany'))).toBeInTheDocument()
  })

  it('shows status, lines, totals and payment details', async () => {
    renderTrack()
    await lookUp()
    expect(await screen.findByText('ED-2030-0001')).toBeInTheDocument()
    expect(screen.getByText(t('status.request'))).toBeInTheDocument()
    expect(screen.getByText('10 x Soda')).toBeInTheDocument()
    expect(screen.getAllByText('TSh 245,000').length).toBeGreaterThan(0)
    expect(screen.getByText('123456')).toBeInTheDocument()
    expect(screen.getByText(t('track.noPayments'))).toBeInTheDocument()
  })

  it('prefills the deposit and shows a submitted reference as pending', async () => {
    renderTrack()
    await lookUp()
    await screen.findByText('ED-2030-0001')
    expect(screen.getByLabelText(t('pay.amount'))).toHaveValue(122500)

    fireEvent.change(screen.getByLabelText(t('pay.reference')), { target: { value: 'abc123' } })
    trackResponse = () =>
      json(200, { ...BOOKING, payments: [PENDING], amount_pending: 122500 })
    fireEvent.click(screen.getByRole('button', { name: t('pay.submit') }))

    expect(await screen.findByText('ABC123')).toBeInTheDocument()
    expect(screen.getByText(t('pay.sent'))).toBeInTheDocument()
    expect(paymentBodies[0]).toMatchObject({
      phone: '0712345678', kind: 'deposit', method: 'mpesa', amount: 122500, reference: 'abc123',
    })
  })

  it('shows the duplicate message', async () => {
    paymentResponse = () => json(409, { detail: { code: 'duplicate_reference' } })
    renderTrack()
    await lookUp()
    await screen.findByText('ED-2030-0001')
    fireEvent.change(screen.getByLabelText(t('pay.reference')), { target: { value: 'abc123' } })
    fireEvent.click(screen.getByRole('button', { name: t('pay.submit') }))
    expect(await screen.findByText(t('pay.duplicate'))).toBeInTheDocument()
  })

  it('hides the payment form on a cancelled booking', async () => {
    trackResponse = () => json(200, { ...BOOKING, status: 'cancelled' })
    renderTrack()
    await lookUp()
    await screen.findByText('ED-2030-0001')
    await waitFor(() => expect(screen.queryByLabelText(t('pay.reference'))).not.toBeInTheDocument())
  })
})
