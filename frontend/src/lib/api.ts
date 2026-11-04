import { supabase } from './supabase'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

export class ApiError extends Error {
  status: number
  /** Machine-readable reason from a structured `detail`, e.g. "quote_changed". */
  code?: string
  /** Whatever else a structured `detail` carried, e.g. the updated quote. */
  data?: Record<string, unknown>

  constructor(status: number, message: string, code?: string, data?: Record<string, unknown>) {
    super(message)
    this.status = status
    this.code = code
    this.data = data
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const session = supabase ? (await supabase.auth.getSession()).data.session : null
  if (session) headers.set('Authorization', `Bearer ${session.access_token}`)

  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = body.detail
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      throw new ApiError(res.status, res.statusText, detail.code, detail)
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : res.statusText)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}
