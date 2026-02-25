<script>
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import { setMessages, clearMessages, currentAgentId } from '$lib/stores/chat.js';
	import { agents } from '$lib/stores/agents.js';
	import { getThread } from '$lib/api/client.js';
	import { get } from 'svelte/store';
	import { onMount } from 'svelte';

	let eveId = $state(null);

	async function loadEveThread() {
		// Find Eve (agent with no parent)
		const allAgents = get(agents);
		const eve = allAgents.find(a => a.parent_id === null);
		if (!eve) return;
		eveId = eve.id;
		try {
			const thread = await getThread(eve.id);
			setMessages(thread);
		} catch (e) {
			console.error('Failed to load Eve thread:', e);
		}
	}

	onMount(() => {
		// Only clear if switching from an agent context to Eve
		const prevAgent = get(currentAgentId);
		if (prevAgent !== null) {
			clearMessages();
		}
		currentAgentId.set(null);
		loadEveThread();

		// Refresh thread when stream finishes (e.g. sub-agent report)
		function handleStreamEnd(event) {
			if (eveId && event.detail?.agent_id === eveId) {
				loadEveThread();
			}
		}
		function handleMessage(event) {
			if (eveId && event.detail?.agent_id === eveId) {
				loadEveThread();
			}
		}

		window.addEventListener('ws:stream_end', handleStreamEnd);
		window.addEventListener('ws:message', handleMessage);
		return () => {
			window.removeEventListener('ws:stream_end', handleStreamEnd);
			window.removeEventListener('ws:message', handleMessage);
		};
	});
</script>

<ChatPanel agentId={null} />
