import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  createArea,
  createVenue,
  createZone,
  deleteArea,
  deleteVenue,
  deleteZone,
  getVenues,
  getZones,
  patchArea,
  patchVenue,
  patchZone,
  type AdminArea,
  type AdminVenue,
  type AdminZone,
  type VenueFields,
  type ZoneFields,
} from '../../lib/adminApi'
import { formatTzs } from '../../lib/publicApi'
import { Field, inputClass } from '../book/ui'
import { Panel } from './BookingActions'
import { LoadProblem, Refusal } from './BookingRows'
import { FormButtons, RecordRow } from './CatalogParts'
import { useCatalogAction, useIsOwner } from './useCatalogAction'

const KEYS = [
  ['admin', 'zones'],
  ['admin', 'venues'],
]

function submit(e: FormEvent, go: () => void) {
  e.preventDefault()
  go()
}

function ZoneForm({
  label,
  buttonLabel,
  zone,
  save,
  onDone,
  onCancel,
}: {
  label: string
  buttonLabel: string
  zone?: AdminZone
  save: (fields: ZoneFields) => Promise<unknown>
  onDone: () => void
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  const [name, setName] = useState(zone?.name ?? '')
  const [fee, setFee] = useState(zone ? String(zone.delivery_fee) : '')
  const action = useCatalogAction(KEYS, save, onDone)
  return (
    <form
      aria-label={label}
      className="space-y-3"
      onSubmit={(e) => submit(e, () => action.mutate({ name, delivery_fee: Number(fee) }))}
    >
      <Field label={t('admin.zones.zoneName')}>
        <input className={inputClass} required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label={t('admin.zones.fee')}>
        <input
          className={inputClass}
          type="number"
          inputMode="numeric"
          required
          min={0}
          step={1}
          value={fee}
          onChange={(e) => setFee(e.target.value)}
        />
      </Field>
      <Refusal error={action.error} />
      <FormButtons label={buttonLabel} pending={action.isPending} onCancel={onCancel} />
    </form>
  )
}

function AreaEdit({ area, zones, onClose }: { area: AdminArea; zones: AdminZone[]; onClose: () => void }) {
  const { t } = useTranslation()
  const [name, setName] = useState(area.name)
  const [zoneId, setZoneId] = useState(String(area.zone_id))
  const action = useCatalogAction(KEYS, () => patchArea(area.id, { name, zone_id: Number(zoneId) }), onClose)
  return (
    <form
      aria-label={`${t('admin.manage.edit')}: ${area.name}`}
      className="space-y-3"
      onSubmit={(e) => submit(e, () => action.mutate())}
    >
      <Field label={t('admin.zones.areaName')}>
        <input className={inputClass} required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label={t('admin.zones.zone')}>
        <select className={inputClass} value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
          {zones.map((zone) => (
            <option key={zone.id} value={zone.id}>
              {zone.name}
            </option>
          ))}
        </select>
      </Field>
      <Refusal error={action.error} />
      <FormButtons label={t('admin.manage.save')} pending={action.isPending} onCancel={onClose} />
    </form>
  )
}

function AddArea({ zone }: { zone: AdminZone }) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const action = useCatalogAction(KEYS, () => createArea({ name, zone_id: zone.id }), () => setName(''))
  return (
    <form
      aria-label={t('admin.zones.addArea')}
      className="space-y-3"
      onSubmit={(e) => submit(e, () => action.mutate())}
    >
      <Field label={t('admin.zones.areaName')}>
        <input className={inputClass} required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Refusal error={action.error} />
      <FormButtons label={t('admin.zones.addArea')} pending={action.isPending} />
    </form>
  )
}

function ZonePanel({ zone, zones, canEdit }: { zone: AdminZone; zones: AdminZone[]; canEdit: boolean }) {
  const { t } = useTranslation()
  return (
    <section className="space-y-3 rounded-md border border-stone-200 bg-white p-4">
      <RecordRow
        name={zone.name}
        canEdit={canEdit}
        queryKeys={KEYS}
        deleteAction={() => deleteZone(zone.id)}
        renderForm={(close) => (
          <ZoneForm
            label={`${t('admin.manage.edit')}: ${zone.name}`}
            buttonLabel={t('admin.manage.save')}
            zone={zone}
            save={(fields) => patchZone(zone.id, fields)}
            onDone={close}
            onCancel={close}
          />
        )}
      >
        <h3 className="font-semibold">{zone.name}</h3>
        <p className="text-sm tabular-nums">{formatTzs(zone.delivery_fee)}</p>
      </RecordRow>

      <h4 className="text-sm font-semibold text-stone-700">{t('admin.zones.areas')}</h4>
      {zone.areas.length === 0 ? (
        <p className="text-sm text-stone-700">{t('admin.zones.noAreas')}</p>
      ) : (
        <ul className="divide-y divide-stone-200">
          {zone.areas.map((area) => (
            <li key={area.id} className="py-2">
              <RecordRow
                name={area.name}
                canEdit={canEdit}
                queryKeys={KEYS}
                deleteAction={() => deleteArea(area.id)}
                renderForm={(close) => <AreaEdit area={area} zones={zones} onClose={close} />}
              >
                {area.name}
              </RecordRow>
            </li>
          ))}
        </ul>
      )}
      {canEdit && <AddArea zone={zone} />}
    </section>
  )
}

