<script>
	import AgentManager from '$lib/components/AgentManager.svelte';
	import ErrorBoundary from '$lib/components/ErrorBoundary.svelte';
</script>

<svelte:head>
	<title>Agent Manager - AshAI</title>
</svelte:head>

<div class="page-container">
	<ErrorBoundary>
		<AgentManager />
	</ErrorBoundary>
</div>

<style>
	.page-container {
		height: 100vh;
		overflow: hidden;
	}
</style>