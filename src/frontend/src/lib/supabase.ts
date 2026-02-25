/**
 * Supabase data helpers — friends, projects, invites CRUD.
 * Reuses the Supabase client from auth.ts.
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js';

let _client: SupabaseClient | null = null;

/** Get or create the Supabase client (shared with auth.ts) */
export function getSupabaseClient(): SupabaseClient | null {
	if (!_client && SUPABASE_URL && SUPABASE_ANON_KEY) {
		_client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
	}
	return _client;
}

// --- Profiles ---

export interface Profile {
	id: string;
	email: string;
	display_name: string;
}

export async function getProfile(userId: string): Promise<Profile> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('profiles')
		.select('*')
		.eq('id', userId)
		.single();
	if (error) throw error;
	return data;
}

export async function getProfileByEmail(email: string): Promise<Profile> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('profiles')
		.select('*')
		.eq('email', email)
		.single();
	if (error) throw error;
	return data;
}

export async function updateProfile(userId: string, updates: Partial<Profile>): Promise<Profile> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('profiles')
		.update(updates)
		.eq('id', userId)
		.select()
		.single();
	if (error) throw error;
	return data;
}

// --- Friendships ---

export interface Friendship {
	id: string;
	requester_id: string;
	addressee_id: string;
	status: string;
	requester: Profile;
	addressee: Profile;
}

export async function fetchFriendships(userId: string): Promise<Friendship[]> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('friendships')
		.select('*, requester:profiles!requester_id(*), addressee:profiles!addressee_id(*)')
		.or(`requester_id.eq.${userId},addressee_id.eq.${userId}`)
		.eq('status', 'accepted');
	if (error) throw error;
	return data;
}

export async function fetchFriendRequests(userId: string): Promise<Friendship[]> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('friendships')
		.select('*, requester:profiles!requester_id(*)')
		.eq('addressee_id', userId)
		.eq('status', 'pending');
	if (error) throw error;
	return data;
}

export async function createFriendRequest(requesterId: string, addresseeId: string): Promise<Friendship> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('friendships')
		.insert({ requester_id: requesterId, addressee_id: addresseeId })
		.select()
		.single();
	if (error) throw error;
	return data;
}

export async function updateFriendshipStatus(friendshipId: string, status: string): Promise<Friendship> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('friendships')
		.update({ status })
		.eq('id', friendshipId)
		.select()
		.single();
	if (error) throw error;
	return data;
}

// --- Projects ---

export interface ProjectRecord {
	id: string;
	name: string;
	description?: string;
	owner_id: string;
	created_at?: string;
}

export interface ProjectMember {
	project_id: string;
	user_id: string;
	role: string;
	joined_at?: string;
	profile: Profile;
}

export async function fetchProjects(userId: string): Promise<Array<ProjectRecord & { my_role: string }>> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('project_members')
		.select('role, joined_at, project:projects(*)')
		.eq('user_id', userId);
	if (error) throw error;
	return data.map((pm: any) => ({ ...pm.project, my_role: pm.role }));
}

export async function createProjectInDb(name: string, description: string, ownerId: string): Promise<ProjectRecord> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');

	// Create project
	const { data: project, error: projError } = await sb
		.from('projects')
		.insert({ name, description, owner_id: ownerId })
		.select()
		.single();
	if (projError) throw projError;

	// Add owner as member
	const { error: memberError } = await sb
		.from('project_members')
		.insert({ project_id: project.id, user_id: ownerId, role: 'owner' });
	if (memberError) throw memberError;

	return project;
}

export async function addProjectMember(projectId: string, userId: string, role: string = 'editor'): Promise<ProjectMember> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('project_members')
		.insert({ project_id: projectId, user_id: userId, role })
		.select()
		.single();
	if (error) throw error;
	return data;
}

export async function fetchProjectMembers(projectId: string): Promise<ProjectMember[]> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('project_members')
		.select('*, profile:profiles(*)')
		.eq('project_id', projectId);
	if (error) throw error;
	return data;
}

export async function removeProjectMember(projectId: string, userId: string): Promise<void> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { error } = await sb
		.from('project_members')
		.delete()
		.eq('project_id', projectId)
		.eq('user_id', userId);
	if (error) throw error;
}

// --- Invites ---

export interface Invite {
	id: string;
	code: string;
	type: 'friend' | 'project';
	creator_id: string;
	project_id?: string;
	max_uses: number;
	uses: number;
	expires_at?: string;
	creator: Profile;
	project?: ProjectRecord;
}

export interface CreateInviteData {
	type: 'friend' | 'project';
	creatorId: string;
	projectId?: string;
	maxUses?: number;
	expiresAt?: string | null;
}

export async function createInvite({ type, creatorId, projectId, maxUses = 1, expiresAt = null }: CreateInviteData): Promise<Invite> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('invites')
		.insert({
			type,
			creator_id: creatorId,
			project_id: projectId,
			max_uses: maxUses,
			expires_at: expiresAt,
		})
		.select()
		.single();
	if (error) throw error;
	return data;
}

export async function getInviteByCode(code: string): Promise<Invite> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { data, error } = await sb
		.from('invites')
		.select('*, creator:profiles!creator_id(*), project:projects(*)')
		.eq('code', code)
		.single();
	if (error) throw error;
	return data;
}

export async function useInvite(inviteId: string): Promise<void> {
	const sb = getSupabaseClient();
	if (!sb) throw new Error('Supabase not configured');
	const { error } = await sb.rpc('increment_invite_uses', { invite_id: inviteId });
	if (error) {
		// Fallback: manual increment if RPC not set up
		const { data } = await sb
			.from('invites')
			.select('uses')
			.eq('id', inviteId)
			.single();
		if (data) {
			await sb
				.from('invites')
				.update({ uses: (data as any).uses + 1 })
				.eq('id', inviteId);
		}
	}
}
