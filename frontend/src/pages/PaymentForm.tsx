import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../lib/api'
import { submitPayment, type TrackedBooking } from '../lib/publicApi'
import { Field, inputClass, Notice, primaryClass } from './book/ui'

const METHODS = ['mpesa', 'tigopesa', 'airtel', 'bank']

function errorKey(error: unknown): string {
  if (error instanceof ApiError && error.code === 'duplicate_reference') return 'pay.duplicate'
  if (error instanceof ApiError && error.code === 'booking_closed') return 'pay.closed'
  if (error instanceof ApiError && error.status === 422) return 'pay.invalid'
  if (error instanceof ApiError && error.status === 429) return 'track.tooMany'
  return 'pay.failed'
}

export default function PaymentForm({
  booking,
  phone,
  onPaid,
}: {
  booking: TrackedBooking
  phone: string
  onPaid: () => void
}) {
  const { t } = useTranslation()
  const amountFor = (kind: string) => (kind === 'deposit' ? booking.deposit_due : booking.balance_due)
  const depositCovered = booking.amount_paid + booking.amount_pending >= booking.deposit_due
  const [kind, setKind] = useState(depositCovered ? 'balance' : 'deposit')
  const [method, setMethod] = useState('mpesa')
  const [amount, setAmount] = useState(String(amountFor(depositCovered ? 'balance' : 'deposit')))
  const [reference, setReference] = useState('')

  const send = useMutation({
    mutationFn: () =>
      submitPayment(booking.code, { phone, kind, method, amount: Number(amount), reference }),
    onSuccess: () => {
      setReference('')
      onPaid()
    },
  })

  const canSend = Number(amount) >= 1 && reference.trim() !== '' && !send.isPending

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (canSend) send.mutate()
      }}
    >
      <h2 className="text-lg font-semibold">{t('pay.title')}</h2>
      <p className="text-sm text-stone-700">{t('pay.lead')}</p>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('pay.kind')}>
          <select
            className={inputClass}
            value={kind}
            onChange={(e) => {
              setKind(e.target.value)
              setAmount(String(amountFor(e.target.value)))
            }}
          >
            <option value="deposit">{t('payment.kind.deposit')}</option>
            <option value="balance">{t('payment.kind.balance')}</option>
          </select>
        </Field>
        <Field label={t('pay.method')}>
          <select className={inputClass} value={method} onChange={(e) => setMethod(e.target.value)}>
            {METHODS.map((m) => (
              <option key={m} value={m}>
                {t(`payment.method.${m}`)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label={t('pay.amount')}>
        <input
          type="number"
          inputMode="numeric"
          min={1}
          className={inputClass}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </Field>
      <Field label={t('pay.reference')}>
        <input
          className={inputClass}
          maxLength={80}
          autoCapitalize="characters"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
        />
      </Field>
      {send.isError && <Notice tone="problem">{t(errorKey(send.error))}</Notice>}
      {send.isSuccess && <Notice>{t('pay.sent')}</Notice>}
      <button type="submit" className={`${primaryClass} w-full`} disabled={!canSend}>
        {t('pay.submit')}
      </button>
    </form>
  )
}
