<script>
	import { onMount, onDestroy } from 'svelte';
	import { agents } from '$lib/stores/agents.js';
	import {
		listAgents,
		sendMessage,
		createAgent,
		updateAgent,
		destroyAgent,
		listTools,
		listProviders,
		listModels
	} from '$lib/api/client.js';
	import AgentCreateModal from './AgentCreateModal.svelte';

	let showCreateModal = $state(false);
	let selectedAgentId = $state(null);
	let messageInput = $state('');
	let selectedAgent = $derived(selectedAgentId ? $agents.find(a => a.id === selectedAgentId) : null);
	let agentMessages = $state({});
	let loading = $state(false);
	let availableTools = $state([]);
	let providers = $state([]);
	let models = $state([]);

	// Edit mode states
	let editMode = $state(false);
	let editForm = $state({
		name: '',
		role: '',
		goal: '',
		provider_name: '',
		model_name: '',
		tool_names: [],
		parent_id: ''
	});
	let saving = $state(false);
	let deleteConfirm = $state(false);

	onMount(async () => {
		await refreshAgents();
		// Load available tools and providers
		try {
			const [toolsData, providersData] = await Promise.all([
				listTools(),
				listProviders()
			]);
			availableTools = toolsData;
			providers = providersData;
		} catch (e) {
			console.error('Failed to load tools/providers:', e);
		}
	});

	async function refreshAgents() {
		try {
			const data = await listAgents();
			agents.set(data);
		} catch (e) {
			console.error('Failed to refresh agents:', e);
		}
	}

	async function selectAgent(agentId) {
		selectedAgentId = agentId;
		editMode = false;
		deleteConfirm = false;

		if (!agentMessages[agentId]) {
			agentMessages[agentId] = [];
		}

		// Load models for the agent's provider
		if (selectedAgent?.provider_name) {
			await loadModels(selectedAgent.provider_name);
		}
	}

	async function loadModels(providerName) {
		try {
			const data = await listModels(providerName);
			models = data.models || [];
		} catch (e) {
			console.error('Failed to load models:', e);
			models = [];
		}
	}

	function startEdit() {
		if (!selectedAgent) return;

		editForm = {
			name: selectedAgent.name,
			role: selectedAgent.role,
			goal: selectedAgent.goal || '',
			provider_name: selectedAgent.provider_name,
			model_name: selectedAgent.model_name || '',
			tool_names: [...(selectedAgent.tool_names || [])],
			parent_id: selectedAgent.parent_id || ''
		};
		editMode = true;
	}

	function cancelEdit() {
		editMode = false;
	}

	async function saveEdit() {
		if (!selectedAgent) return;

		saving = true;
		try {
			await updateAgent(selectedAgent.id, editForm);
			await refreshAgents();
			editMode = false;
		} catch (e) {
			console.error('Failed to update agent:', e);
			alert('Failed to update agent: ' + e.message);
		} finally {
			saving = false;
		}
	}

	function toggleTool(toolName) {
		if (editForm.tool_names.includes(toolName)) {
			editForm.tool_names = editForm.tool_names.filter(t => t !== toolName);
		} else {
			editForm.tool_names = [...editForm.tool_names, toolName];
		}
	}

	async function handleProviderChange(e) {
		editForm.provider_name = e.target.value;
		await loadModels(editForm.provider_name);
		if (models.length > 0) {
			editForm.model_name = models[0];
		}
	}

	async function deleteAgent() {
		if (!selectedAgent || !deleteConfirm) {
			deleteConfirm = true;
			return;
		}

		try {
			await destroyAgent(selectedAgent.id);
			selectedAgentId = null;
			await refreshAgents();
		} catch (e) {
			console.error('Failed to delete agent:', e);
			alert('Failed to delete agent: ' + e.message);
		}
		deleteConfirm = false;
	}

	async function sendMessageToAgent() {
		if (!selectedAgentId || !messageInput.trim()) return;

		const msg = messageInput.trim();
		messageInput = '';

		// Add user message to history
		agentMessages[selectedAgentId] = [
			...agentMessages[selectedAgentId],
			{ role: 'user', content: msg, timestamp: new Date() }
		];

		loading = true;
		try {
			// Send message and get response
			const response = await sendMessage(selectedAgentId, msg);

			// Add agent response to history
			agentMessages[selectedAgentId] = [
				...agentMessages[selectedAgentId],
				{ role: 'assistant', content: response, timestamp: new Date() }
			];
		} catch (e) {
			agentMessages[selectedAgentId] = [
				...agentMessages[selectedAgentId],
				{ role: 'error', content: `Error: ${e.message}`, timestamp: new Date() }
			];
		} finally {
			loading = false;
			await refreshAgents();
		}
	}

	function getStatusColor(status) {
		switch (status) {
			case 'idle': return 'var(--success)';
			case 'running': return 'var(--warning)';
			case 'error': return 'var(--error)';
			default: return 'var(--text-muted)';
		}
	}

	function getStatusIcon(status) {
		switch (status) {
			case 'idle': return '●';
			case 'running': return '◉';
			case 'error': return '✕';
			default: return '○';
		}
	}

	// Check if this is Ash (master agent)
	let isAsh = $derived(selectedAgent && !selectedAgent.parent_id);
