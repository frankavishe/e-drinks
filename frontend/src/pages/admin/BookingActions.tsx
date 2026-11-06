import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  addRefund,
  cancelBooking,
  changeDate,
  confirmPayment,
  decideRush,
  formatDateTime,
  getCancelPreview,
  moveStage,
  patchBooking,
  rejectPayment,
  setDeliveryFee,
  type AdminPayment,
  type BookingDetail,
  type Move,
} from '../../lib/adminApi'
import { formatTzs } from '../../lib/publicApi'
import { AmountRow, Field, inputClass, Notice, primaryClass, secondaryClass } from '../book/ui'
import { Refusal } from './BookingRows'
import { useBookingAction } from './useBookingAction'

const REFUND_METHODS = ['mpesa', 'tigopesa', 'airtel', 'bank', 'cash']

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 rounded-md border border-stone-200 bg-white p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function StageMove({ booking, move }: { booking: BookingDetail; move: Move }) {
  const { t } = useTranslation()
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState('')
  const go = useBookingAction<string>(booking.id, (text) => moveStage(booking.id, move.to, text), () => setAsking(false))
  const stage = t(`status.${move.to}`)
  const label = t(move.back ? 'admin.stage.moveBack' : 'admin.stage.moveTo', { stage })

  return (
    <div className="space-y-2">
      {!asking && (
        <button
          type="button"
          className={move.back ? secondaryClass : primaryClass}
          disabled={!move.allowed || go.isPending}
          onClick={() => (move.back ? setAsking(true) : go.mutate(''))}
        >
          {label}
        </button>
      )}
      {!move.allowed && move.reason && (
        <p className="text-sm text-stone-700">{t([`admin.refusal.${move.reason}`, 'admin.refusal.unknown'])}</p>
      )}
      {asking && (
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault()
            go.mutate(note)
          }}
        >
          <Field label={t('admin.stage.backNote')}>
            <input className={inputClass} required maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={primaryClass} disabled={go.isPending}>
              {t('admin.stage.backConfirm')}
            </button>
            <button type="button" className={secondaryClass} onClick={() => setAsking(false)}>
              {t('admin.keep')}
            </button>
          </div>
        </form>
      )}
      <Refusal error={go.error} />
    </div>
  )
}

export function StagePanel({ booking }: { booking: BookingDetail }) {
  const { t } = useTranslation()
  if (booking.allowed_moves.length === 0) return null
  return (
    <Panel title={t('admin.stage.title')}>
      <div className="space-y-3">
        {booking.allowed_moves.map((move) => (
          <StageMove key={move.to} booking={booking} move={move} />
        ))}
      </div>
    </Panel>
  )
}

export function PaymentRow({
  booking,
  payment,
  finished,
}: {
  booking: BookingDetail
  payment: AdminPayment
  finished: boolean
}) {
  const { t, i18n } = useTranslation()
  const [asking, setAsking] = useState(false)
  const confirm = useBookingAction(booking.id, () => confirmPayment(payment.id))
  const reject = useBookingAction(booking.id, () => rejectPayment(payment.id), () => setAsking(false))
  // Deposits and balances on a finished booking are frozen: the refund was worked out from them.
  const canDecide = !finished || payment.kind === 'refund'
  const busy = confirm.isPending || reject.isPending

  return (
    <li className="space-y-2 py-3">
      <div className="flex justify-between gap-4">
        <span className="font-medium">{payment.reference || t(`payment.kind.${payment.kind}`)}</span>
        <span className="tabular-nums">{formatTzs(payment.amount)}</span>
      </div>
      <p className="text-sm text-stone-700">
        {t(`payment.kind.${payment.kind}`)}, {t(`payment.method.${payment.method}`)}:{' '}
        {t(`payment.paymentStatus.${payment.status}`)}
      </p>
      {payment.confirmed_by_name && payment.confirmed_at && (
        <p className="text-sm text-stone-700">
          {payment.confirmed_by_name}, {formatDateTime(payment.confirmed_at, i18n.language)}
        </p>
      )}
      {canDecide && !asking && (
        <div className="flex flex-wrap gap-2">
          {payment.status === 'pending' && (
            <button type="button" className={primaryClass} disabled={busy} onClick={() => confirm.mutate()}>
              {t('admin.payments.confirm')}
            </button>
          )}
          {payment.status !== 'rejected' && (
            <button type="button" className={secondaryClass} disabled={busy} onClick={() => setAsking(true)}>
              {t('admin.payments.reject')}
            </button>
          )}
        </div>
      )}
      {asking && (
        <div className="space-y-2">
          <Notice>{t('admin.payments.rejectSure')}</Notice>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primaryClass} disabled={busy} onClick={() => reject.mutate()}>
              {t('admin.payments.rejectYes')}
            </button>
            <button type="button" className={secondaryClass} onClick={() => setAsking(false)}>
              {t('admin.keep')}
            </button>
          </div>
        </div>
      )}
      <Refusal error={confirm.error ?? reject.error} />
    </li>
  )
}

