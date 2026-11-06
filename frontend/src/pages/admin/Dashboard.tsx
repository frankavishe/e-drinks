import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getOverview, type BookingRow } from '../../lib/adminApi'
import BookingRows, { LoadProblem } from './BookingRows'

function Section({ title, empty, rows }: { title: string; empty: string; rows: BookingRow[] }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      {rows.length === 0 ? <p className="text-sm text-stone-700">{empty}</p> : <BookingRows rows={rows} />}
    </section>
  )
}

export default function Dashboard() {
  const { t } = useTranslation()
  const overview = useQuery({ queryKey: ['admin', 'overview'], queryFn: getOverview })

  if (overview.isError) return <LoadProblem error={overview.error} />
  if (!overview.data) return <p className="text-stone-700">{t('book.loading')}</p>
  return (
    <div className="space-y-6">
      <Section title={t('admin.dashboard.today')} empty={t('admin.dashboard.noneToday')} rows={overview.data.today} />
      <Section
        title={t('admin.dashboard.upcoming')}
        empty={t('admin.dashboard.noneUpcoming')}
        rows={overview.data.upcoming}
      />
    </div>
  )
}
