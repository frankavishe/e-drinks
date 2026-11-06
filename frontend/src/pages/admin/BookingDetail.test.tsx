import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import BookingDetail from './BookingDetail'

vi.mock('../../lib/supabase', () => ({ supabase: null }))

const PAYMENT = {
  id: 5, kind: 'deposit', method: 'mpesa', amount: 122500, reference: 'ABC123', status: 'pending',
  confirmed_by_name: null, confirmed_at: null, created_at: '2030-01-01T10:00:00Z',
}

const DETAIL = {
  id: 7, code: 'ED-2030-0007', status: 'request', is_rush: false, rush_approved: false, provisional: false,
  event_type: 'wedding', event_date: '2030-01-12', start_time: '18:00:00', guests: 300,
  customer_name: 'Asha', customer_phone: '255712345678', venue_name: 'Ukumbi', total: 245000,
  amount_paid: 0, amount_pending: 122500,
  customer_email: 'asha@example.com', hours: 5, venue_address: 'Barabara 1', custom_area: '', lang: 'sw',
  setup_at: '2030-01-12T10:00:00Z', collect_at: '2030-01-12T20:00:00Z', notes: 'Mlango wa nyuma',
  internal_notes: '', efd_receipt_no: '', date_changes_used: 0, balance_due_date: '2030-01-09', balance_due: 245000,
  subtotal: 160000, addons_total: 0, delivery_fee: 25000, empties_deposit: 60000, deposit_due: 122500,
  refund_due: null as number | null, refunded: 0,
  items: [{ name_sw: 'Soda', name_en: 'Soda pop', unit: 'kreti', qty: 10, unit_price: 16000, line_total: 160000 }],
  addons: [] as unknown[],
  payments: [PAYMENT] as (typeof PAYMENT)[],
  history: [
    { from_status: null, to_status: 'request', changed_by_name: null, note: '', created_at: '2030-01-01T09:00:00Z' },
    { from_status: 'request', to_status: 'request', changed_by_name: 'Amina', note: 'TZS 25000', created_at: '2030-01-01T09:30:00Z' },
  ],
  allowed_moves: [
    { to: 'quoted', allowed: true, reason: null, back: false },
    { to: 'confirmed', allowed: false, reason: 'deposit_not_paid', back: false },
  ],
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const t = (key: string, options?: Record<string, unknown>) => i18n.t(key, options as never) as unknown as string
const moveName = (stage: string) => t('admin.stage.moveTo', { stage: t(`status.${stage}`) })
const button = (name: string) => screen.getByRole('button', { name })

interface Call {
  method: string
  path: string
  body?: Record<string, unknown>
}

let detail: Record<string, unknown>
let role: string
let calls: Call[]
let actionResponse: (call: Call) => Response

const posts = () => calls.filter((call) => call.method !== 'GET')

beforeEach(() => {
  detail = DETAIL
  role = 'staff'
  calls = []
  actionResponse = () => json(200, detail)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace(/^\/api/, '')
      const call: Call = {
        method: init?.method ?? 'GET',
        path,
        body: init?.body ? JSON.parse(init.body as string) : undefined,
      }
      calls.push(call)
      if (path === '/admin/me') return json(200, { id: 'a', role, name: 'Amina' })
      if (path.endsWith('/cancel-preview')) return json(200, { days_ahead: 10, paid: 122500, refund_due: 61250 })
      if (call.method === 'GET') return json(200, detail)
      return actionResponse(call)
    }),
  )
})

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18n.changeLanguage('sw')
})

