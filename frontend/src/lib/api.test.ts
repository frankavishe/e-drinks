import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./supabase', () => ({ supabase: null }))

async function requestedUrl(apiUrl: string): Promise<string> {
  vi.stubEnv('VITE_API_URL', apiUrl)
  const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  vi.resetModules()
  const { api } = await import('./api')
  await api('/public/settings')
  return (fetchMock.mock.calls[0] as unknown[])[0] as string
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('api base URL', () => {
  it('uses the dev proxy when VITE_API_URL is blank, as in .env.example', async () => {
    expect(await requestedUrl('')).toBe('/api/public/settings')
  })

  it('uses VITE_API_URL when it is set', async () => {
    expect(await requestedUrl('https://api.example.test')).toBe(
      'https://api.example.test/public/settings',
    )
  })
})
