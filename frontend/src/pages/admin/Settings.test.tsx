import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import Settings from './Settings'

vi.mock('../../lib/supabase', () => ({ supabase: null }))

const SETTINGS = {
  business_name: 'e-drinks',
  tin: '',
  vrn: '',
  phone: '+255 700 000 000',
  email: '',
  notification_email: '',
  whatsapp_number: '255700000000',
  min_order: '300000',
  notice_days: '3',
  notice_days_servers: '7',
  deposit_percent: '50',
  balance_due_days: '3',
  mpesa_till: '',
  tigopesa_lipa: '',
  airtel_lipa: '',
  bank_details: '',
  policy_text_sw: 'Sera',
  policy_text_en: 'Policy',
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const t = (key: string) => i18n.t(key)

let role: string
let stored: Record<string, string>
let putResponse: (body: Record<string, string>) => Response
let puts: Record<string, string>[]

beforeEach(() => {
  role = 'owner'
  puts = []
  stored = { ...SETTINGS }
  putResponse = (body) => {
    stored = { ...stored, ...body }
    return json(stored)
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url.endsWith('/admin/me')) return json({ id: 'a', role, name: 'Amina' })
      if (init.method === 'PUT') {
        const body = JSON.parse(String(init.body))
        puts.push(body)
        return putResponse(body)
      }
      return json(stored)
    }),
  )
})

afterEach(() => vi.unstubAllGlobals())

/** The role is already known, as it is once AdminLayout has loaded, so a missing control means something. */
function renderSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(['admin', 'me'], { id: 'a', role, name: 'Amina' })
  render(
    <QueryClientProvider client={client}>
      <Settings />
    </QueryClientProvider>,
  )
}

const field = (key: string) => screen.findByLabelText(t(`admin.settings.field.${key}`))

describe('Settings', () => {
  it('lets staff read every setting but not change any', async () => {
    role = 'staff'
    renderSettings()
    const name = await field('business_name')
    expect(name).toHaveValue('e-drinks')
    expect(name).toHaveAttribute('readonly')
    expect(await field('policy_text_en')).toHaveAttribute('readonly')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows a field for every setting the server has', async () => {
    renderSettings()
    for (const key of Object.keys(SETTINGS)) {
      expect(await field(key)).toBeInTheDocument()
    }
  })

  it("sends only the owner's changed keys", async () => {
    renderSettings()
    await screen.findByRole('button', { name: t('admin.settings.save') })
    fireEvent.change(await field('min_order'), { target: { value: '400000' } })
    fireEvent.click(screen.getByRole('button', { name: t('admin.settings.save') }))
    expect(await screen.findByText(t('admin.settings.saved'))).toBeInTheDocument()
    expect(puts).toEqual([{ min_order: '400000' }])
    expect(await field('min_order')).toHaveValue('400000')
  })

  it('has nothing to save until a value differs from what is stored', async () => {
    renderSettings()
    const save = await screen.findByRole('button', { name: t('admin.settings.save') })
    expect(save).toBeDisabled()
    const minOrder = await field('min_order')
    fireEvent.change(minOrder, { target: { value: '400000' } })
    expect(save).toBeEnabled()
    fireEvent.change(minOrder, { target: { value: '300000' } })
    expect(save).toBeDisabled()
  })

  it("shows the server's reason and keeps what was typed when a value is refused", async () => {
    putResponse = () => json({ detail: { code: 'invalid_setting' } }, 409)
    renderSettings()
    await screen.findByRole('button', { name: t('admin.settings.save') })
    fireEvent.change(await field('deposit_percent'), { target: { value: '150' } })
    fireEvent.click(screen.getByRole('button', { name: t('admin.settings.save') }))
    expect(await screen.findByText(t('admin.refusal.invalid_setting'))).toBeInTheDocument()
    expect(await field('deposit_percent')).toHaveValue('150')
  })

  it('says so when the settings cannot be loaded', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ detail: 'no' }, 500)),
    )
    renderSettings()
    expect(await screen.findByText(t('admin.loadFailed'))).toBeInTheDocument()
  })
})
