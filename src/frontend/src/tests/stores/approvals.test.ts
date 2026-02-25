import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import { pendingApprovals, handleApprovalEvent } from '$lib/stores/approvals.js';
import type { ApprovalEvent } from '$lib/types.js';

// Mock the API client
vi.mock('$lib/api/client.js', () => ({
	approveAction: vi.fn().mockResolvedValue(undefined),
	denyAction: vi.fn().mockResolvedValue(undefined)
}));

describe('Approvals Store', () => {
	beforeEach(() => {
		pendingApprovals.set([]);
	});

	it('starts with empty approvals', () => {
		expect(get(pendingApprovals)).toEqual([]);
	});

	it('adds approval on approval.requested event', () => {
		handleApprovalEvent({
			type: 'approval.requested',
			agent_id: 'agent-1',
			data: {
				approval_id: 'apr-1',
				tool_name: 'run_command',
				arguments: '{"cmd": "ls"}',
				created_at: '2024-01-01T00:00:00Z'
			}
		});

		const list = get(pendingApprovals);
		expect(list).toHaveLength(1);
		expect(list[0]).toEqual({
			id: 'apr-1',
			agent_id: 'agent-1',
			tool_name: 'run_command',
			arguments: '{"cmd": "ls"}',
			created_at: '2024-01-01T00:00:00Z'
		});
	});

	it('removes approval on approval.resolved event', () => {
		pendingApprovals.set([
			{ id: 'apr-1', agent_id: 'agent-1', tool_name: 'run_command', arguments: '{}', created_at: '' },
			{ id: 'apr-2', agent_id: 'agent-2', tool_name: 'write_file', arguments: '{}', created_at: '' }
		]);

		handleApprovalEvent({
			type: 'approval.resolved',
			agent_id: 'agent-1',
			data: { approval_id: 'apr-1' }
		});

		const list = get(pendingApprovals);
		expect(list).toHaveLength(1);
		expect(list[0].id).toBe('apr-2');
	});

	it('handles multiple approvals from the same agent', () => {
		handleApprovalEvent({
			type: 'approval.requested',
			agent_id: 'agent-1',
			data: { approval_id: 'apr-1', tool_name: 'read_file', arguments: '{}', created_at: '' }
		});

		handleApprovalEvent({
			type: 'approval.requested',
			agent_id: 'agent-1',
			data: { approval_id: 'apr-2', tool_name: 'write_file', arguments: '{}', created_at: '' }
		});

		const list = get(pendingApprovals);
		expect(list).toHaveLength(2);
	});

	it('resolving non-existent approval is safe', () => {
		pendingApprovals.set([
			{ id: 'apr-1', agent_id: 'agent-1', tool_name: 'run_command', arguments: '{}', created_at: '' }
		]);

		handleApprovalEvent({
			type: 'approval.resolved',
			agent_id: 'agent-1',
			data: { approval_id: 'non-existent' }
		});

		const list = get(pendingApprovals);
		expect(list).toHaveLength(1);
	});
});
