import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../lib/api'
import { formatDateTime, getBooking, getMe, type BookingDetail as Booking, type HistoryEntry } from '../../lib/adminApi'
import { formatDate, formatTzs, localName } from '../../lib/publicApi'
import { AmountRow, Notice } from '../book/ui'
import {
  CancelPanel,
  DateChangePanel,
  DeliveryFeePanel,
  Panel,
  PaymentRow,
  RecordsPanel,
  RefundPanel,
  RushPanel,
  StagePanel,
} from './BookingActions'
import { Flag, LoadProblem } from './BookingRows'
import { bookingKey } from './useBookingAction'

const FINISHED = ['cancelled', 'closed']

function Summary({ booking }: { booking: Booking }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  return (
    <Panel title={t('admin.detail.event')}>
      <p className="font-semibold">
        {t(`eventType.${booking.event_type}`)}, {formatDate(booking.event_date, lang)}, {booking.start_time.slice(0, 5)}
      </p>
      <p className="text-sm text-stone-700">
        {t('track.guests', { count: booking.guests })}, {t('track.hours', { count: booking.hours })}
      </p>
      {booking.venue_name && <p className="text-sm">{booking.venue_name}</p>}
      {booking.venue_address && <p className="text-sm">{booking.venue_address}</p>}
      {booking.custom_area && <p className="text-sm">{booking.custom_area}</p>}
      <dl className="text-sm">
        <AmountRow label={t('admin.detail.setup')} value={formatDateTime(booking.setup_at, lang)} />
        <AmountRow label={t('admin.detail.collect')} value={formatDateTime(booking.collect_at, lang)} />
      </dl>
      <h3 className="font-semibold">{t('admin.detail.customer')}</h3>
      <p className="text-sm">{booking.customer_name}</p>
      <p className="text-sm">
        <a className="underline underline-offset-2" href={`tel:+${booking.customer_phone}`}>
          {booking.customer_phone}
        </a>
      </p>
      {booking.customer_email && <p className="text-sm">{booking.customer_email}</p>}
      {booking.notes && (
        <>
          <h3 className="font-semibold">{t('admin.detail.customerNotes')}</h3>
          <p className="whitespace-pre-line text-sm">{booking.notes}</p>
        </>
      )}
    </Panel>
  )
}

function Order({ booking }: { booking: Booking }) {
  const { t, i18n } = useTranslation()
  return (
    <Panel title={t('admin.detail.order')}>
      <ul className="divide-y divide-stone-200 text-sm">
        {[...booking.items, ...booking.addons].map((line, index) => (
          <li key={index} className="flex justify-between gap-4 py-2">
            <span>
              {line.qty} x {localName(line, i18n.language)}
            </span>
            <span className="tabular-nums">{formatTzs(line.line_total)}</span>
          </li>
        ))}
      </ul>
      <dl className="border-t-2 border-stone-900 pt-2">
        <AmountRow
          label={t('totals.delivery')}
          value={booking.provisional ? t('totals.deliveryPending') : formatTzs(booking.delivery_fee)}
        />
        {booking.empties_deposit > 0 && (
          <AmountRow label={t('totals.empties')} value={formatTzs(booking.empties_deposit)} />
        )}
        <AmountRow label={t('totals.total')} value={formatTzs(booking.total)} strong />
        <AmountRow label={t('admin.detail.deposit')} value={formatTzs(booking.deposit_due)} />
        <AmountRow label={t('totals.paid')} value={formatTzs(booking.amount_paid)} />
        {booking.amount_pending > 0 && (
          <AmountRow label={t('totals.pending')} value={formatTzs(booking.amount_pending)} />
        )}
        <AmountRow label={t('totals.balance')} value={formatTzs(booking.balance_due)} strong />
        {booking.balance_due_date && (
          <AmountRow label={t('totals.balanceDate')} value={formatDate(booking.balance_due_date, i18n.language)} />
        )}
        {booking.refund_due !== null && (
          <>
            <AmountRow label={t('admin.refundDue')} value={formatTzs(booking.refund_due)} strong />
            <AmountRow label={t('admin.refunded')} value={formatTzs(booking.refunded)} />
          </>
        )}
      </dl>
    </Panel>
  )
}

