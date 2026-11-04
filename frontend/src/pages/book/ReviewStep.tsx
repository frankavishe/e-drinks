import { useTranslation } from 'react-i18next'
import { formatDate, formatTzs, localName, type Quote } from '../../lib/publicApi'
import { AmountRow, Notice } from './ui'
import type { ConflictCode } from './wizardState'

export function reviewIsBookable(quote: Quote | undefined): boolean {
  return (
    !!quote &&
    quote.lines.length > 0 &&
    !quote.flags.below_minimum &&
    quote.flags.addons_unavailable.length === 0
  )
}

export default function ReviewStep({
  quote,
  failed,
  conflict,
}: {
  quote: Quote | undefined
  failed: boolean
  conflict: ConflictCode | null
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language

  if (failed) return <Notice tone="problem">{t('book.quoteError')}</Notice>
  if (!quote) return <p className="text-stone-600">{t('book.loading')}</p>

  const { flags } = quote
  return (
    <div className="space-y-4">
      {conflict && <Notice tone="problem">{t(`book.conflict.${conflict}`)}</Notice>}

      <table className="w-full text-left text-sm">
        <thead className="border-b-2 border-stone-900">
          <tr>
            <th scope="col" className="py-2 font-semibold">{t('book.review.item')}</th>
            <th scope="col" className="py-2 text-right font-semibold">{t('book.review.qty')}</th>
            <th scope="col" className="py-2 text-right font-semibold">{t('book.review.amount')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-200">
          {quote.lines.map((line) => (
            <tr key={line.product_id}>
              <td className="py-2 pr-2">
                {localName(line, lang)}
                <span className="block text-stone-600">{line.unit}</span>
              </td>
              <td className="py-2 text-right tabular-nums">{line.packs}</td>
              <td className="py-2 pl-2 text-right tabular-nums">{formatTzs(line.line_total)}</td>
            </tr>
          ))}
          {quote.addon_lines.map((line) => (
            <tr key={line.addon_id}>
              <td className="py-2 pr-2">
                {localName(line, lang)}
                {!line.ok && (
                  <span className="block font-medium text-red-800">
                    {t('book.addons.onlyAvailable', { count: line.available ?? 0 })}
                  </span>
                )}
              </td>
              <td className="py-2 text-right tabular-nums">{line.qty}</td>
              <td className="py-2 pl-2 text-right tabular-nums">{formatTzs(line.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <dl className="border-t-2 border-stone-900 pt-2">
        <AmountRow label={t('totals.drinks')} value={formatTzs(quote.subtotal)} />
        {quote.addons_total > 0 && <AmountRow label={t('totals.addons')} value={formatTzs(quote.addons_total)} />}
        <AmountRow
          label={t('totals.delivery')}
          value={quote.delivery_custom ? t('totals.deliveryPending') : formatTzs(quote.delivery_fee)}
        />
        {quote.empties_deposit > 0 && (
          <AmountRow label={t('totals.empties')} value={formatTzs(quote.empties_deposit)} />
        )}
        <AmountRow label={t('totals.total')} value={formatTzs(quote.total)} strong />
        <AmountRow label={t('totals.deposit')} value={formatTzs(quote.deposit_due)} />
        <AmountRow label={t('totals.balanceDate')} value={formatDate(quote.balance_due_date, lang)} />
      </dl>

      {flags.below_minimum && (
        <Notice tone="problem">{t('book.review.belowMinimum', { amount: formatTzs(flags.min_order) })}</Notice>
      )}
      {flags.addons_unavailable.length > 0 && <Notice tone="problem">{t('book.review.addonsShort')}</Notice>}
      {flags.is_rush && <Notice>{t('book.review.rush')}</Notice>}
      {flags.provisional && <Notice>{t('book.review.provisional')}</Notice>}
    </div>
  )
}
