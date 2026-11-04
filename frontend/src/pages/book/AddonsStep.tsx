import { useQuery } from '@tanstack/react-query'
import type { Dispatch } from 'react'
import { useTranslation } from 'react-i18next'
import { formatTzs, getAddons, localName } from '../../lib/publicApi'
import { Stepper } from './ui'
import { useQuote } from './useQuote'
import { quoteInput, type WizardAction, type WizardState } from './wizardState'

export default function AddonsStep({
  state,
  dispatch,
}: {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}) {
  const { t, i18n } = useTranslation()
  const addons = useQuery({ queryKey: ['addons'], queryFn: getAddons })
  const quote = useQuote(quoteInput(state, true))

  return (
    <div>
      <p className="text-stone-700">{t('book.addons.lead')}</p>
      <ul className="mt-2 divide-y divide-stone-200">
        {addons.data?.map((addon) => {
          const name = localName(addon, i18n.language)
          const line = quote.data?.addon_lines.find((l) => l.addon_id === addon.id)
          return (
            <li key={addon.id} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-40 flex-1">
                  <p className="font-medium">{name}</p>
                  <p className="text-sm text-stone-600">{formatTzs(addon.price)}</p>
                </div>
                <Stepper
                  label={name}
                  value={state.addons[addon.id] ?? 0}
                  onChange={(qty) => dispatch({ type: 'setAddon', addonId: addon.id, qty })}
                />
              </div>
              {line && !line.ok && (
                <p role="alert" className="mt-1 text-sm font-medium text-red-800">
                  {t('book.addons.onlyAvailable', { count: line.available ?? 0 })}
                </p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
