import type { BookingInput, QuoteInput, Venue } from '../../lib/publicApi'

export const STEPS = ['event', 'order', 'addons', 'review', 'contact'] as const
export type StepName = (typeof STEPS)[number]
export type ConflictCode = 'addons_unavailable' | 'below_minimum' | 'quote_changed'

const EAT_OFFSET = '+03:00'

export interface WizardState {
  step: number
  event_type: string
  event_date: string
  start_time: string
  hours: number
  guests: number
  venue_id: number | null
  venue_name: string
  venue_address: string
  area_id: number | null
  unlisted_area: boolean
  custom_area: string
  setup_time: string
  collect_day: 'same' | 'next'
  collect_time: string
  order_mode: 'package' | 'custom'
  package_id: number | null
  overrides: Record<number, number>
  items: Record<number, number>
  addons: Record<number, number>
  name: string
  phone: string
  email: string
  notes: string
  accept_policy: boolean
  age_confirmed: boolean
  reviewed_total: number | null
  conflict: ConflictCode | null
}

export const initialState: WizardState = {
  step: 0,
  event_type: 'wedding',
  event_date: '',
  start_time: '18:00',
  hours: 5,
  guests: 100,
  venue_id: null,
  venue_name: '',
  venue_address: '',
  area_id: null,
  unlisted_area: false,
  custom_area: '',
  setup_time: '15:00',
  collect_day: 'next',
  collect_time: '09:00',
  order_mode: 'package',
  package_id: null,
  overrides: {},
  items: {},
  addons: {},
  name: '',
  phone: '',
  email: '',
  notes: '',
  accept_policy: false,
  age_confirmed: false,
  reviewed_total: null,
  conflict: null,
}

type Fields = Partial<Omit<WizardState, 'step' | 'overrides' | 'items' | 'addons'>>

export type WizardAction =
  | { type: 'set'; fields: Fields }
  | { type: 'chooseVenue'; venue: Venue | null }
  | { type: 'setOverride'; productId: number; packs: number }
  | { type: 'setItem'; productId: number; packs: number }
  | { type: 'setAddon'; addonId: number; qty: number }
  | { type: 'goTo'; step: number }
  | { type: 'reviewed'; total: number }
  | { type: 'conflict'; code: ConflictCode }

function setCount(counts: Record<number, number>, id: number, value: number) {
  const next = { ...counts }
  if (value > 0) next[id] = value
  else delete next[id]
  return next
}

export function reducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'set': {
      const next = { ...state, ...action.fields }
      // Edited crate counts belong to one package and one event size.
      const recompute =
        next.package_id !== state.package_id || next.guests !== state.guests || next.hours !== state.hours
      return recompute ? { ...next, overrides: {} } : next
    }
    case 'chooseVenue':
      return action.venue
        ? {
            ...state,
            venue_id: action.venue.id,
            venue_name: action.venue.name,
            venue_address: action.venue.address,
            area_id: action.venue.area_id,
            unlisted_area: false,
            custom_area: '',
          }
        : { ...state, venue_id: null, venue_name: '', venue_address: '' }
    case 'setOverride':
      // Zero is meaningful here: it removes a product the package would otherwise include.
      return { ...state, overrides: { ...state.overrides, [action.productId]: action.packs } }
    case 'setItem':
      return { ...state, items: setCount(state.items, action.productId, action.packs) }
    case 'setAddon':
      return { ...state, addons: setCount(state.addons, action.addonId, action.qty) }
    case 'goTo':
      return { ...state, step: action.step, conflict: null }
    case 'reviewed':
      return { ...state, reviewed_total: action.total, step: STEPS.indexOf('contact'), conflict: null }
    case 'conflict':
      return { ...state, conflict: action.code, step: STEPS.indexOf('review') }
  }
}

function nextDay(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}

export function setupAt(state: WizardState): string {
  return `${state.event_date}T${state.setup_time}:00${EAT_OFFSET}`
}

export function collectAt(state: WizardState): string {
  const day = state.collect_day === 'next' ? nextDay(state.event_date) : state.event_date
  return `${day}T${state.collect_time}:00${EAT_OFFSET}`
}

export function eventIsComplete(state: WizardState): boolean {
  const hasArea = state.unlisted_area ? state.custom_area.trim() !== '' : state.area_id !== null
  return (
    state.event_date !== '' &&
    state.guests >= 1 &&
    state.hours >= 1 &&
    state.hours <= 24 &&
    hasArea &&
    collectIsAfterSetup(state)
  )
}

export function collectIsAfterSetup(state: WizardState): boolean {
  if (!state.event_date) return true
  return new Date(collectAt(state)).getTime() > new Date(setupAt(state)).getTime()
}

/** The order as the quote endpoint expects it, or null when there is nothing to price yet. */
export function quoteInput(state: WizardState, withAddons: boolean): QuoteInput | null {
  if (!eventIsComplete(state)) return null
  const base: QuoteInput = {
    event_date: state.event_date,
    hours: state.hours,
    guests: state.guests,
    setup_at: setupAt(state),
    collect_at: collectAt(state),
    addons: withAddons
      ? Object.entries(state.addons).map(([id, qty]) => ({ addon_id: Number(id), qty }))
      : [],
    ...(state.unlisted_area ? { custom_area: state.custom_area.trim() } : { area_id: state.area_id! }),
  }
  if (state.order_mode === 'package') {
    if (state.package_id === null) return null
    return { ...base, package_id: state.package_id, overrides: state.overrides }
  }
  const items = Object.entries(state.items).map(([id, packs]) => ({ product_id: Number(id), packs }))
  return items.length ? { ...base, items } : null
}

export function bookingInput(state: WizardState, lang: string): BookingInput | null {
  const quote = quoteInput(state, true)
  if (!quote || state.reviewed_total === null) return null
  return {
    ...quote,
    event_type: state.event_type,
    start_time: `${state.start_time}:00`,
    ...(state.venue_id !== null ? { venue_id: state.venue_id } : {}),
    venue_name: state.venue_name,
    venue_address: state.venue_address,
    name: state.name,
    phone: state.phone,
    email: state.email,
    notes: state.notes,
    lang,
    expected_total: state.reviewed_total,
    accept_policy: state.accept_policy,
    age_confirmed: state.age_confirmed,
  }
}