export function CancelPanel({ booking }: { booking: BookingDetail }) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  // A mutation, not a cached query: what's owed depends on today and on the money received so far.
  const preview = useMutation({ mutationFn: () => getCancelPreview(booking.id) })
  const cancel = useBookingAction(booking.id, () => cancelBooking(booking.id, note))

  return (
    <Panel title={t('admin.cancel.title')}>
      {!preview.data ? (
        <button type="button" className={secondaryClass} disabled={preview.isPending} onClick={() => preview.mutate()}>
          {t('admin.cancel.open')}
        </button>
      ) : (
        <div className="space-y-3">
          <dl>
            <AmountRow label={t('admin.cancel.daysAhead')} value={String(preview.data.days_ahead)} />
            <AmountRow label={t('totals.paid')} value={formatTzs(preview.data.paid)} />
            <AmountRow label={t('admin.refundDue')} value={formatTzs(preview.data.refund_due)} strong />
          </dl>
          <Field label={t('admin.cancel.note')}>
            <input className={inputClass} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primaryClass} disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              {t('admin.cancel.confirm')}
            </button>
            <button type="button" className={secondaryClass} onClick={() => preview.reset()}>
              {t('admin.cancel.keep')}
            </button>
          </div>
        </div>
      )}
      <Refusal error={preview.error ?? cancel.error} />
    </Panel>
  )
}

