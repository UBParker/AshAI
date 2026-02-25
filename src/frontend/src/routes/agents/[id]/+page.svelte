<script>
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import ErrorBoundary from '$lib/components/ErrorBoundary.svelte';
	import { setMessages, clearMessages, currentAgentId } from '$lib/stores/chat.js';
	import { getThread, getAgent } from '$lib/api/client.js';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	let agentName = $state('Agent');
	let loadError = $state('');

	const agentId = $derived(page.params.id);

	async function loadThread(id) {
		loadError = '';
		try {
			const [agent, thread] = await Promise.all([
				getAgent(id),
				getThread(id)
			]);
			agentName = agent.name;
			currentAgentId.set(id);
			setMessages(thread);
		} catch (e) {
			console.error('Failed to load thread:', e);
			loadError = e.message || 'Failed to load conversation';
			clearMessages();
		}
	}

	$effect(() => {
		if (agentId) {
			loadThread(agentId);
		}
	});

	// Listen for WebSocket message events to refresh thread
	onMount(() => {
		function handleWebSocketMessage(event) {
			if (event.detail?.agent_id === agentId) {
				// Refresh the thread when a message is received for this agent
				loadThread(agentId);
			}
		}

		window.addEventListener('ws:message', handleWebSocketMessage);
		return () => window.removeEventListener('ws:message', handleWebSocketMessage);
	});
</script>

<div class="agent-page">
	<div class="agent-header">
		<span class="agent-name">{agentName}</span>
	</div>
	{#if loadError}
		<div class="load-error">
			<p>{loadError}</p>
			<button onclick={() => loadThread(agentId)}>Retry</button>
		</div>
	{:else}
		<ErrorBoundary>
			<ChatPanel agentId={agentId} />
		</ErrorBoundary>
	{/if}
</div>

<style>
	.agent-page {
		display: flex;
		flex-direction: column;
		flex: 1;
		overflow: hidden;
	}
	.agent-header {
		padding: 10px 20px;
		border-bottom: 1px solid var(--border);
		background: var(--bg-secondary);
	}
	.agent-name {
		font-weight: 600;
	}
	.load-error {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		padding: 40px;
		color: var(--error, #e53e3e);
		font-size: 14px;
	}
	.load-error button {
		padding: 8px 20px;
		background: var(--accent);
		color: white;
		border: none;
		border-radius: 8px;
		cursor: pointer;
	}
</style>
