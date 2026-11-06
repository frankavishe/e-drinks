import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import AdminLayout from './AdminLayout'

const signOut = vi.hoisted(() => vi.fn(async () => ({ error: null })))

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: async () => ({ data: { session: { access_token: 'token' } } }),
      signOut,
    },
  },
}))

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const t = (key: string) => i18n.t(key)

let meResponse: () => Response

beforeEach(() => {
  signOut.mockClear()
  meResponse = () => json(200, { id: 'a', role: 'staff', name: 'Amina' })
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => meResponse()),
  )
})

afterEach(() => vi.unstubAllGlobals())

function renderLayout(client = new QueryClient()) {
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<p>admin content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

describe('AdminLayout', () => {
  it('sends someone with no session to the login page', async () => {
    meResponse = () => json(401, { detail: 'Not logged in' })
    renderLayout()
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(screen.queryByText('admin content')).not.toBeInTheDocument()
  })

  it('tells a planner they are not allowed, without showing the admin area', async () => {
    meResponse = () => json(403, { detail: 'Not allowed' })
    renderLayout()
    expect(await screen.findByText(t('admin.notAllowed'))).toBeInTheDocument()
    expect(screen.queryByText('admin content')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: t('admin.nav.bookings') })).not.toBeInTheDocument()
  })

  it('shows an error rather than the login page when the check fails for another reason', async () => {
    meResponse = () => json(500, { detail: 'Boom' })
    renderLayout()
    expect(await screen.findByText(t('admin.loadFailed'))).toBeInTheDocument()
    expect(screen.queryByText('login page')).not.toBeInTheDocument()
  })

  it('shows the admin area, navigation and who is logged in to staff', async () => {
    renderLayout()
    expect(await screen.findByText('admin content')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: t('admin.nav.dashboard') })).toHaveAttribute('href', '/admin')
    expect(screen.getByRole('link', { name: t('admin.nav.bookings') })).toHaveAttribute('href', '/admin/bookings')
    expect(screen.getByText(`Amina · ${t('admin.role.staff')}`)).toBeInTheDocument()
  })

  it('logs out and forgets cached admin data, so the next person on this device cannot see it', async () => {
    const client = new QueryClient()
    client.setQueryData(['admin', 'booking', 1], { financials: { profit: 1 } })
    renderLayout(client)
    fireEvent.click(await screen.findByRole('button', { name: t('admin.logOut') }))
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(signOut).toHaveBeenCalled()
    await waitFor(() => expect(client.getQueryData(['admin', 'booking', 1])).toBeUndefined())
  })
})
