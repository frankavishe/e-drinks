import { useTranslation } from 'react-i18next'
import { Link, Navigate } from 'react-router-dom'
import { ApiError } from '../../lib/api'
import type { BookingRow } from '../../lib/adminApi'
import { formatDate, formatTzs } from '../../lib/publicApi'
import { Notice } from '../book/ui'

/** A failed load: an expired login goes back to the login page, anything else is said out loud. */
export function LoadProblem({ error }: { error: unknown }) {
  const { t } = useTranslation()
  if (error instanceof ApiError && error.status === 401) return <Navigate to="/login" replace />
  return <Notice tone="problem">{t('admin.loadFailed')}</Notice>
}

export function Flag({ tone = 'warn', children }: { tone?: 'warn' | 'plain'; children: string }) {
  const styles = tone === 'warn' ? 'bg-amber-100 text-amber-950' : 'bg-stone-200 text-stone-900'
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${styles}`}>{children}</span>
}

export default function BookingRows({ rows }: { rows: BookingRow[] }) {
  const { t, i18n } = useTranslation()
  return (
    <ul className="divide-y divide-stone-200 rounded-md border border-stone-200 bg-white">
      {rows.map((row) => (
        <li key={row.id}>
          <Link
            to={`/admin/bookings/${row.id}`}
            className="block px-3 py-3 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-emerald-800"
          >
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-semibold tabular-nums text-emerald-900">{row.code}</span>
              <Flag tone="plain">{t(`status.${row.status}`)}</Flag>
              {row.is_rush && <Flag>{t(row.rush_approved ? 'admin.flag.rushApproved' : 'admin.flag.rush')}</Flag>}
              {row.provisional && <Flag>{t('admin.flag.provisional')}</Flag>}
            </span>
            <span className="mt-1 block text-sm">
              {formatDate(row.event_date, i18n.language)}, {row.start_time.slice(0, 5)}
            </span>
            <span className="block text-sm text-stone-700">{row.customer_name}</span>
            <span className="mt-1 block text-sm tabular-nums">
              {t('totals.total')}: {formatTzs(row.total)} · {t('totals.paid')}: {formatTzs(row.amount_paid)}
            </span>
            {row.amount_pending > 0 && (
              <span className="block text-sm font-semibold tabular-nums text-amber-900">
                {t('totals.pending')}: {formatTzs(row.amount_pending)}
              </span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  )
}
