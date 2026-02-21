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

export const friends = writable([]);
export const friendRequests = writable([]);

export async function loadFriends() {
	const user = get(currentUser);
	if (!user) return;

	try {
		const data = await fetchFriendships(user.id);
		// Map to friend profile (the other person in the friendship)
		const friendList = data.map(f => {
			const friend = f.requester_id === user.id ? f.addressee : f.requester;
			return { ...friend, friendship_id: f.id };
		});
		friends.set(friendList);
	} catch (e) {
		console.error('Failed to load friends:', e);
	}
}

export async function loadFriendRequests() {
	const user = get(currentUser);
	if (!user) return;

	try {
		const data = await fetchFriendRequests(user.id);
		friendRequests.set(data);
	} catch (e) {
		console.error('Failed to load friend requests:', e);
	}
}

export async function sendFriendRequest(email) {
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

export async function acceptFriendRequest(friendshipId) {
	await updateFriendshipStatus(friendshipId, 'accepted');
	await loadFriendRequests();
	await loadFriends();
}

export async function declineFriendRequest(friendshipId) {
	await updateFriendshipStatus(friendshipId, 'declined');
	await loadFriendRequests();
}
