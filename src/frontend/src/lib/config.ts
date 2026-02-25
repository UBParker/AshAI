/**
 * App configuration — reads from env vars at build time, with fallbacks.
 */

export const SUPABASE_URL: string = import.meta.env.VITE_SUPABASE_URL || '';
export const SUPABASE_ANON_KEY: string = import.meta.env.VITE_SUPABASE_ANON_KEY || '';
export const GATEWAY_URL: string = import.meta.env.VITE_GATEWAY_URL || '';
