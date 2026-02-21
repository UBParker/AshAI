<script>
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import { setMessages, clearMessages } from '$lib/stores/chat.js';
	import { getThread, getAgent } from '$lib/api/client.js';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	let agentName = $state('Agent');

	const agentId = $derived(page.params.id);

	async function loadThread(id) {
		try {
			const [agent, thread] = await Promise.all([
				getAgent(id),
				getThread(id)
			]);
			agentName = agent.name;
			setMessages(thread);
		} catch (e) {
			console.error('Failed to load thread:', e);
			clearMessages();
		}
	}

	$effect(() => {
		if (agentId) {
			loadThread(agentId);
		}
	});
</script>

<div class="agent-page">
	<div class="agent-header">
		<span class="agent-name">{agentName}</span>
	</div>
	<ChatPanel agentId={agentId} />
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
</style>
