/**
 * Approvals store — pending approvals updated via WebSocket events.
 */
import { writable } from 'svelte/store';
import { approveAction, denyAction } from '$lib/api/client.js';
import type { PendingApproval, ApprovalEvent } from '$lib/types.js';

export const pendingApprovals = writable<PendingApproval[]>([]);

/** Handle a WebSocket approval event */
export function handleApprovalEvent(event: ApprovalEvent): void {
	const { type, data } = event;

	if (type === 'approval.requested') {
		pendingApprovals.update(list => [
			...list,
			{
				id: data.approval_id,
				agent_id: event.agent_id,
				tool_name: data.tool_name!,
				arguments: data.arguments!,
				created_at: data.created_at!
			}
		]);
	} else if (type === 'approval.resolved') {
		pendingApprovals.update(list =>
			list.filter(a => a.id !== data.approval_id)
		);
	}
}

export async function approve(id: string): Promise<void> {
	await approveAction(id);
}

export async function deny(id: string): Promise<void> {
	await denyAction(id);
}
