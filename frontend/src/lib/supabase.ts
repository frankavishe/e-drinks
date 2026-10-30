import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

// Used only for planner/admin login. All data goes through the FastAPI API.
export const supabase: SupabaseClient | null = url && anonKey ? createClient(url, anonKey) : null