function renderDetail() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/admin/bookings/7']}>
        <Routes>
          <Route path="/admin/bookings/:id" element={<BookingDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function open() {
  renderDetail()
  await screen.findByRole('heading', { name: 'ED-2030-0007' })
}

describe('reading a booking', () => {
  it('shows the event, order, payments and history', async () => {
    await open()
    expect(screen.getByText('10 x Soda')).toBeInTheDocument()
    expect(screen.getByText('Mlango wa nyuma')).toBeInTheDocument()
    expect(screen.getByText('ABC123')).toBeInTheDocument()
    expect(screen.getByText(/TZS 25000/)).toBeInTheDocument()
    expect(screen.getByText(/Amina/)).toBeInTheDocument()
  })

  it('shows financials only when the response has them', async () => {
    await open()
    expect(screen.queryByText(t('admin.financials.profit'))).not.toBeInTheDocument()
  })

  it('shows the owner their figures', async () => {
    detail = { ...DETAIL, financials: { goods_total: 100000, revenue: 185000, profit: 85000 } }
    await open()
    expect(screen.getByText(t('admin.financials.profit'))).toBeInTheDocument()
    expect(screen.getByText('TSh 85,000')).toBeInTheDocument()
  })

  it('says when a booking does not exist', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(404, { detail: 'Booking not found' })))
    renderDetail()
    expect(await screen.findByText(t('admin.detail.notFound'))).toBeInTheDocument()
  })
})

describe('stage moves', () => {
  it('disables a refused move and gives the server reason in the current language', async () => {
    await open()
    expect(button(moveName('confirmed'))).toBeDisabled()
    expect(screen.getByText(t('admin.refusal.deposit_not_paid'))).toBeInTheDocument()

    await i18n.changeLanguage('en')
    expect(await screen.findByText("The deposit hasn't been confirmed yet.")).toBeInTheDocument()
  })

  it('moves when allowed and shows the booking the server returns', async () => {
    actionResponse = () => json(200, { ...DETAIL, status: 'quoted', allowed_moves: [] })
    await open()
    fireEvent.click(button(moveName('quoted')))
    expect(await screen.findByText(t('status.quoted'))).toBeInTheDocument()
    expect(posts()[0]).toMatchObject({ path: '/admin/bookings/7/stage', body: { to: 'quoted' } })
  })

  it('shows a refusal from the server and loads the booking again', async () => {
    actionResponse = () => json(409, { detail: { code: 'addons_unavailable' } })
    await open()
    const before = calls.filter((c) => c.method === 'GET' && c.path === '/admin/bookings/7').length
    fireEvent.click(button(moveName('quoted')))
    expect(await screen.findByText(t('admin.refusal.addons_unavailable'))).toBeInTheDocument()
    await waitFor(() =>
      expect(calls.filter((c) => c.method === 'GET' && c.path === '/admin/bookings/7').length).toBeGreaterThan(before),
    )
  })

  it('falls back to a general message for a code it does not know', async () => {
    actionResponse = () => json(409, { detail: { code: 'something_new' } })
    await open()
    fireEvent.click(button(moveName('quoted')))
    expect(await screen.findByText(t('admin.refusal.unknown'))).toBeInTheDocument()
  })

  it('asks for a note before moving back', async () => {
    detail = { ...DETAIL, status: 'confirmed', allowed_moves: [{ to: 'request', allowed: true, reason: null, back: true }] }
    await open()
    fireEvent.click(button(t('admin.stage.moveBack', { stage: t('status.request') })))
    expect(posts()).toHaveLength(0)
    fireEvent.change(screen.getByLabelText(t('admin.stage.backNote')), { target: { value: 'Malipo yalikosewa' } })
    fireEvent.click(button(t('admin.stage.backConfirm')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toMatchObject({ body: { to: 'request', note: 'Malipo yalikosewa' } })
  })
})

describe('payments', () => {
  it('confirm calls the API and shows who confirmed it', async () => {
    actionResponse = () =>
      json(200, {
        ...DETAIL,
        amount_paid: 122500,
        amount_pending: 0,
        payments: [{ ...PAYMENT, status: 'confirmed', confirmed_by_name: 'Juma', confirmed_at: '2030-01-02T10:00:00Z' }],
      })
    await open()
    fireEvent.click(button(t('admin.payments.confirm')))
    expect(await screen.findByText(/Juma/)).toBeInTheDocument()
    expect(posts()[0].path).toBe('/admin/payments/5/confirm')
  })

  it('reject takes a second step, because it cannot be undone', async () => {
    await open()
    fireEvent.click(button(t('admin.payments.reject')))
    expect(posts()).toHaveLength(0)
    fireEvent.click(button(t('admin.payments.rejectYes')))
    await waitFor(() => expect(posts()[0]?.path).toBe('/admin/payments/5/reject'))
  })

  it('offers no way to change a deposit on a cancelled booking', async () => {
    detail = { ...DETAIL, status: 'cancelled', refund_due: 61250, allowed_moves: [] }
    await open()
    expect(screen.queryByRole('button', { name: t('admin.payments.confirm') })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: t('admin.payments.reject') })).not.toBeInTheDocument()
  })

  it('lets a mistaken refund record be rejected on a cancelled booking', async () => {
    detail = {
      ...DETAIL,
      status: 'cancelled',
      refund_due: 61250,
      refunded: 61250,
      allowed_moves: [],
      payments: [{ ...PAYMENT, kind: 'refund', method: 'cash', status: 'confirmed', reference: '' }],
    }
    await open()
    expect(button(t('admin.payments.reject'))).toBeInTheDocument()
    expect(screen.getByText(new RegExp(`${t('payment.method.cash')}:`))).toBeInTheDocument()
  })
})

