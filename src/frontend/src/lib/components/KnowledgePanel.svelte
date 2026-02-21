<script>
	import { onMount } from 'svelte';
	import { listKnowledge, addKnowledge, updateKnowledge, deleteKnowledge } from '$lib/api/client.js';
	import { currentUser } from '$lib/auth.js';

	let { onClose = () => {} } = $props();

	let entries = $state([]);
	let loading = $state(true);
	let error = $state('');

	// Add form
	let showAddForm = $state(false);
	let newTitle = $state('');
	let newContent = $state('');
	let adding = $state(false);

	// Edit state
	let editingId = $state(null);
	let editTitle = $state('');
	let editContent = $state('');

	// Expanded state
	let expandedId = $state(null);

	onMount(loadEntries);

	async function loadEntries() {
		loading = true;
		try {
			entries = await listKnowledge();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	async function handleAdd() {
		if (!newTitle.trim() || !newContent.trim()) return;

		adding = true;
		error = '';
		try {
			const addedBy = $currentUser?.email?.split('@')[0] || null;
			await addKnowledge({ title: newTitle.trim(), content: newContent.trim(), added_by: addedBy });
			newTitle = '';
			newContent = '';
			showAddForm = false;
			await loadEntries();
		} catch (e) {
			error = e.message;
		} finally {
			adding = false;
		}
	}

	function startEdit(entry) {
		editingId = entry.id;
		editTitle = entry.title;
		editContent = entry.content;
	}

	async function saveEdit() {
		if (!editTitle.trim() || !editContent.trim()) return;

		error = '';
		try {
			await updateKnowledge(editingId, { title: editTitle.trim(), content: editContent.trim() });
			editingId = null;
			await loadEntries();
		} catch (e) {
			error = e.message;
		}
	}

	function cancelEdit() {
		editingId = null;
	}

	async function handleDelete(id) {
		error = '';
		try {
			await deleteKnowledge(id);
			await loadEntries();
		} catch (e) {
			error = e.message;
		}
	}

	function toggleExpand(id) {
		expandedId = expandedId === id ? null : id;
	}
</script>

<div class="panel-overlay" onclick={onClose}></div>
<aside class="knowledge-panel">
	<div class="panel-header">
		<h2>Knowledge Base</h2>
		<button class="close-btn" onclick={onClose}>
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<line x1="18" y1="6" x2="6" y2="18"/>
				<line x1="6" y1="6" x2="18" y2="18"/>
			</svg>
		</button>
	</div>

	<div class="panel-content">
		<button class="add-toggle" onclick={() => showAddForm = !showAddForm}>
			{showAddForm ? 'Cancel' : '+ Add Entry'}
		</button>

		{#if showAddForm}
			<div class="add-form">
				<input
					type="text"
					bind:value={newTitle}
					placeholder="Title"
					disabled={adding}
				/>
				<textarea
					bind:value={newContent}
					placeholder="Content — Ash will see this in its context..."
					rows="4"
					disabled={adding}
				></textarea>
				<button class="submit-btn" onclick={handleAdd} disabled={adding || !newTitle.trim() || !newContent.trim()}>
					{adding ? 'Adding...' : 'Add Entry'}
				</button>
			</div>
		{/if}

		{#if error}
			<p class="error">{error}</p>
		{/if}

		{#if loading}
			<p class="loading-text">Loading...</p>
		{:else if entries.length === 0}
			<p class="empty-text">No knowledge entries yet. Add one so Ash knows about your project context.</p>
		{:else}
			<ul class="entry-list">
				{#each entries as entry (entry.id)}
					<li class="entry-item">
						{#if editingId === entry.id}
							<div class="edit-form">
								<input type="text" bind:value={editTitle} />
								<textarea bind:value={editContent} rows="4"></textarea>
								<div class="edit-actions">
									<button class="save-btn" onclick={saveEdit}>Save</button>
									<button class="cancel-btn" onclick={cancelEdit}>Cancel</button>
								</div>
							</div>
						{:else}
							<button class="entry-header" onclick={() => toggleExpand(entry.id)}>
								<span class="entry-title">{entry.title}</span>
								<svg
									width="14" height="14" viewBox="0 0 24 24" fill="none"
									stroke="currentColor" stroke-width="2"
									class="chevron"
									class:expanded={expandedId === entry.id}
								>
									<polyline points="6 9 12 15 18 9"/>
								</svg>
							</button>
							{#if expandedId === entry.id}
								<div class="entry-body">
									<p class="entry-content">{entry.content}</p>
									{#if entry.added_by}
										<p class="entry-meta">Added by {entry.added_by}</p>
									{/if}
									<div class="entry-actions">
										<button class="edit-btn" onclick={() => startEdit(entry)}>Edit</button>
										<button class="delete-btn" onclick={() => handleDelete(entry.id)}>Delete</button>
									</div>
								</div>
							{/if}
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</aside>

<style>
	.panel-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 200;
	}
	.knowledge-panel {
		position: fixed;
		top: 0;
		right: 0;
		width: 400px;
		max-width: 90vw;
		height: 100vh;
		background: var(--bg-primary);
		border-left: 1px solid var(--border);
		z-index: 201;
		display: flex;
		flex-direction: column;
		box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
	}
	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid var(--border);
	}
	.panel-header h2 {
		font-size: 16px;
		font-weight: 600;
	}
	.close-btn {
		padding: 4px;
		border-radius: 4px;
		color: var(--text-muted);
	}
	.close-btn:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}
	.panel-content {
		flex: 1;
		overflow-y: auto;
		padding: 16px 20px;
	}
	.add-toggle {
		font-size: 13px;
		color: var(--accent);
		margin-bottom: 12px;
		padding: 6px 0;
	}
	.add-toggle:hover {
		text-decoration: underline;
	}
	.add-form, .edit-form {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 16px;
		padding: 12px;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	.add-form input, .add-form textarea,
	.edit-form input, .edit-form textarea {
		padding: 8px 12px;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--bg-tertiary);
		outline: none;
		resize: vertical;
		font-size: 13px;
	}
	.add-form input:focus, .add-form textarea:focus,
	.edit-form input:focus, .edit-form textarea:focus {
		border-color: var(--accent);
	}
	.submit-btn {
		padding: 8px 16px;
		background: var(--accent);
		color: white;
		border-radius: 6px;
		font-size: 13px;
		align-self: flex-start;
	}
	.submit-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.error {
		color: var(--error);
		font-size: 12px;
		margin-bottom: 12px;
	}
	.loading-text, .empty-text {
		color: var(--text-muted);
		font-size: 13px;
	}
	.entry-list {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.entry-item {
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: hidden;
	}
	.entry-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 10px 12px;
		text-align: left;
		font-size: 13px;
		font-weight: 500;
	}
	.entry-header:hover {
		background: var(--bg-hover);
	}
	.chevron {
		transition: transform 0.15s;
		flex-shrink: 0;
	}
	.chevron.expanded {
		transform: rotate(180deg);
	}
	.entry-body {
		padding: 0 12px 12px;
		border-top: 1px solid var(--border);
	}
	.entry-content {
		font-size: 13px;
		line-height: 1.5;
		color: var(--text-secondary);
		white-space: pre-wrap;
		padding: 8px 0;
	}
	.entry-meta {
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 8px;
	}
	.entry-actions {
		display: flex;
		gap: 8px;
	}
	.edit-btn, .save-btn {
		font-size: 12px;
		color: var(--accent);
		padding: 4px 8px;
	}
	.cancel-btn {
		font-size: 12px;
		color: var(--text-muted);
		padding: 4px 8px;
	}
	.delete-btn {
		font-size: 12px;
		color: var(--error);
		padding: 4px 8px;
	}
	.edit-actions {
		display: flex;
		gap: 8px;
	}
</style>
