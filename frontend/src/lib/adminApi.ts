import { api } from './api'

export const STAGES = [
  'request',
  'quoted',
  'confirmed',
  'fully_paid',
  'delivered',
  'returns_settled',
  'closed',
  'cancelled',
] as const

export interface AdminProfile {
  id: string
  role: string
  name: string
}

export interface BookingRow {
  id: number
  code: string
  status: string
  is_rush: boolean
  rush_approved: boolean
  provisional: boolean
  event_type: string
  event_date: string
  start_time: string
  guests: number
  customer_name: string
  customer_phone: string
  venue_name: string
  total: number
  amount_paid: number
  amount_pending: number
}

export interface Overview {
  today: BookingRow[]
  upcoming: BookingRow[]
}

export interface BookingList {
  total: number
  items: BookingRow[]
}

export interface BookingFilters {
  q?: string
  status?: string
  date_from?: string
  date_to?: string
  rush?: string
  limit?: number
  offset?: number
}

export interface AdminPayment {
  id: number
  kind: string
  method: string
  amount: number
  reference: string
  status: string
  confirmed_by_name: string | null
  confirmed_at: string | null
  created_at: string
}

export interface HistoryEntry {
  from_status: string | null
  to_status: string
  changed_by_name: string | null
  note: string
  created_at: string
}

export interface Move {
  to: string
  allowed: boolean
  reason: string | null
  back: boolean
}

export interface Financials {
  goods_total: number
  revenue: number
  profit: number
}

export interface BookingDetail extends BookingRow {
  customer_email: string
  hours: number
  venue_address: string
  custom_area: string
  lang: string
  setup_at: string
  collect_at: string
  notes: string
  internal_notes: string
  efd_receipt_no: string
  date_changes_used: number
  balance_due_date: string | null
  balance_due: number
  subtotal: number
  addons_total: number
  delivery_fee: number
  empties_deposit: number
  deposit_due: number
  refund_due: number | null
  refunded: number
  items: { name_sw: string; name_en: string; unit: string; qty: number; unit_price: number; line_total: number }[]
  addons: { name_sw: string; name_en: string; qty: number; unit_price: number; line_total: number }[]
  payments: AdminPayment[]
  history: HistoryEntry[]
  allowed_moves: Move[]
  /** Only in the owner's response. */
  financials?: Financials
}

export interface CancelPreview {
  days_ahead: number
  paid: number
  refund_due: number
}

export interface RefundInput {
  amount: number
  method: string
  reference: string
}

export interface CalendarBooking {
  id: number
  code: string
  status: string
  is_rush: boolean
  customer_name: string
  start_time: string
}

export interface CalendarAddon {
  addon_id: number
  name_sw: string
  name_en: string
  committed: number
  /** Null when the add-on has no limit. */
  owned: number | null
}

export interface CalendarDay {
  date: string
  bookings: CalendarBooking[]
  addons: CalendarAddon[]
}

export interface Calendar {
  days: CalendarDay[]
}

export interface Tier {
  min_qty: number
  unit_price: number
}

export interface ProductFields {
  name_sw: string
  name_en: string
  category: string
  unit: string
  units_per_pack: number
  is_alcohol: boolean
  /** Null means no image. */
  image_url: string | null
  returnable_glass: boolean
  empties_deposit_per_unit: number
  active: boolean
  /** Only in the owner's response. */
  cost_price?: number
}

export interface AdminProduct extends ProductFields {
  id: number
  tiers: Tier[]
}

export interface PackageRule {
  product_id: number
  /** A decimal string with three places, as the API sends it. */
  qty_per_guest: string
  per_hour: boolean
}

export interface PackageFields {
  slug: string
  name_sw: string
  name_en: string
  description_sw: string
  description_en: string
  base_hours: number
  sort_order: number
  active: boolean
}

export interface AdminPackage extends PackageFields {
  id: number
  rules: PackageRule[]
}

export interface AddonFields {
  name_sw: string
  name_en: string
  kind: string
  price: number
  /** Null means no limit. */
  owned_capacity: number | null
  active: boolean
  /** Only in the owner's response. */
  replacement_cost?: number
}

export interface AdminAddon extends AddonFields {
  id: number
}

export interface AdminArea {
  id: number
  name: string
  zone_id: number
}

export interface ZoneFields {
  name: string
  delivery_fee: number
}

export interface AdminZone extends ZoneFields {
  id: number
  areas: AdminArea[]
}

export interface VenueFields {
  name: string
  area_id: number
  address: string
}

export interface AdminVenue extends VenueFields {
  id: number
}

export type SettingsMap = Record<string, string>

const send = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
})

const booking = (id: number, action = '') => `/admin/bookings/${id}${action}`

export const getMe = () => api<AdminProfile>('/admin/me')
export const getOverview = () => api<Overview>('/admin/overview')

export function getBookings(filters: BookingFilters) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const query = params.toString()
  return api<BookingList>(`/admin/bookings${query ? `?${query}` : ''}`)
}

export const getBooking = (id: number) => api<BookingDetail>(booking(id))
export const getCancelPreview = (id: number) => api<CancelPreview>(booking(id, '/cancel-preview'))