describe('cancelling', () => {
  it('shows the preview first and cancels only after the second step', async () => {
    await open()
    fireEvent.click(button(t('admin.cancel.open')))
    expect(await screen.findByText('TSh 61,250')).toBeInTheDocument()
    expect(posts()).toHaveLength(0)

    fireEvent.change(screen.getByLabelText(t('admin.cancel.note')), { target: { value: 'Mteja ameomba' } })
    fireEvent.click(button(t('admin.cancel.confirm')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toMatchObject({ path: '/admin/bookings/7/cancel', body: { note: 'Mteja ameomba' } })
  })

  it('can be backed out of', async () => {
    await open()
    fireEvent.click(button(t('admin.cancel.open')))
    await screen.findByText('TSh 61,250')
    fireEvent.click(button(t('admin.cancel.keep')))
    await waitFor(() => expect(screen.queryByText('TSh 61,250')).not.toBeInTheDocument())
    expect(posts()).toHaveLength(0)
  })

  it('is not offered on a finished booking', async () => {
    detail = { ...DETAIL, status: 'closed', allowed_moves: [] }
    await open()
    expect(screen.queryByRole('button', { name: t('admin.cancel.open') })).not.toBeInTheDocument()
  })
})

describe('refund records', () => {
  it('are offered only on a cancelled booking', async () => {
    await open()
    expect(screen.queryByLabelText(t('admin.refund.amount'))).not.toBeInTheDocument()
  })

  it('post the amount and method', async () => {
    detail = { ...DETAIL, status: 'cancelled', refund_due: 61250, allowed_moves: [] }
    actionResponse = () => json(201, detail)
    await open()
    fireEvent.change(screen.getByLabelText(t('admin.refund.amount')), { target: { value: '61250' } })
    fireEvent.change(screen.getByLabelText(t('admin.refund.method')), { target: { value: 'cash' } })
    fireEvent.click(button(t('admin.refund.submit')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toMatchObject({
      path: '/admin/bookings/7/refunds',
      body: { amount: 61250, method: 'cash', reference: '' },
    })
  })
})

describe('date change', () => {
  it('posts the new date for staff, who are not offered the exception', async () => {
    await open()
    await waitFor(() => expect(calls.some((c) => c.path === '/admin/me')).toBe(true))
    expect(screen.queryByLabelText(t('admin.date.exception'))).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(t('admin.date.newDate')), { target: { value: '2030-02-01' } })
    fireEvent.click(button(t('admin.date.submit')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toMatchObject({
      path: '/admin/bookings/7/date-change',
      body: { new_date: '2030-02-01', exception: false, note: '' },
    })
  })

  it('offers the owner the exception', async () => {
    role = 'owner'
    await open()
    fireEvent.click(await screen.findByLabelText(t('admin.date.exception')))
    fireEvent.change(screen.getByLabelText(t('admin.date.newDate')), { target: { value: '2030-02-01' } })
    fireEvent.change(screen.getByLabelText(t('admin.date.note')), { target: { value: 'Ombi maalum' } })
    fireEvent.click(button(t('admin.date.submit')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0].body).toMatchObject({ exception: true, note: 'Ombi maalum' })
  })
})

describe('rush and delivery fee', () => {
  const RUSH = { ...DETAIL, is_rush: true }

  it('approve posts straight away', async () => {
    detail = RUSH
    await open()
    fireEvent.click(button(t('admin.rush.approve')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toMatchObject({ path: '/admin/bookings/7/rush', body: { approve: true } })
  })

  it('decline says what is owed and needs a second step', async () => {
    detail = { ...RUSH, amount_paid: 122500 }
    await open()
    fireEvent.click(button(t('admin.rush.decline')))
    expect(posts()).toHaveLength(0)
    expect(screen.getByText(t('admin.rush.declineSure', { amount: 'TSh 122,500' }))).toBeInTheDocument()
    fireEvent.click(button(t('admin.rush.declineYes')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0].body).toMatchObject({ approve: false })
  })

  it('is not offered once approved or on an ordinary booking', async () => {
    detail = { ...RUSH, rush_approved: true }
    await open()
    expect(screen.queryByRole('button', { name: t('admin.rush.approve') })).not.toBeInTheDocument()
  })

  it('sets the delivery fee only while it is provisional', async () => {
    await open()
    expect(screen.queryByLabelText(t('admin.fee.label'))).not.toBeInTheDocument()
  })

  it('posts the delivery fee', async () => {
    detail = { ...DETAIL, provisional: true }
    await open()
    fireEvent.change(screen.getByLabelText(t('admin.fee.label')), { target: { value: '50000' } })
    fireEvent.click(button(t('admin.fee.submit')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toMatchObject({ path: '/admin/bookings/7/delivery-fee', body: { fee: 50000 } })
  })

  it('accepts a delivery fee of zero but not an empty one', async () => {
    detail = { ...DETAIL, provisional: true }
    await open()
    fireEvent.click(button(t('admin.fee.submit')))
    expect(posts()).toHaveLength(0)
    fireEvent.change(screen.getByLabelText(t('admin.fee.label')), { target: { value: '0' } })
    fireEvent.click(button(t('admin.fee.submit')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0].body).toMatchObject({ fee: 0 })
  })
})

describe('records', () => {
  it('saves the EFD number and internal notes', async () => {
    await open()
    fireEvent.change(screen.getByLabelText(t('admin.records.efd')), { target: { value: 'EFD-1' } })
    fireEvent.change(screen.getByLabelText(t('admin.records.internal')), { target: { value: 'Piga simu kwanza' } })
    fireEvent.click(button(t('admin.records.save')))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toMatchObject({
      method: 'PATCH',
      path: '/admin/bookings/7',
      body: { efd_receipt_no: 'EFD-1', internal_notes: 'Piga simu kwanza' },
    })
    expect(await screen.findByText(t('admin.records.saved'))).toBeInTheDocument()
  })
})

describe('refusal strings', () => {
  const CODES = [
    'invalid_move', 'deposit_not_paid', 'not_fully_paid', 'rush_not_approved', 'provisional', 'addons_unavailable',
    'owner_only', 'note_required', 'booking_finished', 'pending_payments', 'not_cancelled', 'refund_exceeds_due',
    'duplicate_reference', 'date_change_used', 'too_close_to_event', 'date_inside_notice', 'same_date', 'not_rush',
    'not_provisional', 'already_confirmed', 'already_rejected', 'payment_needed_by_stage',
  ]

  it.each(CODES)('%s is translated in both languages', (code) => {
    expect(i18n.exists(`admin.refusal.${code}`, { lng: 'sw', fallbackLng: [] })).toBe(true)
    expect(i18n.exists(`admin.refusal.${code}`, { lng: 'en', fallbackLng: [] })).toBe(true)
  })
})
