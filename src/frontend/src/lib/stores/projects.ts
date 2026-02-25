/**
 * Projects store — project list and context switching.
 */
import { writable, get } from 'svelte/store';
import { currentUser } from '$lib/auth.js';
import { getAccessToken } from '$lib/auth.js';
import {
	fetchProjects,
	createProjectInDb,
	addProjectMember,
	removeProjectMember,
} from '$lib/supabase.js';
import {
	waitForBackend,
	connectWebSocket,
	disconnectWebSocket,
} from '$lib/api/client.js';
import { refreshAgents } from '$lib/stores/agents.js';
import { clearMessages } from '$lib/stores/chat.js';
import type { Project, WebSocketEvent } from '$lib/types.js';

export const projects = writable<Project[]>([]);
export const currentProject = writable<Project | null>(null); // null = personal mode

export async function loadProjects(): Promise<void> {
	const user = get(currentUser);
	if (!user) return;

	try {
		const data = await fetchProjects(user.id);
		projects.set(data);
	} catch (e) {
		console.error('Failed to load projects:', e);
	}
}

export async function createProject(name: string, description: string = ''): Promise<Project> {
	const user = get(currentUser);
	if (!user) throw new Error('Not logged in');

	const project = await createProjectInDb(name, description, user.id);
	await loadProjects();
	return project;
}

export async function inviteToProject(projectId: string, userId: string): Promise<void> {
	await addProjectMember(projectId, userId);
}

export async function leaveProject(projectId: string): Promise<void> {
	const user = get(currentUser);
	if (!user) return;
	await removeProjectMember(projectId, user.id);
	await loadProjects();
}

/**
 * Switch to a project instance.
 */
export async function switchToProject(project: Project, onWebSocketEvent: (event: WebSocketEvent) => void): Promise<void> {
	const token = await getAccessToken();
	if (!token) throw new Error('Not authenticated');

	// Disconnect current WebSocket
	disconnectWebSocket();

	// Request project session from gateway
	const res = await fetch('/gateway/project-session', {
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

	await waitForBackend();

	// Reconnect WebSocket and refresh state
	await connectWebSocket(onWebSocketEvent);
	await refreshAgents();
	clearMessages();
	currentProject.set(project);
}

/**
 * Switch back to personal mode.
 */
export async function switchToPersonal(onWebSocketEvent: (event: WebSocketEvent) => void): Promise<void> {
	const token = await getAccessToken();
	if (!token) throw new Error('Not authenticated');

	const proj = get(currentProject);

	// Disconnect current WebSocket
	disconnectWebSocket();

	// Leave project if currently in one
	if (proj) {
		await fetch('/gateway/leave-project', {
			method: 'POST',
			headers: {
				'Authorization': `Bearer ${token}`,
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ project_id: proj.id }),
		}).catch(() => {});
	}

	// Get personal session
	const res = await fetch('/gateway/session', {
		method: 'POST',
		headers: {
			'Authorization': `Bearer ${token}`,
			'Content-Type': 'application/json',
		},
	});

	if (!res.ok) throw new Error('Failed to start personal session');

	await waitForBackend();

	// Reconnect WebSocket and refresh state
	await connectWebSocket(onWebSocketEvent);
	await refreshAgents();
	clearMessages();
	currentProject.set(null);
}
