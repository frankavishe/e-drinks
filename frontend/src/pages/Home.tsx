import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

export default function Home() {
  const { t } = useTranslation()
  return (
    <section className="mx-auto max-w-6xl px-4 py-20">
      <h1 className="max-w-2xl text-4xl font-bold leading-tight">{t('home.title')}</h1>
      <p className="mt-4 max-w-xl text-lg text-stone-600">{t('home.lead')}</p>
      <Link
        to="/book"
        className="mt-8 inline-block rounded-md bg-emerald-700 px-6 py-3 font-semibold text-white hover:bg-emerald-800"
      >
        {t('home.cta')}
      </Link>
    </section>
  )
}
