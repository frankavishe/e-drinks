import { useQuery } from '@tanstack/react-query'
import type { Dispatch } from 'react'
import { useTranslation } from 'react-i18next'
import { getAreas } from '../../lib/publicApi'
import { Field, inputClass, Notice } from './ui'
import { collectIsAfterSetup, type WizardAction, type WizardState } from './wizardState'

const EVENT_TYPES = ['wedding', 'corporate', 'birthday', 'other']
const OTHER_AREA = 'other'

function todayInDar(): string {
  return new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString().slice(0, 10)
}

export default function EventStep({
  state,
  dispatch,
}: {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}) {
  const { t } = useTranslation()
  const areas = useQuery({ queryKey: ['areas'], queryFn: getAreas })
  const set = (fields: Extract<WizardAction, { type: 'set' }>['fields']) =>
    dispatch({ type: 'set', fields })

  const allAreas = (areas.data?.zones.flatMap((zone) => zone.areas) ?? []).sort((a, b) =>
    a.name.localeCompare(b.name),
  )
  const savedVenue = state.venue_id !== null

  function chooseVenue(value: string) {
    const venue = areas.data?.venues.find((v) => v.id === Number(value)) ?? null
    dispatch({ type: 'chooseVenue', venue })
  }

  function chooseArea(value: string) {
    // A saved venue belongs to one area, so a different area means a different venue.
    dispatch({ type: 'chooseVenue', venue: null })
    if (value === OTHER_AREA) set({ unlisted_area: true, area_id: null })
    else set({ unlisted_area: false, custom_area: '', area_id: value ? Number(value) : null })
  }

  return (
    <div className="space-y-4">
      <Field label={t('book.event.type')}>
        <select
          className={inputClass}
          value={state.event_type}
          onChange={(e) => set({ event_type: e.target.value })}
        >
          {EVENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(`eventType.${type}`)}
            </option>
          ))}
        </select>
      </Field>

      <Field label={t('book.event.date')}>
        <input
          type="date"
          className={inputClass}
          min={todayInDar()}
          value={state.event_date}
          onChange={(e) => set({ event_date: e.target.value })}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label={t('book.event.startTime')}>
          <input
            type="time"
            className={inputClass}
            value={state.start_time}
            onChange={(e) => set({ start_time: e.target.value })}
          />
        </Field>
        <Field label={t('book.event.hours')}>
          <input
            type="number"
            inputMode="numeric"
            min={1}
            max={24}
            className={inputClass}
            value={state.hours || ''}
            onChange={(e) => set({ hours: Math.trunc(Number(e.target.value)) || 0 })}
          />
        </Field>
      </div>

      <Field label={t('book.event.guests')}>
        <input
          type="number"
          inputMode="numeric"
          min={1}
          className={inputClass}
          value={state.guests || ''}
          onChange={(e) => set({ guests: Math.trunc(Number(e.target.value)) || 0 })}
        />
      </Field>

      <Field label={t('book.event.venue')}>
        <select
          className={inputClass}
          value={state.venue_id ?? ''}
          onChange={(e) => chooseVenue(e.target.value)}
        >
          <option value="">{t('book.event.otherVenue')}</option>
          {areas.data?.venues.map((venue) => (
            <option key={venue.id} value={venue.id}>
              {venue.name}
            </option>
          ))}
        </select>
      </Field>

      {!savedVenue && (
        <Field label={t('book.event.venueName')}>
          <input
            className={inputClass}
            maxLength={160}
            value={state.venue_name}
            onChange={(e) => set({ venue_name: e.target.value })}
          />
        </Field>
      )}

      <Field label={t('book.event.area')}>
        <select
          className={inputClass}
          value={state.unlisted_area ? OTHER_AREA : (state.area_id ?? '')}
          onChange={(e) => chooseArea(e.target.value)}
        >
          <option value="">{t('book.event.chooseArea')}</option>
          {allAreas.map((area) => (
            <option key={area.id} value={area.id}>
              {area.name}
            </option>
          ))}
          <option value={OTHER_AREA}>{t('book.event.areaNotListed')}</option>
        </select>
      </Field>

      {state.unlisted_area && (
        <Field label={t('book.event.customArea')} hint={t('book.event.customAreaHint')}>
          <input
            className={inputClass}
            maxLength={120}
            value={state.custom_area}
            onChange={(e) => set({ custom_area: e.target.value })}
          />
        </Field>
      )}

      <Field label={t('book.event.venueAddress')}>
        <input
          className={inputClass}
          maxLength={255}
          readOnly={savedVenue}
          value={state.venue_address}
          onChange={(e) => set({ venue_address: e.target.value })}
        />
      </Field>

      <Field label={t('book.event.setupTime')} hint={t('book.event.setupHint')}>
        <input
          type="time"
          className={inputClass}
          value={state.setup_time}
          onChange={(e) => set({ setup_time: e.target.value })}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label={t('book.event.collectDay')}>
          <select
            className={inputClass}
            value={state.collect_day}
            onChange={(e) => set({ collect_day: e.target.value as WizardState['collect_day'] })}
          >
            <option value="same">{t('book.event.collectSame')}</option>
            <option value="next">{t('book.event.collectNext')}</option>
          </select>
        </Field>
        <Field label={t('book.event.collectTime')}>
          <input
            type="time"
            className={inputClass}
            value={state.collect_time}
            onChange={(e) => set({ collect_time: e.target.value })}
          />
        </Field>
      </div>

      {!collectIsAfterSetup(state) && <Notice tone="problem">{t('book.event.collectBeforeSetup')}</Notice>}
    </div>
  )
}