</script>

<div class="agent-manager">
	<div class="sidebar">
		<div class="sidebar-header">
			<h2>Agents</h2>
			<button class="create-btn" onclick={() => showCreateModal = true}>
				+ Create Agent
			</button>
		</div>

		<div class="agent-list">
			{#each $agents as agent}
				<div
					class="agent-item {selectedAgentId === agent.id ? 'selected' : ''}"
					onclick={() => selectAgent(agent.id)}
				>
					<span class="status-icon" style="color: {getStatusColor(agent.status)}">
						{getStatusIcon(agent.status)}
					</span>
					<div class="agent-info">
						<div class="agent-name">{agent.name}</div>
						<div class="agent-meta">
							<span class="agent-status">{agent.status}</span>
							{#if agent.tool_names?.length > 0}
								<span class="tool-count">{agent.tool_names.length} tools</span>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>
	</div>

	<div class="main-panel">
		{#if selectedAgent}
			<div class="agent-details">
				<div class="agent-header">
					<div class="agent-title">
						{#if editMode}
							<input
								class="edit-name"
								bind:value={editForm.name}
								placeholder="Agent name"
							/>
						{:else}
							<h3>{selectedAgent.name}</h3>
						{/if}
						<span class="status-badge" style="background: {getStatusColor(selectedAgent.status)}">
							{selectedAgent.status}
						</span>
					</div>

					<div class="agent-actions">
						{#if !isAsh}
							{#if editMode}
								<button class="btn save-btn" onclick={saveEdit} disabled={saving}>
									{saving ? 'Saving...' : 'Save'}
								</button>
								<button class="btn cancel-btn" onclick={cancelEdit}>
									Cancel
								</button>
							{:else}
								<button class="btn edit-btn" onclick={startEdit}>
									Edit
								</button>
								{#if deleteConfirm}
									<button class="btn delete-btn confirm" onclick={deleteAgent}>
										Confirm Delete?
									</button>
									<button class="btn cancel-btn" onclick={() => deleteConfirm = false}>
										Cancel
									</button>
								{:else}
									<button class="btn delete-btn" onclick={deleteAgent}>
										Delete
									</button>
								{/if}
							{/if}
						{:else}
							<span class="master-badge">Master Agent</span>
						{/if}
					</div>
				</div>

				{#if editMode}
					<div class="edit-form">
						<div class="form-group">
							<label>Role (System Prompt)</label>
							<textarea
								bind:value={editForm.role}
								placeholder="Define the agent's role and capabilities..."
								rows="4"
							></textarea>
						</div>

						<div class="form-group">
							<label>Goal</label>
							<input
								bind:value={editForm.goal}
								placeholder="What is this agent's primary objective?"
							/>
						</div>

						<div class="form-group">
							<label>Parent Agent</label>
							<select bind:value={editForm.parent_id}>
								<option value="">No parent (Master agent)</option>
								{#each $agents.filter(a => a.id !== selectedAgent.id) as agent}
									<option value={agent.id}>{agent.name}</option>
								{/each}
							</select>
							<small class="hint">Changing parent affects edit permissions</small>
						</div>

						<div class="form-row">
							<div class="form-group">
								<label>Provider</label>
								<select value={editForm.provider_name} onchange={handleProviderChange}>
									{#each providers as provider}
										<option value={provider.name}>
											{provider.name}{provider.is_default ? ' (default)' : ''}
										</option>
									{/each}
								</select>
							</div>

							<div class="form-group">
								<label>Model</label>
								<select bind:value={editForm.model_name}>
									<option value="">Default</option>
									{#each models as model}
										<option value={model}>{model}</option>
									{/each}
								</select>
							</div>
						</div>

						<div class="form-group">
							<label>Tools ({editForm.tool_names.length} selected)</label>
							<div class="tool-grid">
								{#each availableTools as tool}
									<button
										type="button"
										class="tool-checkbox {editForm.tool_names.includes(tool.name) ? 'selected' : ''}"
										onclick={() => toggleTool(tool.name)}
									>
										<span class="tool-checkbox-icon">
											{editForm.tool_names.includes(tool.name) ? '✓' : ''}
										</span>
										<span class="tool-label">
											{tool.name}
											{#if tool.requires_approval}
												<span class="approval-badge" title="Requires approval">!</span>
											{/if}
										</span>
									</button>
								{/each}
							</div>
							{#if availableTools.length === 0}
								<p class="no-tools">Loading tools...</p>
							{/if}
						</div>
					</div>
				{:else}
					<div class="agent-config">
						<div class="config-row">
							<label>Provider:</label>
							<span>{selectedAgent.provider_name}</span>
						</div>
						<div class="config-row">
							<label>Model:</label>
							<span>{selectedAgent.model_name || 'default'}</span>
						</div>
						{#if selectedAgent.goal}
							<div class="config-row">
								<label>Goal:</label>
								<span>{selectedAgent.goal}</span>
							</div>
						{/if}
						{#if selectedAgent.role}
							<div class="config-row">
								<label>Role:</label>
								<div class="role-text">{selectedAgent.role}</div>
							</div>
						{/if}
					</div>

					<div class="tools-section">
						<div class="tools-header">
							<h4>Tools ({selectedAgent.tool_names?.length || 0})</h4>
							{#if !isAsh}
								<button class="edit-tools-btn" onclick={startEdit} title="Edit tools">
									<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
										<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
										<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
									</svg>
								</button>
							{/if}
						</div>
						{#if selectedAgent.tool_names?.length > 0}
							<div class="tool-list">
								{#each selectedAgent.tool_names as toolName}
									{@const tool = availableTools.find(t => t.name === toolName)}
									<div class="tool-item" title={tool?.description || ''}>
										<span class="tool-name">{toolName}</span>
										{#if tool?.requires_approval}
											<span class="approval-icon" title="Requires approval">!</span>
										{/if}
									</div>
								{/each}
							</div>
						{:else}
							<p class="no-tools-message">No tools assigned. Click Edit to add tools.</p>
						{/if}
					</div>
				{/if}

				<div class="chat-section">
					<h4>Message Agent</h4>
					<div class="message-history">
						{#each agentMessages[selectedAgent.id] || [] as msg}
							<div class="message {msg.role}">
								<div class="message-role">{msg.role}</div>
								<div class="message-content">{msg.content}</div>
							</div>
						{/each}
						{#if loading}
							<div class="message thinking">
								<div class="message-role">thinking</div>
								<div class="message-content">...</div>
							</div>
						{/if}
					</div>

					<div class="message-input-container">
						<textarea
							class="message-input"
							bind:value={messageInput}
							placeholder="Send a message to {selectedAgent.name}..."
							onkeydown={(e) => {
								if (e.key === 'Enter' && !e.shiftKey) {
									e.preventDefault();
									sendMessageToAgent();
								}
							}}
							disabled={loading || editMode}
						></textarea>
						<button
							class="send-btn"
							onclick={sendMessageToAgent}
							disabled={loading || !messageInput.trim() || editMode}
						>
							Send
						</button>
					</div>
				</div>
			</div>
		{:else}
			<div class="empty-state">
				<p>Select an agent to view details and send messages</p>
			</div>
		{/if}
	</div>
</div>

<AgentCreateModal
	open={showCreateModal}
	onClose={() => {
		showCreateModal = false;
		refreshAgents();
	}}
/>

<style>
	.agent-manager {
		display: flex;
		height: 100%;
		background: var(--bg-primary);
	}

	.sidebar {
		width: 280px;
		background: var(--bg-secondary);
		border-right: 1px solid var(--border);
		display: flex;
		flex-direction: column;
	}

	.sidebar-header {
		padding: 16px;
		border-bottom: 1px solid var(--border);
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.sidebar-header h2 {
		font-size: 18px;
		font-weight: 600;
	}

	.create-btn {
		background: var(--accent);
		color: white;
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 13px;
		font-weight: 600;
	}

	.create-btn:hover {
		background: var(--accent-hover);
	}

	.agent-list {
		flex: 1;
		overflow-y: auto;
	}

	.agent-item {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 16px;
		cursor: pointer;
		border-bottom: 1px solid var(--border);
	}

	.agent-item:hover {
		background: var(--bg-hover);
	}

	.agent-item.selected {
		background: var(--bg-tertiary);
	}

	.status-icon {
		font-size: 12px;
	}

	.agent-info {
		flex: 1;
	}

	.agent-name {
		font-weight: 600;
		font-size: 14px;
	}

	.agent-meta {
		display: flex;
		gap: 8px;
		margin-top: 2px;
	}

	.agent-status,
	.tool-count {
		font-size: 11px;
		color: var(--text-muted);
	}

	.main-panel {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.agent-details {
		padding: 24px;
		height: 100%;
		overflow-y: auto;
	}

	.agent-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	.agent-title {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.agent-title h3 {
		font-size: 20px;
		font-weight: 600;
	}

	.edit-name {
		font-size: 20px;
		font-weight: 600;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 4px 8px;
	}

	.status-badge {
		padding: 4px 8px;
		border-radius: 4px;
		font-size: 12px;
		font-weight: 600;
		color: white;
	}

	.master-badge {
		padding: 4px 8px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 4px;
		font-size: 12px;
		color: var(--text-muted);
	}

	.agent-actions {
		display: flex;
		gap: 8px;
	}

	.btn {
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.edit-btn {
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
	}

	.edit-btn:hover {
		background: var(--bg-hover);
	}

	.save-btn {
		background: var(--success);
		color: white;
	}

	.cancel-btn {
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
	}

	.delete-btn {
		background: var(--bg-tertiary);
		color: var(--error);
		border: 1px solid var(--border);
	}

	.delete-btn.confirm {
		background: var(--error);
		color: white;
	}

	.edit-form {
		background: var(--bg-secondary);
		padding: 20px;
		border-radius: 8px;
		margin-bottom: 20px;
	}

	.form-group {
		margin-bottom: 16px;
	}

	.form-group label {
		display: block;
		font-size: 12px;
		font-weight: 600;
		margin-bottom: 6px;
		color: var(--text-secondary);
	}

	.form-group input,
	.form-group textarea,
	.form-group select {
		width: 100%;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 8px 12px;
		font-size: 14px;
	}

	.form-group textarea {
		resize: vertical;
		font-family: inherit;
		line-height: 1.5;
	}

	.form-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}

	.tool-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 8px;
	}

	.tool-checkbox {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 8px 10px;
		background: var(--bg-tertiary);
		border: 2px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
		font-size: 13px;
		transition: all 0.2s;
		text-align: left;
		width: 100%;
		color: var(--text-primary);
	}

	.tool-checkbox:hover {
		background: var(--bg-hover);
		border-color: var(--accent);
	}

	.tool-checkbox.selected {
		background: var(--accent);
		border-color: var(--accent);
		color: white;
	}

	.tool-checkbox.selected .approval-badge {
		background: white;
		color: var(--warning);
	}

	.tool-label {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.tool-checkbox-icon {
		width: 16px;
		height: 16px;
		border: 2px solid currentColor;
		border-radius: 3px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 12px;
		font-weight: bold;
		flex-shrink: 0;
	}

	.approval-badge {
		background: var(--warning);
		color: black;
		font-size: 10px;
		font-weight: 700;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.no-tools {
		color: var(--text-muted);
		font-style: italic;
		font-size: 13px;
		padding: 10px;
		text-align: center;
		background: var(--bg-tertiary);
		border-radius: 6px;
	}

	.agent-config {
		background: var(--bg-secondary);
		padding: 16px;
		border-radius: 8px;
		margin-bottom: 20px;
	}

	.config-row {
		display: flex;
		gap: 12px;
		margin-bottom: 12px;
		font-size: 14px;
	}

	.config-row:last-child {
		margin-bottom: 0;
	}

	.config-row label {
		font-weight: 600;
		color: var(--text-muted);
		min-width: 80px;
	}

	.role-text {
		white-space: pre-wrap;
		line-height: 1.5;
		color: var(--text-secondary);
	}

	.tools-section {
		margin-bottom: 20px;
	}

	.tools-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;
	}

	.tools-section h4 {
		font-size: 14px;
		font-weight: 600;
		color: var(--text-secondary);
	}

	.edit-tools-btn {
		padding: 4px 8px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		color: var(--text-muted);
		transition: all 0.2s;
	}

	.edit-tools-btn:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}

	.no-tools-message {
		color: var(--text-muted);
		font-style: italic;
		font-size: 13px;
		padding: 12px;
		background: var(--bg-tertiary);
		border: 1px dashed var(--border);
		border-radius: 6px;
		text-align: center;
	}

	.tool-list {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.tool-item {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 4px 10px;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 6px;
		font-size: 13px;
	}

	.approval-icon {
		background: var(--warning);
		color: black;
		font-size: 10px;
		font-weight: 700;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.chat-section {
		flex: 1;
		display: flex;
		flex-direction: column;
	}

	.chat-section h4 {
		font-size: 14px;
		font-weight: 600;
		margin-bottom: 12px;
		color: var(--text-secondary);
	}

	.message-history {
		flex: 1;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 16px;
		overflow-y: auto;
		margin-bottom: 12px;
		min-height: 200px;
		max-height: 400px;
	}

	.message {
		margin-bottom: 16px;
	}

	.message:last-child {
		margin-bottom: 0;
	}

	.message-role {
		font-size: 11px;
		font-weight: 600;
		color: var(--text-muted);
		margin-bottom: 4px;
		text-transform: uppercase;
	}

	.message.user .message-role {
		color: var(--accent);
	}

	.message.assistant .message-role {
		color: var(--success);
	}

	.message.error .message-role {
		color: var(--error);
	}

	.message-content {
		font-size: 14px;
		line-height: 1.5;
		white-space: pre-wrap;
	}

	.message.thinking .message-content {
		color: var(--text-muted);
		font-style: italic;
	}

	.message-input-container {
		display: flex;
		gap: 12px;
	}

	.message-input {
		flex: 1;
		min-height: 80px;
		padding: 12px;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 8px;
		resize: vertical;
		font-size: 14px;
	}

	.message-input:focus {
		outline: none;
		border-color: var(--accent);
	}

	.send-btn {
		padding: 12px 24px;
		background: var(--accent);
		color: white;
		border-radius: 8px;
		font-weight: 600;
		align-self: flex-end;
	}

	.send-btn:hover:not(:disabled) {
		background: var(--accent-hover);
	}

	.send-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.empty-state {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: var(--text-muted);
		font-size: 14px;
	}
</style>