export const patchBooking = (id: number, body: { efd_receipt_no?: string; internal_notes?: string }) =>
  api<BookingDetail>(booking(id), send('PATCH', body))
export const moveStage = (id: number, to: string, note = '') =>
  api<BookingDetail>(booking(id, '/stage'), send('POST', { to, note }))
export const cancelBooking = (id: number, note = '') =>
  api<BookingDetail>(booking(id, '/cancel'), send('POST', { note }))
export const changeDate = (id: number, body: { new_date: string; exception: boolean; note: string }) =>
  api<BookingDetail>(booking(id, '/date-change'), send('POST', body))
export const decideRush = (id: number, approve: boolean, note = '') =>
  api<BookingDetail>(booking(id, '/rush'), send('POST', { approve, note }))
export const setDeliveryFee = (id: number, fee: number) =>
  api<BookingDetail>(booking(id, '/delivery-fee'), send('POST', { fee }))
export const addRefund = (id: number, body: RefundInput) =>
  api<BookingDetail>(booking(id, '/refunds'), send('POST', body))
export const confirmPayment = (paymentId: number) =>
  api<BookingDetail>(`/admin/payments/${paymentId}/confirm`, send('POST'))
export const rejectPayment = (paymentId: number) =>
  api<BookingDetail>(`/admin/payments/${paymentId}/reject`, send('POST'))

export const getCalendar = (from: string, to: string) =>
  api<Calendar>(`/admin/calendar?${new URLSearchParams({ from, to })}`)

export const getProducts = () => api<AdminProduct[]>('/admin/products')
export const createProduct = (body: ProductFields & { tiers: Tier[] }) =>
  api<AdminProduct>('/admin/products', send('POST', body))
export const patchProduct = (id: number, body: Partial<ProductFields>) =>
  api<AdminProduct>(`/admin/products/${id}`, send('PATCH', body))
export const putTiers = (id: number, tiers: Tier[]) =>
  api<AdminProduct>(`/admin/products/${id}/tiers`, send('PUT', tiers))
export const deleteProduct = (id: number) => api<void>(`/admin/products/${id}`, send('DELETE'))

export const getPackages = () => api<AdminPackage[]>('/admin/packages')
export const createPackage = (body: PackageFields & { rules: PackageRule[] }) =>
  api<AdminPackage>('/admin/packages', send('POST', body))
export const patchPackage = (id: number, body: Partial<PackageFields>) =>
  api<AdminPackage>(`/admin/packages/${id}`, send('PATCH', body))
export const putRules = (id: number, rules: PackageRule[]) =>
  api<AdminPackage>(`/admin/packages/${id}/rules`, send('PUT', rules))
export const deletePackage = (id: number) => api<void>(`/admin/packages/${id}`, send('DELETE'))

export const getAddons = () => api<AdminAddon[]>('/admin/addons')
export const createAddon = (body: AddonFields) => api<AdminAddon>('/admin/addons', send('POST', body))
export const patchAddon = (id: number, body: Partial<AddonFields>) =>
  api<AdminAddon>(`/admin/addons/${id}`, send('PATCH', body))
export const deleteAddon = (id: number) => api<void>(`/admin/addons/${id}`, send('DELETE'))

export const getZones = () => api<AdminZone[]>('/admin/zones')
export const createZone = (body: ZoneFields) => api<AdminZone>('/admin/zones', send('POST', body))
export const patchZone = (id: number, body: Partial<ZoneFields>) =>
  api<AdminZone>(`/admin/zones/${id}`, send('PATCH', body))
export const deleteZone = (id: number) => api<void>(`/admin/zones/${id}`, send('DELETE'))

export const createArea = (body: { name: string; zone_id: number }) =>
  api<AdminArea>('/admin/areas', send('POST', body))
export const patchArea = (id: number, body: { name?: string; zone_id?: number }) =>
  api<AdminArea>(`/admin/areas/${id}`, send('PATCH', body))
export const deleteArea = (id: number) => api<void>(`/admin/areas/${id}`, send('DELETE'))

export const getVenues = () => api<AdminVenue[]>('/admin/venues')
export const createVenue = (body: VenueFields) => api<AdminVenue>('/admin/venues', send('POST', body))
export const patchVenue = (id: number, body: Partial<VenueFields>) =>
  api<AdminVenue>(`/admin/venues/${id}`, send('PATCH', body))
export const deleteVenue = (id: number) => api<void>(`/admin/venues/${id}`, send('DELETE'))

export const getSettings = () => api<SettingsMap>('/admin/settings')
/** Send only the keys that changed; the answer is the full map. */
export const putSettings = (changes: SettingsMap) => api<SettingsMap>('/admin/settings', send('PUT', changes))

/** Date and time as they read in Dar es Salaam, wherever the browser is. */
export function formatDateTime(iso: string, lang: string): string {
  return new Intl.DateTimeFormat(lang === 'sw' ? 'sw-TZ' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Africa/Dar_es_Salaam',
  }).format(new Date(iso))
}
