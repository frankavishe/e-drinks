import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { getBookings, STAGES } from '../../lib/adminApi'
import { Field, inputClass, primaryClass, secondaryClass } from '../book/ui'
import BookingRows, { LoadProblem } from './BookingRows'

const PAGE_SIZE = 50

function SearchForm({ initial, onSearch }: { initial: string; onSearch: (q: string) => void }) {
  const { t } = useTranslation()
  const [text, setText] = useState(initial)
  return (
    <form
      className="flex items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        onSearch(text.trim())
      }}
    >
      <div className="flex-1">
        <Field label={t('admin.list.search')}>
          <input className={inputClass} maxLength={120} value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
      </div>
      <button type="submit" className={primaryClass}>
        {t('admin.list.searchButton')}
      </button>
    </form>
  )
}

export default function BookingList() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const status = params.get('status') ?? ''
  const dateFrom = params.get('date_from') ?? ''
  const dateTo = params.get('date_to') ?? ''
  const rush = params.get('rush') ?? ''
  const offset = Math.max(0, Number(params.get('offset')) || 0)

  const filters = { q, status, date_from: dateFrom, date_to: dateTo, rush, limit: PAGE_SIZE, offset }
  const list = useQuery({
    queryKey: ['admin', 'bookings', filters],
    queryFn: () => getBookings(filters),
    placeholderData: keepPreviousData,
  })

  /** Any new filter starts again from the first page. */
  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    next.delete('offset')
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  function goTo(newOffset: number) {
    const next = new URLSearchParams(params)
    next.set('offset', String(newOffset))
    setParams(next)
  }

  const total = list.data?.total ?? 0

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t('admin.nav.bookings')}</h1>

      {/* Keyed so going Back to another search shows that search's text. */}
      <SearchForm key={q} initial={q} onSearch={(value) => setFilter('q', value)} />

      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t('admin.list.stage')}>
          <select className={inputClass} value={status} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="">{t('admin.list.allStages')}</option>
            {STAGES.map((stage) => (
              <option key={stage} value={stage}>
                {t(`status.${stage}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('admin.list.from')}>
          <input
            type="date"
            className={inputClass}
            value={dateFrom}
            onChange={(e) => setFilter('date_from', e.target.value)}
          />
        </Field>
        <Field label={t('admin.list.to')}>
          <input
            type="date"
            className={inputClass}
            value={dateTo}
            onChange={(e) => setFilter('date_to', e.target.value)}
          />
        </Field>
      </div>
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          className="size-5"
          checked={rush === 'true'}
          onChange={(e) => setFilter('rush', e.target.checked ? 'true' : '')}
        />
        {t('admin.list.rushOnly')}
      </label>

      {list.isError ? (
        <LoadProblem error={list.error} />
      ) : !list.data ? (
        <p className="text-stone-700">{t('book.loading')}</p>
      ) : list.data.items.length === 0 ? (
        <p className="text-stone-700">{t('admin.list.empty')}</p>
      ) : (
        <>
          <p className="text-sm text-stone-700">{t('admin.list.count', { count: total })}</p>
          <BookingRows rows={list.data.items} />
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              className={`${secondaryClass} disabled:cursor-not-allowed disabled:opacity-50`}
              disabled={offset === 0}
              onClick={() => goTo(Math.max(0, offset - PAGE_SIZE))}
            >
              {t('admin.list.previous')}
            </button>
            <button
              type="button"
              className={`${secondaryClass} disabled:cursor-not-allowed disabled:opacity-50`}
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => goTo(offset + PAGE_SIZE)}
            >
              {t('admin.list.next')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
