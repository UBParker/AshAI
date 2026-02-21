<script>
	import { pendingApprovals, approve, deny } from '$lib/stores/approvals.js';

	let loading = $state(false);

	// Current approval is the first in the queue
	let current = $derived($pendingApprovals[0] || null);
	let queueLength = $derived($pendingApprovals.length);

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
			<h3>Action Approval Required</h3>
			{#if queueLength > 1}
				<span class="badge">{queueLength} pending</span>
			{/if}
		</div>

		<div class="body">
			<div class="field">
				<span class="label">Tool</span>
				<span class="value tool-name">{current.tool_name}</span>
			</div>

			<div class="field">
				<span class="label">Arguments</span>
				<pre class="args">{JSON.stringify(current.arguments, null, 2)}</pre>
			</div>
		</div>

		<div class="actions">
			<button class="btn deny" onclick={handleDeny} disabled={loading}>
				Deny (Esc)
			</button>
			<button class="btn approve" onclick={handleApprove} disabled={loading}>
				Approve (Enter)
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
		border: 1px solid var(--border);
		border-radius: 12px;
		width: 480px;
		max-width: 90vw;
		max-height: 80vh;
		overflow-y: auto;
	}
	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid var(--border);
	}
	.header h3 {
		font-size: 16px;
		font-weight: 600;
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
	.field {
		margin-bottom: 12px;
	}
	.label {
		display: block;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: var(--text-muted);
		margin-bottom: 4px;
	}
	.tool-name {
		font-size: 16px;
		font-weight: 600;
		color: var(--accent);
	}
	.args {
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 12px;
		font-size: 12px;
		overflow-x: auto;
		white-space: pre-wrap;
		word-break: break-word;
		max-height: 300px;
		overflow-y: auto;
	}
	.actions {
		display: flex;
		gap: 8px;
		padding: 16px 20px;
		border-top: 1px solid var(--border);
		justify-content: flex-end;
	}
	.btn {
		padding: 8px 20px;
		border-radius: 8px;
		font-weight: 600;
		font-size: 13px;
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
		background: var(--error);
		color: #fff;
	}
	.deny:hover:not(:disabled) {
		filter: brightness(1.1);
	}
</style>
