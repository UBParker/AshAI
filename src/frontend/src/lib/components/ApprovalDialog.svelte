<script>
	import { pendingApprovals, approve, deny } from '$lib/stores/approvals.js';

	let loading = $state(false);

	// Current approval is the first in the queue
	let current = $derived($pendingApprovals[0] || null);
	let queueLength = $derived($pendingApprovals.length);

	/**
	 * Parse arguments — may be a JSON string, an object, or something else.
	 * Returns a list of { key, value } pairs for display.
	 */
	function parseArgs(args) {
		if (!args) return [];
		let obj = args;
		if (typeof args === 'string') {
			try { obj = JSON.parse(args); } catch { return [{ key: null, value: args }]; }
		}
		if (typeof obj !== 'object' || obj === null) {
			return [{ key: null, value: String(obj) }];
		}
		return Object.entries(obj).map(([key, value]) => ({
			key,
			value: typeof value === 'string' ? value : JSON.stringify(value, null, 2)
		}));
	}

	let parsedArgs = $derived(parseArgs(current?.arguments));

	async function handleApprove() {
		if (!current || loading) return;
		loading = true;
		try {
			await approve(current.id);
		} finally {
			loading = false;
		}
	}

	async function handleDeny() {
		if (!current || loading) return;
		loading = true;
		try {
			await deny(current.id);
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e) {
		if (!current) return;
		if (e.key === 'Enter') {
			e.preventDefault();
			handleApprove();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			handleDeny();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if current}
<div class="overlay">
	<div class="dialog">
		<div class="header">
			<div class="header-left">
				<span class="shield">&#x26A0;</span>
				<h3>Approval Required</h3>
			</div>
			{#if queueLength > 1}
				<span class="badge">{queueLength} pending</span>
			{/if}
		</div>

		<div class="body">
			<div class="tool-banner">
				<span class="tool-label">Tool</span>
				<span class="tool-name">{current.tool_name}</span>
			</div>

			{#if parsedArgs.length > 0}
				<div class="args-section">
					{#each parsedArgs as { key, value }}
						<div class="arg-row">
							{#if key}
								<span class="arg-key">{key}</span>
							{/if}
							<pre class="arg-value">{value}</pre>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<div class="actions">
			<button class="btn deny" onclick={handleDeny} disabled={loading}>
				Deny <kbd>Esc</kbd>
			</button>
			<button class="btn approve" onclick={handleApprove} disabled={loading}>
				Approve <kbd>Enter</kbd>
			</button>
		</div>
	</div>
</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}
	.dialog {
		background: var(--bg-secondary);
		border: 1px solid var(--warning);
		border-radius: 12px;
		width: 520px;
		max-width: 90vw;
		max-height: 80vh;
		overflow-y: auto;
		box-shadow: 0 0 30px rgba(255, 152, 0, 0.1);
	}
	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 14px 20px;
		border-bottom: 1px solid var(--border);
	}
	.header-left {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.shield {
		font-size: 18px;
		line-height: 1;
	}
	.header h3 {
		font-size: 15px;
		font-weight: 600;
		color: var(--text-primary);
	}
	.badge {
		background: var(--warning);
		color: #000;
		font-size: 11px;
		padding: 2px 8px;
		border-radius: 10px;
		font-weight: 600;
	}
	.body {
		padding: 16px 20px;
	}
	.tool-banner {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 14px;
		background: var(--bg-tertiary);
		border-radius: 8px;
		margin-bottom: 14px;
	}
	.tool-label {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: var(--text-muted);
		flex-shrink: 0;
	}
	.tool-name {
		font-size: 15px;
		font-weight: 700;
		color: var(--accent);
		font-family: 'SF Mono', 'Fira Code', monospace;
	}
	.args-section {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.arg-row {
		border-left: 3px solid var(--border);
		padding-left: 12px;
	}
	.arg-key {
		display: block;
		font-size: 11px;
		font-weight: 600;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.3px;
		margin-bottom: 2px;
	}
	.arg-value {
		margin: 0;
		font-size: 13px;
		font-family: 'SF Mono', 'Fira Code', monospace;
		color: var(--text-primary);
		white-space: pre-wrap;
		word-break: break-word;
		line-height: 1.5;
		max-height: 200px;
		overflow-y: auto;
	}
	.actions {
		display: flex;
		gap: 10px;
		padding: 14px 20px;
		border-top: 1px solid var(--border);
		justify-content: flex-end;
	}
	.btn {
		padding: 8px 24px;
		border-radius: 8px;
		font-weight: 600;
		font-size: 13px;
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}
	.btn kbd {
		font-size: 10px;
		padding: 1px 5px;
		border-radius: 3px;
		background: rgba(255, 255, 255, 0.15);
		font-family: inherit;
	}
	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.approve {
		background: var(--success);
		color: #fff;
	}
	.approve:hover:not(:disabled) {
		filter: brightness(1.1);
	}
	.deny {
		background: var(--bg-tertiary);
		color: var(--text-secondary);
		border: 1px solid var(--border);
	}
	.deny:hover:not(:disabled) {
		background: var(--bg-hover);
		color: var(--text-primary);
	}
</style>