function HistoryRow({ entry }: { entry: HistoryEntry }) {
  const { t, i18n } = useTranslation()
  const moved = entry.from_status && entry.from_status !== entry.to_status
  return (
    <li className="py-2 text-sm">
      <p className="font-medium">
        {moved && `${t(`status.${entry.from_status}`)} → `}
        {t(`status.${entry.to_status}`)}
      </p>
      {entry.note && <p className="whitespace-pre-line">{entry.note}</p>}
      <p className="text-stone-700">
        {entry.changed_by_name ?? t('admin.detail.byCustomer')}, {formatDateTime(entry.created_at, i18n.language)}
      </p>
    </li>
  )
}

export default function BookingDetail() {
  const { t } = useTranslation()
  const bookingId = Number(useParams().id)
  const query = useQuery({
    queryKey: bookingKey(bookingId),
    queryFn: () => getBooking(bookingId),
    retry: false,
  })
  const me = useQuery({ queryKey: ['admin', 'me'], queryFn: getMe, retry: false })
  const booking = query.data

  if (!booking) {
    if (query.isPending) return <p className="text-stone-700">{t('book.loading')}</p>
    if (query.error instanceof ApiError && query.error.status === 404) {
      return <Notice tone="problem">{t('admin.detail.notFound')}</Notice>
    }
    return <LoadProblem error={query.error} />
  }

  const finished = FINISHED.includes(booking.status)

  return (
    <div className="space-y-4">
      <Link to="/admin/bookings" className="text-sm underline underline-offset-2">
        {t('admin.detail.allBookings')}
      </Link>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold tabular-nums text-emerald-900">{booking.code}</h1>
        <Flag tone="plain">{t(`status.${booking.status}`)}</Flag>
        {booking.is_rush && <Flag>{t(booking.rush_approved ? 'admin.flag.rushApproved' : 'admin.flag.rush')}</Flag>}
        {booking.provisional && <Flag>{t('admin.flag.provisional')}</Flag>}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <StagePanel booking={booking} />
          {booking.is_rush && !booking.rush_approved && !finished && <RushPanel booking={booking} />}
          {booking.provisional && !finished && <DeliveryFeePanel booking={booking} />}
          <Panel title={t('admin.payments.title')}>
            {booking.payments.length === 0 ? (
              <p className="text-sm text-stone-700">{t('admin.payments.none')}</p>
            ) : (
              <ul className="divide-y divide-stone-200">
                {booking.payments.map((payment) => (
                  <PaymentRow key={payment.id} booking={booking} payment={payment} finished={finished} />
                ))}
              </ul>
            )}
          </Panel>
          {booking.status === 'cancelled' && <RefundPanel booking={booking} />}
          <RecordsPanel booking={booking} />
          {!finished && <DateChangePanel booking={booking} isOwner={me.data?.role === 'owner'} />}
          {!finished && <CancelPanel booking={booking} />}
        </div>
        <div className="space-y-4">
          <Summary booking={booking} />
          <Order booking={booking} />
          {booking.financials && (
            <Panel title={t('admin.financials.title')}>
              <dl>
                <AmountRow label={t('admin.financials.goods')} value={formatTzs(booking.financials.goods_total)} />
                <AmountRow label={t('admin.financials.revenue')} value={formatTzs(booking.financials.revenue)} />
                <AmountRow label={t('admin.financials.profit')} value={formatTzs(booking.financials.profit)} strong />
              </dl>
            </Panel>
          )}
          <Panel title={t('admin.detail.history')}>
            <ul className="divide-y divide-stone-200">
              {booking.history.map((entry, index) => (
                <HistoryRow key={index} entry={entry} />
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  )
}
