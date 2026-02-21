<script>
	let { toolCall } = $props();
	let expanded = $state(false);

	function toggle() {
		expanded = !expanded;
	}

	let argsFormatted = $derived(
		(() => {
			try {
				const parsed = typeof toolCall.arguments === 'string'
					? JSON.parse(toolCall.arguments)
					: toolCall.arguments;
				return JSON.stringify(parsed, null, 2);
			} catch {
				return toolCall.arguments || '{}';
			}
		})()
	);

	let resultFormatted = $derived(
		(() => {
			if (!toolCall.result) return null;
			try {
				const parsed = typeof toolCall.result === 'string'
					? JSON.parse(toolCall.result)
					: toolCall.result;
				return JSON.stringify(parsed, null, 2);
			} catch {
				return toolCall.result;
			}
		})()
	);
</script>

<div class="tool-block">
	<button class="tool-header" onclick={toggle}>
		<span class="tool-icon">
			{#if toolCall.status === 'running'}
				<span class="spinner"></span>
			{:else if toolCall.status === 'done'}
				<span class="check">&#10003;</span>
			{:else if toolCall.status === 'error'}
				<span class="error-icon">&#10007;</span>
			{:else}
				<span class="dot">&#9679;</span>
			{/if}
		</span>
		<span class="tool-name">{toolCall.name}</span>
		<span class="expand-arrow">{expanded ? '&#9660;' : '&#9654;'}</span>
	</button>

	{#if expanded}
		<div class="tool-details">
			<div class="detail-section">
				<span class="detail-label">Arguments</span>
				<pre class="detail-content">{argsFormatted}</pre>
			</div>
			{#if resultFormatted}
				<div class="detail-section">
					<span class="detail-label">Result</span>
					<pre class="detail-content">{resultFormatted}</pre>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.tool-block {
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		margin: 6px 0;
		overflow: hidden;
	}
	.tool-header {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 8px 12px;
		text-align: left;
		font-size: 13px;
	}
	.tool-header:hover {
		background: var(--bg-hover);
	}
	.tool-name {
		flex: 1;
		font-weight: 600;
		color: var(--accent);
	}
	.expand-arrow {
		font-size: 10px;
		color: var(--text-muted);
	}
	.spinner {
		display: inline-block;
		width: 12px;
		height: 12px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	.check {
		color: var(--success);
		font-size: 14px;
	}
	.error-icon {
		color: var(--error);
		font-size: 14px;
	}
	.dot {
		color: var(--text-muted);
		font-size: 8px;
	}
	.tool-details {
		border-top: 1px solid var(--border);
		padding: 8px 12px;
	}
	.detail-section {
		margin-bottom: 8px;
	}
	.detail-section:last-child {
		margin-bottom: 0;
	}
	.detail-label {
		display: block;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: var(--text-muted);
		margin-bottom: 4px;
	}
	.detail-content {
		background: var(--bg-primary);
		border-radius: 6px;
		padding: 8px;
		font-size: 11px;
		overflow-x: auto;
		white-space: pre-wrap;
		word-break: break-word;
		max-height: 200px;
		overflow-y: auto;
	}
</style>
