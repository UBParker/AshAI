/**
 * Projects store — project list and context switching.
 */
import { writable, get } from 'svelte/store';
import { currentUser } from '$lib/auth.js';
import { getAccessToken } from '$lib/auth.js';
import { GATEWAY_URL } from '$lib/config.js';
import {
	fetchProjects,
	createProjectInDb,
	addProjectMember,
	removeProjectMember,
} from '$lib/supabase.js';
import {
	setBackendUrl,
	waitForBackend,
	connectWebSocket,
	disconnectWebSocket,
} from '$lib/api/client.js';
import { refreshAgents } from '$lib/stores/agents.js';
import { clearMessages } from '$lib/stores/chat.js';

export const projects = writable([]);
export const currentProject = writable(null); // null = personal mode

export async function loadProjects() {
	const user = get(currentUser);
	if (!user) return;

	try {
		const data = await fetchProjects(user.id);
		projects.set(data);
	} catch (e) {
		console.error('Failed to load projects:', e);
	}
}

export async function createProject(name, description = '') {
	const user = get(currentUser);
	if (!user) throw new Error('Not logged in');

	const project = await createProjectInDb(name, description, user.id);
	await loadProjects();
	return project;
}

export async function inviteToProject(projectId, userId) {
	await addProjectMember(projectId, userId);
}

export async function leaveProject(projectId) {
	const user = get(currentUser);
	if (!user) return;
	await removeProjectMember(projectId, user.id);
	await loadProjects();
}

/**
 * Switch to a project instance.
 * @param {object} project - The project object with at least { id, name }
 * @param {function} onWebSocketEvent - WebSocket event handler
 */
export async function switchToProject(project, onWebSocketEvent) {
	const token = await getAccessToken();
	if (!token || !GATEWAY_URL) throw new Error('Not authenticated');

	// Disconnect current WebSocket
	disconnectWebSocket();

	// Request project session from gateway
	const res = await fetch(`${GATEWAY_URL}/gateway/project-session`, {
		method: 'POST',
		headers: {
			'Authorization': `Bearer ${token}`,
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ project_id: project.id }),
	});

	if (!res.ok) {
		const text = await res.text();
		throw new Error(`Failed to start project session: ${text}`);
	}

	const { backend_url } = await res.json();
	setBackendUrl(backend_url);
	await waitForBackend();

	// Reconnect WebSocket and refresh state
	connectWebSocket(onWebSocketEvent);
	await refreshAgents();
	clearMessages();
	currentProject.set(project);
}

/**
 * Switch back to personal mode.
 * @param {function} onWebSocketEvent - WebSocket event handler
 */
export async function switchToPersonal(onWebSocketEvent) {
	const token = await getAccessToken();
	if (!token || !GATEWAY_URL) throw new Error('Not authenticated');

	const proj = get(currentProject);

	// Disconnect current WebSocket
	disconnectWebSocket();

	// Leave project if currently in one
	if (proj) {
		await fetch(`${GATEWAY_URL}/gateway/leave-project`, {
			method: 'POST',
			headers: {
				'Authorization': `Bearer ${token}`,
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ project_id: proj.id }),
		}).catch(() => {});
	}

	// Get personal session
	const res = await fetch(`${GATEWAY_URL}/gateway/session`, {
		method: 'POST',
		headers: {
			'Authorization': `Bearer ${token}`,
			'Content-Type': 'application/json',
		},
	});

	if (!res.ok) throw new Error('Failed to start personal session');

	const { backend_url } = await res.json();
	setBackendUrl(backend_url);
	await waitForBackend();

	// Reconnect WebSocket and refresh state
	connectWebSocket(onWebSocketEvent);
	await refreshAgents();
	clearMessages();
	currentProject.set(null);
}
