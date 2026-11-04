import { api } from './api'

export interface Tier {
  min_qty: number
  unit_price: number
}

export interface Product {
  id: number
  name_sw: string
  name_en: string
  category: string
  unit: string
  tiers: Tier[]
}

export interface Package {
  id: number
  slug: string
  name_sw: string
  name_en: string
  description_sw: string
  description_en: string
  rules: { product_id: number }[]
}

export interface Addon {
  id: number
  name_sw: string
  name_en: string
  kind: string
  price: number
}

export interface Venue {
  id: number
  name: string
  area_id: number
  address: string
}

export interface Areas {
  zones: { id: number; name: string; delivery_fee: number; areas: { id: number; name: string }[] }[]
  venues: Venue[]
}

export interface PaymentInstructions {
  mpesa_till: string
  tigopesa_lipa: string
  airtel_lipa: string
  bank_details: string
}

export interface PublicSettings {
  business_name: string
  whatsapp_number: string
  policy_text_sw: string
  policy_text_en: string
  payment_instructions: PaymentInstructions
}

export interface QuoteInput {
  event_date: string
  hours: number
  guests: number
  setup_at: string
  collect_at: string
  package_id?: number
  overrides?: Record<number, number>
  items?: { product_id: number; packs: number }[]
  addons: { addon_id: number; qty: number }[]
  area_id?: number
  custom_area?: string
}

export interface QuoteLine {
  product_id: number
  name_sw: string
  name_en: string
  unit: string
  packs: number
  unit_price: number
  line_total: number
  empties_deposit: number
}

export interface AddonLine {
  addon_id: number
  name_sw: string
  name_en: string
  qty: number
  unit_price: number
  line_total: number
  available: number | null
  ok: boolean
}

export interface Quote {
  lines: QuoteLine[]
  addon_lines: AddonLine[]
  subtotal: number
  addons_total: number
  delivery_fee: number
  delivery_custom: boolean
  empties_deposit: number
  total: number
  deposit_due: number
  balance_due_date: string
  flags: {
    is_rush: boolean
    below_minimum: boolean
    min_order: number
    provisional: boolean
    addons_unavailable: number[]
  }
}

export interface BookingInput extends QuoteInput {
  event_type: string
  start_time: string
  venue_id?: number
  venue_name: string
  venue_address: string
  name: string
  phone: string
  email: string
  notes: string
  lang: string
  expected_total: number
  accept_policy: boolean
  age_confirmed: boolean
}

export interface BookingCreated {
  code: string
  status: string
  is_rush: boolean
  provisional: boolean
  total: number
  deposit_due: number
  balance_due_date: string
  payment_instructions: PaymentInstructions
  whatsapp_number: string
}

export interface PaymentRecord {
  kind: string
  amount: number
  method: string
  reference: string
  status: string
  created_at: string
}

export interface TrackedBooking {
  code: string
  status: string
  is_rush: boolean
  provisional: boolean
  event_type: string
  event_date: string
  start_time: string
  hours: number
  guests: number
  venue_name: string
  venue_address: string
  items: { name_sw: string; name_en: string; unit: string; qty: number; unit_price: number; line_total: number }[]
  addons: { name_sw: string; name_en: string; qty: number; unit_price: number; line_total: number }[]
  subtotal: number
  addons_total: number
  delivery_fee: number
  empties_deposit: number
  total: number
  deposit_due: number
  balance_due_date: string
  amount_paid: number
  amount_pending: number
  balance_due: number
  payments: PaymentRecord[]
  payment_instructions: PaymentInstructions
}

export interface PaymentInput {
  phone: string
  kind: string
  method: string
  amount: number
  reference: string
}

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const getSettings = () => api<PublicSettings>('/public/settings')
export const getCatalog = () => api<Product[]>('/public/catalog')
export const getPackages = () => api<Package[]>('/public/packages')
export const getAddons = () => api<Addon[]>('/public/addons')
export const getAreas = () => api<Areas>('/public/areas')
export const postQuote = (input: QuoteInput) => api<Quote>('/public/quote', post(input))
export const createBooking = (input: BookingInput) => api<BookingCreated>('/public/bookings', post(input))
export const trackBooking = (code: string, phone: string) =>
  api<TrackedBooking>('/public/track', post({ code, phone }))
export const submitPayment = (code: string, input: PaymentInput) =>
  api<PaymentRecord>(`/public/bookings/${encodeURIComponent(code)}/payments`, post(input))

/** Display only. Every amount comes from the server. */
export function formatTzs(amount: number): string {
  return `TSh ${amount.toLocaleString('en-US')}`
}

export function formatDate(isoDate: string, lang: string): string {
  return new Intl.DateTimeFormat(lang === 'sw' ? 'sw-TZ' : 'en-GB', {
    dateStyle: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${isoDate}T00:00:00Z`))
}

export function localName(item: { name_sw: string; name_en: string }, lang: string): string {
  return lang === 'en' ? item.name_en : item.name_sw
}

export function whatsappLink(number: string, message: string): string {
  return `https://wa.me/${number.replace(/\D/g, '')}?text=${encodeURIComponent(message)}`
}
