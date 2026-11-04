import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../lib/api'
import { formatDate, formatTzs, localName, trackBooking, type TrackedBooking } from '../lib/publicApi'
import { AmountRow, Field, inputClass, Notice, PaymentDetails, primaryClass } from './book/ui'
import PaymentForm from './PaymentForm'

const FINISHED = ['cancelled', 'closed']

function errorKey(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) return 'track.notFound'
  if (error instanceof ApiError && error.status === 429) return 'track.tooMany'
  return 'track.failed'
}

function BookingDetails({ booking }: { booking: TrackedBooking }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const lines = [...booking.items, ...booking.addons]

  return (
    <>
      <div className="border-y-2 border-dashed border-stone-900 py-4">
        <p className="text-3xl font-bold tracking-tight tabular-nums text-emerald-900">{booking.code}</p>
        <p className="mt-1 text-sm text-stone-700">{t('track.status')}</p>
        <p className="text-lg font-semibold">{t(`status.${booking.status}`)}</p>
      </div>

      {booking.is_rush && <Notice>{t('track.rush')}</Notice>}
      {booking.provisional && <Notice>{t('track.provisional')}</Notice>}

      <section>
        <p className="font-semibold">
          {t(`eventType.${booking.event_type}`)}, {formatDate(booking.event_date, lang)}
        </p>
        <p className="text-sm text-stone-700">
          {t('track.guests', { count: booking.guests })}, {t('track.hours', { count: booking.hours })}
        </p>
        {booking.venue_name && <p className="text-sm text-stone-700">{booking.venue_name}</p>}
        {booking.venue_address && <p className="text-sm text-stone-700">{booking.venue_address}</p>}
      </section>

      <section>
        <h2 className="text-lg font-semibold">{t('track.order')}</h2>
        <ul className="mt-1 divide-y divide-stone-200 text-sm">
          {lines.map((line, index) => (
            <li key={index} className="flex justify-between gap-4 py-2">
              <span>
                {line.qty} x {localName(line, lang)}
              </span>
              <span className="tabular-nums">{formatTzs(line.line_total)}</span>
            </li>
          ))}
        </ul>
        <dl className="mt-2 border-t-2 border-stone-900 pt-2">
          <AmountRow
            label={t('totals.delivery')}
            value={booking.provisional ? t('totals.deliveryPending') : formatTzs(booking.delivery_fee)}
          />
          {booking.empties_deposit > 0 && (
            <AmountRow label={t('totals.empties')} value={formatTzs(booking.empties_deposit)} />
          )}
          <AmountRow label={t('totals.total')} value={formatTzs(booking.total)} strong />
          <AmountRow label={t('totals.deposit')} value={formatTzs(booking.deposit_due)} />
          <AmountRow label={t('totals.paid')} value={formatTzs(booking.amount_paid)} />
          {booking.amount_pending > 0 && (
            <AmountRow label={t('totals.pending')} value={formatTzs(booking.amount_pending)} />
          )}
          <AmountRow label={t('totals.balance')} value={formatTzs(booking.balance_due)} strong />
          <AmountRow label={t('totals.balanceDate')} value={formatDate(booking.balance_due_date, lang)} />
        </dl>
      </section>

      <section>
        <h2 className="text-lg font-semibold">{t('track.payments')}</h2>
        {booking.payments.length === 0 ? (
          <p className="mt-1 text-sm text-stone-700">{t('track.noPayments')}</p>
        ) : (
          <ul className="mt-1 divide-y divide-stone-200 text-sm">
            {booking.payments.map((payment) => (
              <li key={`${payment.reference}-${payment.created_at}`} className="py-2">
                <div className="flex justify-between gap-4">
                  <span className="font-medium">{payment.reference}</span>
                  <span className="tabular-nums">{formatTzs(payment.amount)}</span>
                </div>
                <p className="text-stone-700">
                  {t(`payment.kind.${payment.kind}`)}, {t(`payment.method.${payment.method}`)}:{' '}
                  {t(`payment.paymentStatus.${payment.status}`)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {!FINISHED.includes(booking.status) && (
        <section>
          <h2 className="text-lg font-semibold">{t('payment.howToPay')}</h2>
          <div className="mt-1">
            <PaymentDetails instructions={booking.payment_instructions} />
          </div>
        </section>
      )}
    </>
  )
}

export default function Track() {
  const { t } = useTranslation()
  const [code, setCode] = useState('')
  const [phone, setPhone] = useState('')
  const [booking, setBooking] = useState<TrackedBooking | null>(null)
  // The details that found this booking, so later edits to the form can't send a payment elsewhere.
  const [found, setFound] = useState<{ code: string; phone: string } | null>(null)

  const lookup = useMutation({
    mutationFn: (query: { code: string; phone: string }) => trackBooking(query.code, query.phone),
    onSuccess: (result, query) => {
      setBooking(result)
      setFound(query)
    },
    onError: () => setBooking(null),
  })

  return (
    <section className="mx-auto max-w-xl space-y-6 px-4 py-8">
      <h1 className="text-2xl font-bold">{t('track.title')}</h1>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          lookup.mutate({ code: code.trim().toUpperCase(), phone })
        }}
      >
        <p className="text-stone-700">{t('track.lead')}</p>
        <Field label={t('track.code')}>
          <input
            className={inputClass}
            autoCapitalize="characters"
            placeholder="ED-2026-0001"
            required
            maxLength={40}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </Field>
        <Field label={t('track.phone')}>
          <input
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            className={inputClass}
            required
            maxLength={40}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </Field>
        <button type="submit" className={`${primaryClass} w-full`} disabled={lookup.isPending}>
          {t('track.submit')}
        </button>
        {lookup.isError && <Notice tone="problem">{t(errorKey(lookup.error))}</Notice>}
      </form>

      {booking && found && (
        <>
          <BookingDetails booking={booking} />
          {!FINISHED.includes(booking.status) && (
            <PaymentForm
              key={booking.code}
              booking={booking}
              phone={found.phone}
              onPaid={() => lookup.mutate(found)}
            />
          )}
        </>
      )}
    </section>
  )
}
