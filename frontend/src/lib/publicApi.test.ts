import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { formatTzs, whatsappLink } from './publicApi'

describe('whatsappLink', () => {
  it('uses the digits of the number and encodes the message', () => {
    const link = whatsappLink('+255 700-000-000', 'Oda ED-2026-0001 & zaidi')
    expect(link).toBe('https://wa.me/255700000000?text=Oda%20ED-2026-0001%20%26%20zaidi')
  })

  it.each(['sw', 'en'])('holds the booking number in the %s message', (lng) => {
    const message = i18n.t('book.confirm.whatsappMessage', { code: 'ED-2026-0001', lng })
    expect(decodeURIComponent(whatsappLink('255700000000', message))).toContain('ED-2026-0001')
  })

  it('has a different message per language', () => {
    const sw = i18n.t('book.confirm.whatsappMessage', { code: 'X', lng: 'sw' })
    const en = i18n.t('book.confirm.whatsappMessage', { code: 'X', lng: 'en' })
    expect(sw).not.toBe(en)
  })
})

describe('formatTzs', () => {
  it('groups thousands', () => {
    expect(formatTzs(1806500)).toBe('TSh 1,806,500')
  })
})
