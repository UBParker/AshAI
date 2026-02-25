<script>
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import { clearMessages, currentAgentId } from '$lib/stores/chat.js';
	import { get } from 'svelte/store';
	import { onMount } from 'svelte';

	onMount(() => {
		// Only clear if switching from an agent context to Eve
		const prevAgent = get(currentAgentId);
		if (prevAgent !== null) {
			clearMessages();
		}
		currentAgentId.set(null);
	});
</script>

<ChatPanel agentId={null} />