function VenueForm({
  label,
  buttonLabel,
  venue,
  zones,
  save,
  onDone,
  onCancel,
}: {
  label: string
  buttonLabel: string
  venue?: AdminVenue
  zones: AdminZone[]
  save: (fields: VenueFields) => Promise<unknown>
  onDone: () => void
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  const [name, setName] = useState(venue?.name ?? '')
  const [areaId, setAreaId] = useState(venue ? String(venue.area_id) : '')
  const [address, setAddress] = useState(venue?.address ?? '')
  const action = useCatalogAction(KEYS, save, onDone)
  return (
    <form
      aria-label={label}
      className="space-y-3"
      onSubmit={(e) => submit(e, () => action.mutate({ name, area_id: Number(areaId), address }))}
    >
      <Field label={t('admin.zones.venueName')}>
        <input className={inputClass} required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label={t('admin.zones.area')}>
        <select className={inputClass} required value={areaId} onChange={(e) => setAreaId(e.target.value)}>
          <option value="">{t('admin.zones.chooseArea')}</option>
          {zones.map((zone) => (
            <optgroup key={zone.id} label={zone.name}>
              {zone.areas.map((area) => (
                <option key={area.id} value={area.id}>
                  {area.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </Field>
      <Field label={t('admin.zones.address')}>
        <input className={inputClass} maxLength={255} value={address} onChange={(e) => setAddress(e.target.value)} />
      </Field>
      <Refusal error={action.error} />
      <FormButtons label={buttonLabel} pending={action.isPending} onCancel={onCancel} />
    </form>
  )
}

function Venues({ venues, zones, canEdit }: { venues: AdminVenue[]; zones: AdminZone[]; canEdit: boolean }) {
  const { t } = useTranslation()
  // The form resets by remounting, so a new venue starts blank in every field.
  const [addCount, setAddCount] = useState(0)
  const areaName = (id: number) => zones.flatMap((zone) => zone.areas).find((area) => area.id === id)?.name ?? ''
  return (
    <Panel title={t('admin.zones.venuesTitle')}>
      {venues.length === 0 ? (
        <p className="text-sm text-stone-700">{t('admin.zones.noVenues')}</p>
      ) : (
        <ul className="divide-y divide-stone-200">
          {venues.map((venue) => (
            <li key={venue.id} className="py-2">
              <RecordRow
                name={venue.name}
                canEdit={canEdit}
                queryKeys={KEYS}
                deleteAction={() => deleteVenue(venue.id)}
                renderForm={(close) => (
                  <VenueForm
                    label={`${t('admin.manage.edit')}: ${venue.name}`}
                    buttonLabel={t('admin.manage.save')}
                    venue={venue}
                    zones={zones}
                    save={(fields) => patchVenue(venue.id, fields)}
                    onDone={close}
                    onCancel={close}
                  />
                )}
              >
                <p className="font-medium">{venue.name}</p>
                <p className="text-sm text-stone-700">{areaName(venue.area_id)}</p>
                {venue.address && <p className="text-sm text-stone-700">{venue.address}</p>}
              </RecordRow>
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <VenueForm
          key={addCount}
          label={t('admin.zones.addVenue')}
          buttonLabel={t('admin.zones.addVenue')}
          zones={zones}
          save={createVenue}
          onDone={() => setAddCount((count) => count + 1)}
        />
      )}
    </Panel>
  )
}

export default function ZonesVenues() {
  const { t } = useTranslation()
  const canEdit = useIsOwner()
  const [addCount, setAddCount] = useState(0)
  const zones = useQuery({ queryKey: KEYS[0], queryFn: getZones })
  const venues = useQuery({ queryKey: KEYS[1], queryFn: getVenues })
  const error = zones.error ?? venues.error

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t('admin.nav.zones')}</h1>
      {error ? (
        <LoadProblem error={error} />
      ) : !zones.data || !venues.data ? (
        <p className="text-stone-700">{t('book.loading')}</p>
      ) : (
        <>
          <h2 className="text-lg font-semibold">{t('admin.zones.zonesTitle')}</h2>
          {zones.data.length === 0 && <p className="text-sm text-stone-700">{t('admin.zones.noZones')}</p>}
          {zones.data.map((zone) => (
            <ZonePanel key={zone.id} zone={zone} zones={zones.data} canEdit={canEdit} />
          ))}
          {canEdit && (
            <section className="rounded-md border border-stone-200 bg-white p-4">
              <ZoneForm
                key={addCount}
                label={t('admin.zones.addZone')}
                buttonLabel={t('admin.zones.addZone')}
                save={createZone}
                onDone={() => setAddCount((count) => count + 1)}
              />
            </section>
          )}
          <Venues venues={venues.data} zones={zones.data} canEdit={canEdit} />
        </>
      )}
    </div>
  )
}
