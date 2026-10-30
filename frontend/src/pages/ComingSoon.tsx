import { useTranslation } from 'react-i18next'

export default function ComingSoon() {
  const { t } = useTranslation()
  return <p className="mx-auto max-w-6xl px-4 py-20 text-stone-500">{t('comingSoon')}</p>
}
