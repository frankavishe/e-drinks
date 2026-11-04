import { useQuery } from '@tanstack/react-query'
import type { Dispatch } from 'react'
import { useTranslation } from 'react-i18next'
import { formatTzs, getCatalog, getPackages, localName, type Quote } from '../../lib/publicApi'
import { AmountRow, Notice, Stepper } from './ui'
import { useQuote } from './useQuote'
import { quoteInput, type WizardAction, type WizardState } from './wizardState'

export function orderIsReady(quote: Quote | undefined): boolean {
  return (quote?.lines.length ?? 0) > 0
}

export default function OrderStep({
  state,
  dispatch,
}: {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: getCatalog })
  const packages = useQuery({ queryKey: ['packages'], queryFn: getPackages })
  const quote = useQuote(quoteInput(state, false))

  const isPackage = state.order_mode === 'package'
  const chosen = packages.data?.find((p) => p.id === state.package_id)
  const products = catalog.data ?? []
  const rows = isPackage
    ? products.filter((p) => chosen?.rules.some((rule) => rule.product_id === p.id))
    : products
  const lineFor = (id: number) => quote.data?.lines.find((line) => line.product_id === id)

  const modeClass = (active: boolean) =>
    `min-h-11 flex-1 rounded-md px-3 py-2 font-semibold ${
      active ? 'bg-emerald-700 text-white' : 'border border-stone-300 bg-white hover:bg-stone-100'
    }`

  return (
    <div className="space-y-5">
      <div className="flex gap-2">
        <button
          type="button"
          aria-pressed={isPackage}
          className={modeClass(isPackage)}
          onClick={() => dispatch({ type: 'set', fields: { order_mode: 'package' } })}
        >
          {t('book.order.modePackage')}
        </button>
        <button
          type="button"
          aria-pressed={!isPackage}
          className={modeClass(!isPackage)}
          onClick={() => dispatch({ type: 'set', fields: { order_mode: 'custom' } })}
        >
          {t('book.order.modeCustom')}
        </button>
      </div>

      {isPackage && (
        <fieldset className="space-y-2">
          <legend className="mb-2 font-medium">{t('book.order.choosePackage')}</legend>
          {packages.data?.map((pkg) => (
            <label
              key={pkg.id}
              className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 ${
                pkg.id === state.package_id ? 'border-emerald-700 bg-emerald-50' : 'border-stone-300 bg-white'
              }`}
            >
              <input
                type="radio"
                name="package"
                className="mt-1 size-4 accent-emerald-700"
                checked={pkg.id === state.package_id}
                onChange={() => dispatch({ type: 'set', fields: { package_id: pkg.id } })}
              />
              <span>
                <span className="block font-semibold">{localName(pkg, lang)}</span>
                <span className="block text-sm text-stone-600">
                  {lang === 'en' ? pkg.description_en : pkg.description_sw}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      )}

      {rows.length > 0 && (isPackage ? chosen : true) && (
        <section>
          <h3 className="font-medium">{isPackage ? t('book.order.adjust') : t('book.order.chooseDrinks')}</h3>
          <ul className="mt-2 divide-y divide-stone-200">
            {rows.map((product) => {
              const name = localName(product, lang)
              const line = lineFor(product.id)
              const packs = isPackage
                ? (state.overrides[product.id] ?? line?.packs ?? 0)
                : (state.items[product.id] ?? 0)
              return (
                <li key={product.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div className="min-w-40 flex-1">
                    <p className="font-medium">{name}</p>
                    <p className="text-sm text-stone-600">
                      {product.unit}
                      {line && `, ${formatTzs(line.unit_price)}`}
                    </p>
                  </div>
                  <Stepper
                    label={name}
                    value={packs}
                    onChange={(value) =>
                      dispatch({
                        type: isPackage ? 'setOverride' : 'setItem',
                        productId: product.id,
                        packs: value,
                      })
                    }
                  />
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {quote.isError && <Notice tone="problem">{t('book.quoteError')}</Notice>}
      {quote.data && !quote.isError && (
        <dl className="border-t-2 border-stone-900 pt-2">
          <AmountRow label={t('book.order.subtotal')} value={formatTzs(quote.data.subtotal)} strong />
        </dl>
      )}
    </div>
  )
}
