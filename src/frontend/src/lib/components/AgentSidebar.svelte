<script>
	import { agents } from '$lib/stores/agents.js';
	import AgentCreateModal from './AgentCreateModal.svelte';

	let { visible = true, currentAgentId = null, onSelectAgent = () => {}, children } = $props();
	let showCreateModal = $state(false);

	const statusColors = {
		running: 'var(--success)',
		idle: 'var(--accent)',
		error: 'var(--error)',
		waiting_for_user: 'var(--warning)',
		completed: 'var(--text-muted)',
		created: 'var(--text-muted)',
	};
</script>

{#if visible}
<aside class="sidebar">
	<div class="section-header">
		<span class="section-label">Agents</span>
		<button class="new-agent-btn" onclick={() => showCreateModal = true} title="Create new agent">
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<line x1="12" y1="5" x2="12" y2="19"/>
				<line x1="5" y1="12" x2="19" y2="12"/>
			</svg>
		</button>
	</div>
	<ul class="agent-list">
		{#each $agents as agent (agent.id)}
			<li>
				<button
					class="agent-item"
					class:active={currentAgentId === agent.id}
					onclick={() => onSelectAgent(agent.id)}
				>
					<span
						class="status-dot"
						class:pulse={agent.status === 'waiting_for_user'}
						style="background: {statusColors[agent.status] || 'var(--text-muted)'}"
					></span>
					<span class="agent-name">{agent.name}</span>
					<span class="agent-status">{agent.status}</span>
				</button>
			</li>
		{/each}
	</ul>
	{#if children}
		{@render children()}
	{/if}
</aside>
{/if}

<AgentCreateModal open={showCreateModal} onClose={() => showCreateModal = false} />

<style>
	.sidebar {
		width: var(--sidebar-width);
		height: 100%;
		background: var(--bg-secondary);
		border-right: 1px solid var(--border);
		overflow-y: auto;
		flex-shrink: 0;
	}
	.section-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 16px 8px;
	}
	.section-label {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: var(--text-muted);
		font-weight: 600;
	}
	.new-agent-btn {
		width: 28px;
		height: 28px;
		border-radius: 6px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted);
	}
	.new-agent-btn:hover {
		background: var(--bg-hover);
		color: var(--accent);
	}
	.agent-list {
		list-style: none;
	}
	.agent-item {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 16px;
		text-align: left;
		border-radius: 0;
	}
	.agent-item:hover {
		background: var(--bg-hover);
	}
	.agent-item.active {
		background: var(--bg-tertiary);
	}
	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.status-dot.pulse {
		animation: pulse-glow 1.5s ease-in-out infinite;
	}
	@keyframes pulse-glow {
		0%, 100% {
			box-shadow: 0 0 0 0 var(--warning);
			opacity: 1;
		}
		50% {
			box-shadow: 0 0 8px 3px var(--warning);
			opacity: 0.7;
		}
	}
	.agent-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.agent-status {
		font-size: 11px;
		color: var(--text-muted);
	}
</style>
