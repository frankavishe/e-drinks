import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { getCalendar, type CalendarAddon, type CalendarBooking, type CalendarDay } from '../../lib/adminApi'
import { formatDate, localName } from '../../lib/publicApi'
import { primaryClass, secondaryClass } from '../book/ui'
import { Flag, LoadProblem } from './BookingRows'

type View = 'month' | 'week'

/* Dates stay YYYY-MM-DD strings and all arithmetic is in UTC, so the browser's timezone can't shift a day. */

const toDate = (iso: string) => new Date(`${iso}T00:00:00Z`)
const toIso = (date: Date) => date.toISOString().slice(0, 10)
const todayInDar = () => toIso(new Date(Date.now() + 3 * 60 * 60 * 1000))

function isDate(value: string | null): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = toDate(value)
  return !Number.isNaN(date.getTime()) && toIso(date) === value
}

function addDays(iso: string, days: number): string {
  const date = toDate(iso)
  date.setUTCDate(date.getUTCDate() + days)
  return toIso(date)
}

/** The first of the month, `months` away. Starting from the first means the 31st can't skip a short month. */
function addMonths(iso: string, months: number): string {
  const date = toDate(`${iso.slice(0, 7)}-01`)
  date.setUTCMonth(date.getUTCMonth() + months)
  return toIso(date)
}

const mondayOf = (iso: string) => addDays(iso, -((toDate(iso).getUTCDay() + 6) % 7))

function rangeOf(view: View, date: string) {
  if (view === 'week') {
    const from = mondayOf(date)
    return { from, to: addDays(from, 6) }
  }
  const lastOfMonth = addDays(addMonths(date, 1), -1)
  return { from: mondayOf(`${date.slice(0, 7)}-01`), to: addDays(mondayOf(lastOfMonth), 6) }
}

function localeFormat(lang: string, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat(lang === 'sw' ? 'sw-TZ' : 'en-GB', { ...options, timeZone: 'UTC' })
}

function BookingLink({ booking }: { booking: CalendarBooking }) {
  const { t } = useTranslation()
  return (
    <Link
      to={`/admin/bookings/${booking.id}`}
      className="block min-h-11 rounded border border-stone-200 bg-stone-50 p-1.5 text-xs break-words hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-emerald-800"
    >
      <span className="block tabular-nums">{booking.start_time.slice(0, 5)}</span>
      <span className="block font-semibold tabular-nums text-emerald-900">{booking.code}</span>
      <span className="block text-stone-700">{booking.customer_name}</span>
      <span className="mt-1 flex flex-wrap gap-1">
        <Flag tone="plain">{t(`status.${booking.status}`)}</Flag>
        {booking.is_rush && <Flag>{t('admin.flag.rush')}</Flag>}
      </span>
    </Link>
  )
}

function AddonUsage({ addon }: { addon: CalendarAddon }) {
  const { t, i18n } = useTranslation()
  const full = addon.owned !== null && addon.committed >= addon.owned
  return (
    <li className={`text-xs break-words ${full ? 'font-semibold text-amber-900' : 'text-stone-700'}`}>
      <span>{localName(addon, i18n.language)}: </span>
      <span className="tabular-nums">
        {addon.owned === null
          ? t('admin.calendar.inUse', { committed: addon.committed })
          : t('admin.calendar.usage', { committed: addon.committed, owned: addon.owned })}
      </span>
      {full && (
        <>
          {' '}
          <Flag>{t('admin.calendar.full')}</Flag>
        </>
      )}
    </li>
  )
}

