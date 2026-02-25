/**
 * Auth module — wraps Supabase auth for AshAI.
 * Provides sign-up, sign-in, sign-out, and session management.
 */

import { createClient, type SupabaseClient, type Session, type AuthChangeEvent } from '@supabase/supabase-js';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js';
import { writable } from 'svelte/store';
import type { User } from '@supabase/supabase-js';

let supabase: SupabaseClient | null = null;

function getSupabase(): SupabaseClient | null {
	if (!supabase && SUPABASE_URL && SUPABASE_ANON_KEY) {
		supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
	}
	return supabase;
}

/** Whether Supabase auth is configured */
export function isAuthEnabled(): boolean {
	return !!(SUPABASE_URL && SUPABASE_ANON_KEY);
}

/** Current user store — null if not logged in */
export const currentUser = writable<User | null>(null);

/** Sign up with email, password, and display name */
export async function signUp(email: string, password: string, displayName: string = ''): Promise<{ user: User | null; session: Session | null }> {
	const sb = getSupabase();
	if (!sb) throw new Error('Auth not configured');

	const { data, error } = await sb.auth.signUp({
		email,
		password,
		options: {
			data: { display_name: displayName || email.split('@')[0] }
		}
	});
	if (error) throw error;

	// Update the profile with the display name
	if (data.user && displayName) {
		await sb.from('profiles').upsert({
			id: data.user.id,
			email,
			display_name: displayName,
		});
	}

	return data;
}

/** Sign in with email and password */
export async function signIn(email: string, password: string): Promise<{ user: User; session: Session }> {
	const sb = getSupabase();
	if (!sb) throw new Error('Auth not configured');

	const { data, error } = await sb.auth.signInWithPassword({ email, password });
	if (error) throw error;
	return data;
}

/** Sign out */
export async function signOut(): Promise<void> {
	const sb = getSupabase();
	if (!sb) return;

	const { error } = await sb.auth.signOut();
	if (error) throw error;
	currentUser.set(null);
}

/** Get current session (access token + user) */
export async function getSession(): Promise<Session | null> {
	const sb = getSupabase();
	if (!sb) return null;

	const { data: { session } } = await sb.auth.getSession();
	return session;
}

/** Get the current access token (JWT) */
export async function getAccessToken(): Promise<string | null> {
	const session = await getSession();
	return session?.access_token || null;
}

/** Listen for auth state changes */
export function onAuthStateChange(callback: (event: AuthChangeEvent, session: Session | null) => void): { unsubscribe: () => void } {
	const sb = getSupabase();
	if (!sb) return { unsubscribe: () => {} };

	const { data: { subscription } } = sb.auth.onAuthStateChange((event, session) => {
		currentUser.set(session?.user || null);
		callback(event, session);
	});

	return subscription;
}

/** Initialize — check for existing session */
export async function initAuth(): Promise<Session | null> {
	const session = await getSession();
	currentUser.set(session?.user || null);
	return session;
}
