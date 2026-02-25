import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import { agents, handleAgentEvent } from '$lib/stores/agents.js';
import type { Agent, AgentEvent } from '$lib/types.js';

// Mock the API client
vi.mock('$lib/api/client.js', () => ({
	listAgents: vi.fn().mockResolvedValue([])
}));

const mockAgent = (overrides: Partial<Agent> = {}): Agent => ({
	id: 'agent-1',
	name: 'Alice',
	status: 'idle',
	...overrides
});

describe('Agents Store', () => {
	beforeEach(() => {
		agents.set([]);
	});

	it('starts with empty agent list', () => {
		expect(get(agents)).toEqual([]);
	});

	it('handles agent.status_changed event', () => {
		agents.set([
			mockAgent({ id: 'agent-1', name: 'Alice' }),
			mockAgent({ id: 'agent-2', name: 'Bob' })
		]);

		handleAgentEvent({
			type: 'agent.status_changed',
			agent_id: 'agent-1',
			data: { status: 'thinking' }
		});

		const list = get(agents);
		expect(list[0].status).toBe('thinking');
		expect(list[1].status).toBe('idle');
	});

	it('handles agent.destroyed event', () => {
		agents.set([
			mockAgent({ id: 'agent-1', name: 'Alice' }),
			mockAgent({ id: 'agent-2', name: 'Bob' })
		]);

		handleAgentEvent({
			type: 'agent.destroyed',
			agent_id: 'agent-1',
			data: {}
		});

		const list = get(agents);
		expect(list).toHaveLength(1);
		expect(list[0].id).toBe('agent-2');
	});

	it('ignores unknown event types', () => {
		agents.set([mockAgent()]);

		handleAgentEvent({
			type: 'unknown.event',
			agent_id: 'agent-1',
			data: {}
		});

		const list = get(agents);
		expect(list).toHaveLength(1);
		expect(list[0].status).toBe('idle');
	});

	it('handles status_changed for non-existent agent gracefully', () => {
		agents.set([mockAgent()]);

		handleAgentEvent({
			type: 'agent.status_changed',
			agent_id: 'non-existent',
			data: { status: 'thinking' }
		});

		const list = get(agents);
		expect(list).toHaveLength(1);
		expect(list[0].status).toBe('idle');
	});

	it('handles destroyed for non-existent agent gracefully', () => {
		agents.set([mockAgent()]);

		handleAgentEvent({
			type: 'agent.destroyed',
			agent_id: 'non-existent',
			data: {}
		});

		const list = get(agents);
		expect(list).toHaveLength(1);
	});
});
