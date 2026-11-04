import { cloneElement, useId, type ReactElement, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { PaymentInstructions } from '../../lib/publicApi'

// 16px text stops phones zooming in on focus; 44px height is a comfortable tap target.
export const inputClass =
  'block w-full min-h-11 rounded-md border border-stone-300 bg-white px-3 py-2 text-base ' +
  'focus:border-emerald-700 focus:outline-2 focus:outline-emerald-700 ' +
  'read-only:bg-stone-100 disabled:bg-stone-100'

export const primaryClass =
  'inline-flex min-h-11 items-center justify-center rounded-md bg-emerald-700 px-5 py-2 font-semibold text-white ' +
  'hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800 ' +
  'disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-600'

export const secondaryClass =
  'inline-flex min-h-11 items-center justify-center rounded-md border border-stone-300 bg-white px-5 py-2 font-semibold ' +
  'hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800'

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactElement<{ id?: string }>
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {cloneElement(children, { id })}
      {hint && <p className="mt-1 text-sm text-stone-600">{hint}</p>}
    </div>
  )
}

export function Stepper({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: number) => void
}) {
  const { t } = useTranslation()
  const buttonClass =
    'size-11 shrink-0 rounded-md border border-stone-300 bg-white text-xl leading-none hover:bg-stone-100 ' +
    'focus-visible:outline-2 focus-visible:outline-emerald-800'
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        className={buttonClass}
        aria-label={`${t('book.less')}: ${label}`}
        onClick={() => onChange(Math.max(0, value - 1))}
      >
        −
      </button>
      <input
        type="number"
        inputMode="numeric"
        min={0}
        aria-label={label}
        className="min-h-11 w-16 rounded-md border border-stone-300 bg-white px-1 text-center text-base"
        value={value}
        onChange={(e) => onChange(Math.max(0, Math.trunc(Number(e.target.value)) || 0))}
      />
      <button
        type="button"
        className={buttonClass}
        aria-label={`${t('book.more')}: ${label}`}
        onClick={() => onChange(value + 1)}
      >
        +
      </button>
    </div>
  )
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'problem'; children: ReactNode }) {
  const styles =
    tone === 'problem'
      ? 'border-red-700 bg-red-50 text-red-900'
      : 'border-emerald-700 bg-emerald-50 text-emerald-950'
  return (
    <p role={tone === 'problem' ? 'alert' : undefined} className={`border-l-4 px-3 py-2 text-sm ${styles}`}>
      {children}
    </p>
  )
}

export function AmountRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 py-1 ${strong ? 'text-lg font-bold' : ''}`}>
      <dt>{label}</dt>
      <dd className="text-right tabular-nums">{value}</dd>
    </div>
  )
}

export function PaymentDetails({ instructions }: { instructions: PaymentInstructions }) {
  const { t } = useTranslation()
  const rows = [
    ['M-Pesa', instructions.mpesa_till],
    ['Tigo Pesa', instructions.tigopesa_lipa],
    ['Airtel Money', instructions.airtel_lipa],
    [t('payment.bank'), instructions.bank_details],
  ].filter(([, value]) => value.trim() !== '')

  if (rows.length === 0) return <p className="text-sm text-stone-700">{t('payment.noDetails')}</p>
  return (
    <dl>
      {rows.map(([name, value]) => (
        <div key={name} className="flex justify-between gap-4 border-b border-stone-200 py-2 last:border-b-0">
          <dt className="text-stone-700">{name}</dt>
          <dd className="whitespace-pre-line text-right font-semibold tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  )
}
