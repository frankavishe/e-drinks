import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { formatDate, formatTzs, whatsappLink, type BookingCreated } from '../../lib/publicApi'
import { AmountRow, Notice, PaymentDetails, primaryClass, secondaryClass } from './ui'

export default function Confirmation({ booking }: { booking: BookingCreated }) {
  const { t, i18n } = useTranslation()
  const message = t('book.confirm.whatsappMessage', { code: booking.code })

  return (
    <div className="space-y-6">
      <div className="border-y-2 border-dashed border-stone-900 py-6 text-center">
        <h2 className="text-lg font-semibold">{t('book.confirm.title')}</h2>
        <p className="mt-2 text-sm text-stone-700">{t('book.confirm.keepNumber')}</p>
        <p className="mt-3 text-4xl font-bold tracking-tight tabular-nums text-emerald-900 sm:text-5xl">
          {booking.code}
        </p>
      </div>

      {booking.is_rush && <Notice>{t('book.confirm.rush')}</Notice>}
      {booking.provisional && <Notice>{t('book.confirm.provisional')}</Notice>}

      <dl>
        <AmountRow label={t('totals.total')} value={formatTzs(booking.total)} strong />
        <AmountRow label={t('totals.deposit')} value={formatTzs(booking.deposit_due)} />
        <AmountRow
          label={t('totals.balanceDate')}
          value={formatDate(booking.balance_due_date, i18n.language)}
        />
      </dl>

      <section>
        <h3 className="font-semibold">{t('payment.howToPay')}</h3>
        <p className="mb-2 text-sm text-stone-700">{t('book.confirm.payLead')}</p>
        <PaymentDetails instructions={booking.payment_instructions} />
      </section>

      <div className="flex flex-col gap-3">
        <a
          className={primaryClass}
          href={whatsappLink(booking.whatsapp_number, message)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t('book.confirm.whatsapp')}
        </a>
        <Link className={secondaryClass} to="/track">
          {t('book.confirm.track')}
        </Link>
      </div>
    </div>
  )
}
