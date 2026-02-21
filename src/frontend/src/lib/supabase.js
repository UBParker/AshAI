/**
 * Supabase data helpers — friends, projects, invites CRUD.
 * Reuses the Supabase client from auth.js.
 */

import { createClient } from '@supabase/supabase-js';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js';

let _client = null;

/** Get or create the Supabase client (shared with auth.js) */
export function getSupabaseClient() {
	if (!_client && SUPABASE_URL && SUPABASE_ANON_KEY) {
		_client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
	}
	return _client;
}

// --- Profiles ---

export async function getProfile(userId) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('profiles')
		.select('*')
		.eq('id', userId)
		.single();
	if (error) throw error;
	return data;
}

export async function getProfileByEmail(email) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('profiles')
		.select('*')
		.eq('email', email)
		.single();
	if (error) throw error;
	return data;
}

export async function updateProfile(userId, updates) {
	const sb = getSupabaseClient();
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

export async function fetchFriendships(userId) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('friendships')
		.select('*, requester:profiles!requester_id(*), addressee:profiles!addressee_id(*)')
		.or(`requester_id.eq.${userId},addressee_id.eq.${userId}`)
		.eq('status', 'accepted');
	if (error) throw error;
	return data;
}

export async function fetchFriendRequests(userId) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('friendships')
		.select('*, requester:profiles!requester_id(*)')
		.eq('addressee_id', userId)
		.eq('status', 'pending');
	if (error) throw error;
	return data;
}

export async function createFriendRequest(requesterId, addresseeId) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('friendships')
		.insert({ requester_id: requesterId, addressee_id: addresseeId })
		.select()
		.single();
	if (error) throw error;
	return data;
}

export async function updateFriendshipStatus(friendshipId, status) {
	const sb = getSupabaseClient();
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

export async function fetchProjects(userId) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('project_members')
		.select('role, joined_at, project:projects(*)')
		.eq('user_id', userId);
	if (error) throw error;
	return data.map(pm => ({ ...pm.project, my_role: pm.role }));
}

export async function createProjectInDb(name, description, ownerId) {
	const sb = getSupabaseClient();

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

export async function addProjectMember(projectId, userId, role = 'editor') {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('project_members')
		.insert({ project_id: projectId, user_id: userId, role })
		.select()
		.single();
	if (error) throw error;
	return data;
}

export async function fetchProjectMembers(projectId) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('project_members')
		.select('*, profile:profiles(*)')
		.eq('project_id', projectId);
	if (error) throw error;
	return data;
}

export async function removeProjectMember(projectId, userId) {
	const sb = getSupabaseClient();
	const { error } = await sb
		.from('project_members')
		.delete()
		.eq('project_id', projectId)
		.eq('user_id', userId);
	if (error) throw error;
}

// --- Invites ---

export async function createInvite({ type, creatorId, projectId, maxUses = 1, expiresAt = null }) {
	const sb = getSupabaseClient();
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

export async function getInviteByCode(code) {
	const sb = getSupabaseClient();
	const { data, error } = await sb
		.from('invites')
		.select('*, creator:profiles!creator_id(*), project:projects(*)')
		.eq('code', code)
		.single();
	if (error) throw error;
	return data;
}

export async function useInvite(inviteId) {
	const sb = getSupabaseClient();
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
				.update({ uses: data.uses + 1 })
				.eq('id', inviteId);
		}
	}
}