export function RefundPanel({ booking }: { booking: BookingDetail }) {
  const { t } = useTranslation()
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('mpesa')
  const [reference, setReference] = useState('')
  const add = useBookingAction(
    booking.id,
    () => addRefund(booking.id, { amount: Number(amount), method, reference }),
    () => {
      setAmount('')
      setReference('')
    },
  )

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    add.mutate()
  }

  return (
    <Panel title={t('admin.refund.title')}>
      <form className="space-y-3" onSubmit={onSubmit}>
        <Field label={t('admin.refund.amount')}>
          <input
            type="number"
            inputMode="numeric"
            min={1}
            step={1}
            required
            className={inputClass}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
        <Field label={t('admin.refund.method')}>
          <select className={inputClass} value={method} onChange={(e) => setMethod(e.target.value)}>
            {REFUND_METHODS.map((name) => (
              <option key={name} value={name}>
                {t(`payment.method.${name}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('admin.refund.reference')}>
          <input className={inputClass} maxLength={80} value={reference} onChange={(e) => setReference(e.target.value)} />
        </Field>
        <button type="submit" className={primaryClass} disabled={add.isPending}>
          {t('admin.refund.submit')}
        </button>
        <Refusal error={add.error} />
      </form>
    </Panel>
  )
}

export function DateChangePanel({ booking, isOwner }: { booking: BookingDetail; isOwner: boolean }) {
  const { t } = useTranslation()
  const [newDate, setNewDate] = useState('')
  const [exception, setException] = useState(false)
  const [note, setNote] = useState('')
  const change = useBookingAction(
    booking.id,
    () => changeDate(booking.id, { new_date: newDate, exception, note }),
    () => {
      setNewDate('')
      setException(false)
      setNote('')
    },
  )

  return (
    <Panel title={t('admin.date.title')}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          change.mutate()
        }}
      >
        <p className="text-sm text-stone-700">{t('admin.date.used', { count: booking.date_changes_used })}</p>
        <Field label={t('admin.date.newDate')}>
          <input type="date" required className={inputClass} value={newDate} onChange={(e) => setNewDate(e.target.value)} />
        </Field>
        <Field label={t('admin.date.note')}>
          <input className={inputClass} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        {isOwner && (
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              className="size-5"
              checked={exception}
              onChange={(e) => setException(e.target.checked)}
            />
            {t('admin.date.exception')}
          </label>
        )}
        <button type="submit" className={primaryClass} disabled={change.isPending}>
          {t('admin.date.submit')}
        </button>
        <Refusal error={change.error} />
      </form>
    </Panel>
  )
}

export function RushPanel({ booking }: { booking: BookingDetail }) {
  const { t } = useTranslation()
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState('')
  const decide = useBookingAction<boolean>(booking.id, (approve) => decideRush(booking.id, approve, note))

  return (
    <Panel title={t('admin.rush.title')}>
      <Field label={t('admin.rush.note')}>
        <input className={inputClass} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {asking ? (
        <div className="space-y-2">
          <Notice>{t('admin.rush.declineSure', { amount: formatTzs(booking.amount_paid) })}</Notice>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primaryClass} disabled={decide.isPending} onClick={() => decide.mutate(false)}>
              {t('admin.rush.declineYes')}
            </button>
            <button type="button" className={secondaryClass} onClick={() => setAsking(false)}>
              {t('admin.keep')}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button type="button" className={primaryClass} disabled={decide.isPending} onClick={() => decide.mutate(true)}>
            {t('admin.rush.approve')}
          </button>
          <button type="button" className={secondaryClass} onClick={() => setAsking(true)}>
            {t('admin.rush.decline')}
          </button>
        </div>
      )}
      <Refusal error={decide.error} />
    </Panel>
  )
}

export function DeliveryFeePanel({ booking }: { booking: BookingDetail }) {
  const { t } = useTranslation()
  const [fee, setFee] = useState('')
  const save = useBookingAction(booking.id, () => setDeliveryFee(booking.id, Number(fee)))

  return (
    <Panel title={t('admin.fee.title')}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate()
        }}
      >
        <Field label={t('admin.fee.label')} hint={booking.custom_area || undefined}>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            step={1}
            required
            className={inputClass}
            value={fee}
            onChange={(e) => setFee(e.target.value)}
          />
        </Field>
        <button type="submit" className={primaryClass} disabled={save.isPending}>
          {t('admin.fee.submit')}
        </button>
        <Refusal error={save.error} />
      </form>
    </Panel>
  )
}

export function RecordsPanel({ booking }: { booking: BookingDetail }) {
  const { t } = useTranslation()
  const [efd, setEfd] = useState(booking.efd_receipt_no)
  const [internal, setInternal] = useState(booking.internal_notes)
  const save = useBookingAction(
    booking.id,
    () => patchBooking(booking.id, { efd_receipt_no: efd, internal_notes: internal }),
    (detail) => {
      setEfd(detail.efd_receipt_no)
      setInternal(detail.internal_notes)
    },
  )

  return (
    <Panel title={t('admin.records.title')}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate()
        }}
      >
        <Field label={t('admin.records.efd')}>
          <input className={inputClass} maxLength={60} value={efd} onChange={(e) => setEfd(e.target.value)} />
        </Field>
        <Field label={t('admin.records.internal')} hint={t('admin.records.internalHint')}>
          <textarea
            className={inputClass}
            rows={3}
            maxLength={5000}
            value={internal}
            onChange={(e) => setInternal(e.target.value)}
          />
        </Field>
        <button type="submit" className={primaryClass} disabled={save.isPending}>
          {t('admin.records.save')}
        </button>
        {save.isSuccess && <Notice>{t('admin.records.saved')}</Notice>}
        <Refusal error={save.error} />
      </form>
    </Panel>
  )
}
