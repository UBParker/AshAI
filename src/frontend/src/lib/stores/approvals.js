/**
 * Approvals store — pending approvals updated via WebSocket events.
 */
import { writable } from 'svelte/store';
import { approveAction, denyAction } from '$lib/api/client.js';

export const pendingApprovals = writable([]);

/** Handle a WebSocket approval event */
export function handleApprovalEvent(event) {
	const { type, data } = event;

	if (type === 'approval.requested') {
		pendingApprovals.update(list => [
			...list,
			{
				id: data.approval_id,
				agent_id: event.agent_id,
				tool_name: data.tool_name,
				arguments: data.arguments,
				created_at: data.created_at
			}
		]);
	} else if (type === 'approval.resolved') {
		pendingApprovals.update(list =>
			list.filter(a => a.id !== data.approval_id)
		);
	}
}

export async function approve(id) {
	await approveAction(id);
}

export async function deny(id) {
	await denyAction(id);
}
