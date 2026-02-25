/**
 * Friends store — friend list and pending requests.
 */
import { writable, get } from 'svelte/store';
import { currentUser } from '$lib/auth.js';
import {
	fetchFriendships,
	fetchFriendRequests,
	getProfileByEmail,
	createFriendRequest,
	updateFriendshipStatus,
} from '$lib/supabase.js';

export interface Friend {
	id: string;
	email: string;
	display_name: string;
	friendship_id: string;
}

export interface FriendRequest {
	id: string;
	requester_id: string;
	requester: { id: string; email: string; display_name: string };
	status: string;
}

export const friends = writable<Friend[]>([]);
export const friendRequests = writable<FriendRequest[]>([]);

export async function loadFriends(): Promise<void> {
	const user = get(currentUser);
	if (!user) return;

	try {
		const data = await fetchFriendships(user.id);
		// Map to friend profile (the other person in the friendship)
		const friendList = data.map((f: any) => {
			const friend = f.requester_id === user.id ? f.addressee : f.requester;
			return { ...friend, friendship_id: f.id };
		});
		friends.set(friendList);
	} catch (e) {
		console.error('Failed to load friends:', e);
	}
}

export async function loadFriendRequests(): Promise<void> {
	const user = get(currentUser);
	if (!user) return;

	try {
		const data = await fetchFriendRequests(user.id);
		friendRequests.set(data);
	} catch (e) {
		console.error('Failed to load friend requests:', e);
	}
}

export async function sendFriendRequest(email: string): Promise<void> {
	const user = get(currentUser);
	if (!user) throw new Error('Not logged in');

	// Look up the addressee by email
	const profile = await getProfileByEmail(email);
	if (!profile) throw new Error('User not found');
	if (profile.id === user.id) throw new Error('Cannot friend yourself');

	await createFriendRequest(user.id, profile.id);
	// Refresh lists
	await loadFriends();
}

export async function acceptFriendRequest(friendshipId: string): Promise<void> {
	await updateFriendshipStatus(friendshipId, 'accepted');
	await loadFriendRequests();
	await loadFriends();
}

export async function declineFriendRequest(friendshipId: string): Promise<void> {
	await updateFriendshipStatus(friendshipId, 'declined');
	await loadFriendRequests();
}
