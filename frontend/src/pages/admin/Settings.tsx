import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getSettings, putSettings, type SettingsMap } from '../../lib/adminApi'
import { Field, inputClass, Notice, primaryClass } from '../book/ui'
import { Panel } from './BookingActions'
import { LoadProblem, Refusal } from './BookingRows'
import { useCatalogAction, useIsOwner } from './useCatalogAction'

const SETTINGS_KEY = ['admin', 'settings']

const GROUPS = [
  ['business', ['business_name', 'tin', 'vrn', 'phone', 'email', 'notification_email', 'whatsapp_number']],
  ['rules', ['min_order', 'notice_days', 'notice_days_servers', 'deposit_percent', 'balance_due_days']],
  ['payment', ['mpesa_till', 'tigopesa_lipa', 'airtel_lipa', 'bank_details']],
  ['policy', ['policy_text_sw', 'policy_text_en']],
] as const

const NUMBERS: readonly string[] = GROUPS[1][1]
const LONG_TEXT: readonly string[] = ['bank_details', 'policy_text_sw', 'policy_text_en']

function SettingsForm({ saved, canEdit }: { saved: SettingsMap; canEdit: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [edits, setEdits] = useState<SettingsMap>({})
  const changes = Object.fromEntries(Object.entries(edits).filter(([key, value]) => value !== saved[key]))
  const dirty = Object.keys(changes).length > 0
  const save = useCatalogAction([SETTINGS_KEY], putSettings, (map) => {
    queryClient.setQueryData(SETTINGS_KEY, map)
    setEdits({})
  })

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate(changes)
      }}
    >
      {GROUPS.map(([group, keys]) => (
        <Panel key={group} title={t(`admin.settings.group.${group}`)}>
          {keys.map((key) => {
            const common = {
              className: inputClass,
              readOnly: !canEdit,
              value: edits[key] ?? saved[key] ?? '',
            }
            const change = (value: string) => setEdits((current) => ({ ...current, [key]: value }))
            return (
              <Field key={key} label={t(`admin.settings.field.${key}`)}>
                {LONG_TEXT.includes(key) ? (
                  <textarea {...common} rows={5} onChange={(e) => change(e.target.value)} />
                ) : (
                  <input
                    {...common}
                    inputMode={NUMBERS.includes(key) ? 'numeric' : undefined}
                    onChange={(e) => change(e.target.value)}
                  />
                )}
              </Field>
            )
          })}
        </Panel>
      ))}
      {canEdit && (
        <div className="space-y-2">
          <Refusal error={save.error} />
          {save.isSuccess && !dirty && <Notice>{t('admin.settings.saved')}</Notice>}
          <button type="submit" className={primaryClass} disabled={!dirty || save.isPending}>
            {t('admin.settings.save')}
          </button>
        </div>
      )}
    </form>
  )
}

export default function Settings() {
  const { t } = useTranslation()
  const canEdit = useIsOwner()
  const settings = useQuery({ queryKey: SETTINGS_KEY, queryFn: getSettings })

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t('admin.nav.settings')}</h1>
      {settings.isError ? (
        <LoadProblem error={settings.error} />
      ) : !settings.data ? (
        <p className="text-stone-700">{t('book.loading')}</p>
      ) : (
        <>
          {!canEdit && <p className="text-sm text-stone-700">{t('admin.settings.readOnly')}</p>}
          <SettingsForm saved={settings.data} canEdit={canEdit} />
        </>
      )}
    </div>
  )
}
