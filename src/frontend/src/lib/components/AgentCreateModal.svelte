<script>
	import { onMount } from 'svelte';
	import { listProviders, listModels, listTools, createAgent } from '$lib/api/client.js';
	import { refreshAgents } from '$lib/stores/agents.js';

	let { open = false, onClose = () => {} } = $props();

	let name = $state('');
	let role = $state('');
	let goal = $state('');
	let providerName = $state('');
	let modelName = $state('');
	let selectedTools = $state([]);

	let providers = $state([]);
	let models = $state([]);
	let tools = $state([]);
	let loading = $state(false);
	let error = $state('');

	onMount(async () => {
		try {
			const [providerData, toolData] = await Promise.all([
				listProviders(),
				listTools()
			]);
			providers = providerData;
			tools = toolData;
			if (providers.length > 0) {
				const defaultP = providers.find(p => p.is_default) || providers[0];
				providerName = defaultP.name;
				await loadModels(providerName);
			}
		} catch (e) {
			console.error('Failed to load form data:', e);
		}
	});

	async function loadModels(provider) {
		if (!provider) return;
		try {
			const data = await listModels(provider);
			models = data.models || [];
			if (models.length > 0) {
				modelName = models[0];
			}
		} catch {
			models = [];
		}
	}

	function handleProviderChange(e) {
		providerName = e.target.value;
		loadModels(providerName);
	}

	function toggleTool(toolName) {
		if (selectedTools.includes(toolName)) {
			selectedTools = selectedTools.filter(t => t !== toolName);
		} else {
			selectedTools = [...selectedTools, toolName];
		}
	}

	async function handleSubmit() {
		if (!name.trim() || !role.trim()) return;
		loading = true;
		error = '';
		try {
			await createAgent({
				name: name.trim(),
				role: role.trim(),
				goal: goal.trim(),
				provider_name: providerName,
				model_name: modelName,
				tool_names: selectedTools
			});
			await refreshAgents();
			onClose();
			// Reset form
			name = '';
			role = '';
			goal = '';
			selectedTools = [];
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
<div class="overlay" onclick={onClose}>
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<h3>Create New Agent</h3>
			<button class="close-btn" onclick={onClose}>&times;</button>
		</div>

		<form class="modal-body" onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
			<div class="field">
				<label for="agent-name">Name</label>
				<input id="agent-name" type="text" bind:value={name} placeholder="e.g. CodeBot" required />
			</div>

			<div class="field">
				<label for="agent-role">Role (System Prompt)</label>
				<textarea id="agent-role" bind:value={role} placeholder="You are a coding assistant..." rows="3" required></textarea>
			</div>

			<div class="field">
				<label for="agent-goal">Goal</label>
				<input id="agent-goal" type="text" bind:value={goal} placeholder="Help with Python development" />
			</div>

			<div class="row">
				<div class="field flex-1">
					<label for="provider">Provider</label>
					<select id="provider" value={providerName} onchange={handleProviderChange}>
						{#each providers as p}
							<option value={p.name}>{p.name}{p.is_default ? ' (default)' : ''}</option>
						{/each}
					</select>
				</div>

				<div class="field flex-1">
					<label for="model">Model</label>
					<select id="model" bind:value={modelName}>
						{#each models as m}
							<option value={m}>{m}</option>
						{/each}
					</select>
				</div>
			</div>

			<div class="field">
				<label>Tools</label>
				<div class="tool-grid">
					{#each tools as tool}
						<label class="tool-checkbox">
							<input
								type="checkbox"
								checked={selectedTools.includes(tool.name)}
								onchange={() => toggleTool(tool.name)}
							/>
							<span class="tool-label">
								{tool.name}
								{#if tool.requires_approval}
									<span class="approval-badge" title="Requires approval">!</span>
								{/if}
							</span>
						</label>
					{/each}
				</div>
			</div>

			{#if error}
				<div class="error">{error}</div>
			{/if}

			<div class="actions">
				<button type="button" class="btn cancel" onclick={onClose}>Cancel</button>
				<button type="submit" class="btn submit" disabled={loading || !name.trim() || !role.trim()}>
					{loading ? 'Creating...' : 'Create Agent'}
				</button>
			</div>
		</form>
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
		z-index: 999;
	}
	.modal {
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 12px;
		width: 520px;
		max-width: 90vw;
		max-height: 85vh;
		overflow-y: auto;
	}
	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid var(--border);
	}
	.modal-header h3 {
		font-size: 16px;
		font-weight: 600;
	}
	.close-btn {
		font-size: 24px;
		color: var(--text-muted);
		padding: 0 4px;
	}
	.close-btn:hover {
		color: var(--text-primary);
	}
	.modal-body {
		padding: 16px 20px;
	}
	.field {
		margin-bottom: 14px;
	}
	.field label {
		display: block;
		font-size: 12px;
		font-weight: 600;
		margin-bottom: 4px;
		color: var(--text-secondary);
	}
	.field input, .field textarea, .field select {
		width: 100%;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 8px 12px;
		outline: none;
	}
	.field input:focus, .field textarea:focus, .field select:focus {
		border-color: var(--accent);
	}
	.row {
		display: flex;
		gap: 12px;
	}
	.flex-1 {
		flex: 1;
	}
	.tool-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
	}
	.tool-checkbox {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 13px;
		cursor: pointer;
		padding: 4px;
		border-radius: 4px;
	}
	.tool-checkbox:hover {
		background: var(--bg-hover);
	}
	.tool-label {
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.approval-badge {
		background: var(--warning);
		color: #000;
		font-size: 9px;
		font-weight: 700;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}
	.error {
		color: var(--error);
		font-size: 13px;
		margin-bottom: 12px;
	}
	.actions {
		display: flex;
		gap: 8px;
		justify-content: flex-end;
		padding-top: 8px;
		border-top: 1px solid var(--border);
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
	.cancel {
		background: var(--bg-tertiary);
	}
	.cancel:hover {
		background: var(--bg-hover);
	}
	.submit {
		background: var(--accent);
		color: #fff;
	}
	.submit:hover:not(:disabled) {
		background: var(--accent-hover);
	}
</style>
