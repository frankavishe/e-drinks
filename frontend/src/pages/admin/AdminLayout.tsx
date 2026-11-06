import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ApiError } from '../../lib/api'
import { getMe } from '../../lib/adminApi'
import { supabase } from '../../lib/supabase'
import { Notice } from '../book/ui'

const NAV = [
  ['/admin', 'admin.nav.dashboard', true],
  ['/admin/bookings', 'admin.nav.bookings', false],
] as const

export default function AdminLayout() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const other = i18n.language === 'sw' ? 'en' : 'sw'
  const me = useQuery({ queryKey: ['admin', 'me'], queryFn: getMe, retry: false })
  const status = me.error instanceof ApiError ? me.error.status : undefined

  async function logOut() {
    await supabase?.auth.signOut()
    queryClient.removeQueries({ queryKey: ['admin'] })
    navigate('/login')
  }

  if (status === 401) return <Navigate to="/login" replace />

  return (
    <div className="flex min-h-screen flex-col bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link to="/admin" className="text-xl font-bold text-emerald-800">
            {t('brand')}
          </Link>
          {me.data && (
            <nav className="flex flex-wrap gap-4 text-sm">
              {NAV.map(([to, key, end]) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    isActive ? 'font-semibold text-emerald-700' : 'hover:text-emerald-700'
                  }
                >
                  {t(key)}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="ml-auto flex flex-wrap items-center gap-3 text-sm">
            {me.data && <span className="text-stone-700">{`${me.data.name} · ${t(`admin.role.${me.data.role}`)}`}</span>}
            <button type="button" onClick={() => i18n.changeLanguage(other)} className="underline underline-offset-2">
              {other === 'en' ? 'English' : 'Kiswahili'}
            </button>
            {(me.data || status === 403) && (
              <button type="button" onClick={logOut} className="underline underline-offset-2">
                {t('admin.logOut')}
              </button>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {me.data ? (
          <Outlet />
        ) : me.isPending ? (
          <p className="text-stone-700">{t('book.loading')}</p>
        ) : (
          <Notice tone="problem">{t(status === 403 ? 'admin.notAllowed' : 'admin.loadFailed')}</Notice>
        )}
      </main>
    </div>
  )
}
