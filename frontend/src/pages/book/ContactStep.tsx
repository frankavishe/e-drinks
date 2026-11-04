import { useQuery } from '@tanstack/react-query'
import type { Dispatch } from 'react'
import { useTranslation } from 'react-i18next'
import { getSettings } from '../../lib/publicApi'
import { Field, inputClass } from './ui'
import type { WizardAction, WizardState } from './wizardState'

export function contactIsComplete(state: WizardState): boolean {
  return (
    state.name.trim() !== '' && state.phone.trim() !== '' && state.accept_policy && state.age_confirmed
  )
}

export default function ContactStep({
  state,
  dispatch,
}: {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}) {
  const { t, i18n } = useTranslation()
  const settings = useQuery({ queryKey: ['settings'], queryFn: getSettings })
  const set = (fields: Extract<WizardAction, { type: 'set' }>['fields']) =>
    dispatch({ type: 'set', fields })
  const policy = i18n.language === 'en' ? settings.data?.policy_text_en : settings.data?.policy_text_sw

  const checkClass = 'mt-1 size-5 shrink-0 accent-emerald-700'
  return (
    <div className="space-y-4">
      <Field label={t('book.contact.name')}>
        <input
          className={inputClass}
          autoComplete="name"
          maxLength={120}
          value={state.name}
          onChange={(e) => set({ name: e.target.value })}
        />
      </Field>
      <Field label={t('book.contact.phone')} hint={t('book.contact.phoneHint')}>
        <input
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          className={inputClass}
          value={state.phone}
          onChange={(e) => set({ phone: e.target.value })}
        />
      </Field>
      <Field label={t('book.contact.email')}>
        <input
          type="email"
          autoComplete="email"
          className={inputClass}
          maxLength={200}
          value={state.email}
          onChange={(e) => set({ email: e.target.value })}
        />
      </Field>
      <Field label={t('book.contact.notes')}>
        <textarea
          className={inputClass}
          rows={3}
          maxLength={1000}
          value={state.notes}
          onChange={(e) => set({ notes: e.target.value })}
        />
      </Field>

      <section className="border-l-4 border-stone-400 pl-3">
        <h3 className="font-medium">{t('book.contact.policyTitle')}</h3>
        <p className="mt-1 text-sm text-stone-700">{policy}</p>
      </section>

      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          className={checkClass}
          checked={state.accept_policy}
          onChange={(e) => set({ accept_policy: e.target.checked })}
        />
        <span>{t('book.contact.acceptPolicy')}</span>
      </label>
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          className={checkClass}
          checked={state.age_confirmed}
          onChange={(e) => set({ age_confirmed: e.target.checked })}
        />
        <span>{t('book.contact.ageConfirmed')}</span>
      </label>
    </div>
  )
}