function DayCell({ day, outside, today }: { day: CalendarDay; outside: boolean; today: boolean }) {
  const { i18n } = useTranslation()
  const lang = i18n.language
  const date = toDate(day.date)
  const weekday = localeFormat(lang, { weekday: 'short' }).format(date)
  const label = `${localeFormat(lang, { weekday: 'long' }).format(date)}, ${formatDate(day.date, lang)}`
  return (
    <li
      aria-label={label}
      aria-current={today ? 'date' : undefined}
      // Phones stack the days, so the neighbouring months' days would only add length.
      className={`min-w-0 space-y-2 p-2 md:min-h-28 ${outside ? 'hidden bg-stone-100 md:block' : 'bg-white'}`}
    >
      <p className={`text-sm ${outside ? 'text-stone-600' : ''}`}>
        <span className="md:hidden">{weekday} </span>
        <span
          className={`inline-flex size-7 items-center justify-center rounded-full tabular-nums ${
            today ? 'bg-emerald-700 font-semibold text-white' : ''
          }`}
        >
          {date.getUTCDate()}
        </span>
      </p>
      {day.bookings.length > 0 && (
        <ul className="space-y-1">
          {day.bookings.map((booking) => (
            <li key={booking.id}>
              <BookingLink booking={booking} />
            </li>
          ))}
        </ul>
      )}
      {day.addons.length > 0 && (
        <ul className="space-y-1">
          {day.addons.map((addon) => (
            <AddonUsage key={addon.addon_id} addon={addon} />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function Calendar() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [params, setParams] = useSearchParams()
  const view: View = params.get('view') === 'week' ? 'week' : 'month'
  const rawDate = params.get('date')
  const today = todayInDar()
  const date = isDate(rawDate) ? rawDate : today
  const { from, to } = rangeOf(view, date)

  const calendar = useQuery({
    queryKey: ['admin', 'calendar', from, to],
    queryFn: () => getCalendar(from, to),
  })

  function go(nextView: View, nextDate: string) {
    setParams({ view: nextView, date: nextDate })
  }

  const step = (direction: 1 | -1) =>
    go(view, view === 'week' ? addDays(date, 7 * direction) : addMonths(date, direction))

  const period =
    view === 'week'
      ? `${formatDate(from, lang)} – ${formatDate(to, lang)}`
      : localeFormat(lang, { month: 'long', year: 'numeric' }).format(toDate(date))

  // 1 January 2024 was a Monday.
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    localeFormat(lang, { weekday: 'short' }).format(toDate(addDays('2024-01-01', i))),
  )

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t('admin.nav.calendar')}</h1>

      <div className="flex flex-wrap items-center gap-2">
        {(['month', 'week'] as const).map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={view === option}
            className={view === option ? primaryClass : secondaryClass}
            onClick={() => go(option, date)}
          >
            {t(`admin.calendar.${option}`)}
          </button>
        ))}
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          <button type="button" className={secondaryClass} onClick={() => step(-1)}>
            {t('admin.calendar.previous')}
          </button>
          <button type="button" className={secondaryClass} onClick={() => go(view, today)}>
            {t('admin.calendar.today')}
          </button>
          <button type="button" className={secondaryClass} onClick={() => step(1)}>
            {t('admin.calendar.next')}
          </button>
        </div>
      </div>

      <h2 className="text-lg font-semibold" aria-live="polite">
        {period}
      </h2>

      {calendar.isError ? (
        <LoadProblem error={calendar.error} />
      ) : !calendar.data ? (
        <p className="text-stone-700">{t('book.loading')}</p>
      ) : (
        <div className="overflow-hidden rounded-md border border-stone-200 bg-stone-200">
          <div aria-hidden="true" className="hidden grid-cols-7 gap-px border-b border-stone-200 md:grid">
            {weekdays.map((weekday) => (
              <div key={weekday} className="bg-stone-100 px-2 py-1 text-xs font-semibold text-stone-700">
                {weekday}
              </div>
            ))}
          </div>
          <ol className="grid grid-cols-1 gap-px md:grid-cols-7">
            {calendar.data.days.map((day) => (
              <DayCell
                key={day.date}
                day={day}
                outside={view === 'month' && day.date.slice(0, 7) !== date.slice(0, 7)}
                today={day.date === today}
              />
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
