/**
 * Agents store — reactive list of agents updated via WebSocket.
 */
import { writable } from 'svelte/store';
import { listAgents } from '$lib/api/client.js';

export const agents = writable([]);

export async function refreshAgents() {
	try {
		const data = await listAgents();
		agents.set(data);
	} catch (e) {
		console.error('Failed to fetch agents:', e);
	}
}

/** Handle a WebSocket event to update agents reactively */
export function handleAgentEvent(event) {
	const { type, agent_id, data } = event;

	if (type === 'agent.created') {
		// Refresh full list to get new agent data
		refreshAgents();
	} else if (type === 'agent.status_changed') {
		agents.update(list =>
			list.map(a => a.id === agent_id ? { ...a, status: data.status } : a)
		);
	} else if (type === 'agent.destroyed') {
		agents.update(list => list.filter(a => a.id !== agent_id));
	}
}
