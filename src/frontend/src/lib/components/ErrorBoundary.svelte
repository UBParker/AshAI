<script>
	let { children, fallback = defaultFallback } = $props();

	function defaultFallback(error, reset) {
		return { error, reset };
	}

	let caughtError = $state(null);
	let resetFn = $state(null);

	function handleError(e, reset) {
		console.error('[ErrorBoundary]', e);
		caughtError = e;
		resetFn = reset;
	}
</script>

<svelte:boundary onerror={handleError}>
	{#if caughtError}
		<div class="error-boundary">
			<div class="error-card">
				<h2>Something went wrong</h2>
				<p class="error-message">{caughtError?.message || 'An unexpected error occurred'}</p>
				<details>
					<summary>Error details</summary>
					<pre>{caughtError?.stack || String(caughtError)}</pre>
				</details>
				<button class="retry-btn" onclick={() => { caughtError = null; resetFn?.(); }}>
					Try Again
				</button>
			</div>
		</div>
	{:else}
		{@render children()}
	{/if}
</svelte:boundary>

<style>
	.error-boundary {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24px;
		min-height: 200px;
	}
	.error-card {
		background: var(--bg-secondary, #1a1a1a);
		border: 1px solid var(--error, #e53e3e);
		border-radius: 12px;
		padding: 24px;
		max-width: 500px;
		width: 100%;
	}
	.error-card h2 {
		color: var(--error, #e53e3e);
		margin: 0 0 8px;
		font-size: 18px;
	}
	.error-message {
		color: var(--text-secondary, #999);
		margin: 0 0 16px;
		font-size: 14px;
	}
	details {
		margin-bottom: 16px;
	}
	summary {
		color: var(--text-muted, #666);
		cursor: pointer;
		font-size: 13px;
	}
	pre {
		background: var(--bg-tertiary, #111);
		border-radius: 8px;
		padding: 12px;
		font-size: 12px;
		overflow-x: auto;
		color: var(--text-secondary, #999);
		margin-top: 8px;
	}
	.retry-btn {
		background: var(--accent, #7c5cfc);
		color: white;
		border: none;
		border-radius: 8px;
		padding: 8px 20px;
		font-size: 14px;
		cursor: pointer;
	}
	.retry-btn:hover {
		opacity: 0.9;
	}
</style>
