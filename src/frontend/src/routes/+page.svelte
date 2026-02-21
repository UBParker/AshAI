<script>
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import { clearMessages } from '$lib/stores/chat.js';
	import { onMount } from 'svelte';

	onMount(() => {
		clearMessages();
	});
</script>

<ChatPanel agentId={null} />
