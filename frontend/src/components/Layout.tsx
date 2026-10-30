import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet } from 'react-router-dom'

const NAV = [
  ['/packages', 'nav.packages'],
  ['/gallery', 'nav.gallery'],
  ['/faq', 'nav.faq'],
  ['/planners', 'nav.planners'],
  ['/contact', 'nav.contact'],
  ['/track', 'nav.track'],
] as const

export default function Layout() {
  const { t, i18n } = useTranslation()
  const other = i18n.language === 'sw' ? 'en' : 'sw'

  return (
    <div className="min-h-screen flex flex-col bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
          <Link to="/" className="text-xl font-bold text-emerald-800">
            {t('brand')}
          </Link>
          <nav className="flex flex-wrap gap-4 text-sm">
            {NAV.map(([to, key]) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => (isActive ? 'text-emerald-700 font-semibold' : 'hover:text-emerald-700')}
              >
                {t(key)}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <button
              type="button"
              onClick={() => i18n.changeLanguage(other)}
              className="text-sm underline underline-offset-2"
            >
              {other === 'en' ? 'English' : 'Kiswahili'}
            </button>
            <Link to="/book" className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800">
              {t('nav.book')}
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-stone-200 bg-white py-6 text-center text-sm text-stone-500">
        {t('brand')} · {t('tagline')}
      </footer>
    </div>
  )
}
