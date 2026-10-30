import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import sw from './sw.json'

const STORAGE_KEY = 'lang'

function savedLanguage(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? 'sw'
  } catch {
    return 'sw'
  }
}

i18n.use(initReactI18next).init({
  resources: { sw: { translation: sw }, en: { translation: en } },
  lng: savedLanguage(),
  fallbackLng: 'sw',
  interpolation: { escapeValue: false },
})

i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng
  try {
    localStorage.setItem(STORAGE_KEY, lng)
  } catch {
    /* storage unavailable */
  }
})

export default i18n
