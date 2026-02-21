<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { projects, loadProjects, createProject, switchToProject } from '$lib/stores/projects.js';
	import { handleAgentEvent } from '$lib/stores/agents.js';
	import { handleApprovalEvent } from '$lib/stores/approvals.js';
	import { fetchProjectMembers } from '$lib/supabase.js';

	let showCreateForm = $state(false);
	let newName = $state('');
	let newDescription = $state('');
	let creating = $state(false);
	let error = $state('');
	let memberCounts = $state({});

	onMount(async () => {
		await loadProjects();
		// Load member counts
		for (const proj of $projects) {
			try {
				const members = await fetchProjectMembers(proj.id);
				memberCounts[proj.id] = members.length;
			} catch {
				memberCounts[proj.id] = 0;
			}
		}
		memberCounts = { ...memberCounts };
	});

	async function handleCreate() {
		if (!newName.trim()) return;

		creating = true;
		error = '';

		try {
			await createProject(newName.trim(), newDescription.trim());
			newName = '';
			newDescription = '';
			showCreateForm = false;
		} catch (e) {
			error = e.message;
		} finally {
			creating = false;
		}
	}

	function wsEventHandler(event) {
		handleAgentEvent(event);
		handleApprovalEvent(event);
	}

	async function handleOpenProject(project) {
		try {
			await switchToProject(project, wsEventHandler);
			goto('/');
		} catch (e) {
			error = e.message;
		}
	}
</script>

<div class="projects-page">
	<div class="page-header">
		<h1>Projects</h1>
		<button class="create-btn" onclick={() => showCreateForm = !showCreateForm}>
			{showCreateForm ? 'Cancel' : 'New Project'}
		</button>
	</div>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	{#if showCreateForm}
		<div class="create-form">
			<input
				type="text"
				bind:value={newName}
				placeholder="Project name"
				disabled={creating}
			/>
			<textarea
				bind:value={newDescription}
				placeholder="Description (optional)"
				rows="2"
				disabled={creating}
			></textarea>
			<button class="submit-btn" onclick={handleCreate} disabled={creating || !newName.trim()}>
				{creating ? 'Creating...' : 'Create Project'}
			</button>
		</div>
	{/if}

	<div class="project-grid">
		{#if $projects.length === 0}
			<p class="empty-text">No projects yet. Create one to start collaborating.</p>
		{:else}
			{#each $projects as project (project.id)}
				<button class="project-card" onclick={() => handleOpenProject(project)}>
					<div class="card-icon">
						<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
						</svg>
					</div>
					<h3 class="card-name">{project.name}</h3>
					{#if project.description}
						<p class="card-desc">{project.description}</p>
					{/if}
					<div class="card-meta">
						<span class="member-count">
							<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
								<circle cx="9" cy="7" r="4"/>
							</svg>
							{memberCounts[project.id] || 1} member{(memberCounts[project.id] || 1) !== 1 ? 's' : ''}
						</span>
						<span class="role-badge">{project.my_role}</span>
					</div>
				</button>
			{/each}
		{/if}
	</div>
</div>

<style>
	.projects-page {
		padding: 32px;
		max-width: 800px;
		margin: 0 auto;
		width: 100%;
		overflow-y: auto;
	}
	.page-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 24px;
	}
	h1 {
		font-size: 24px;
		font-weight: 700;
	}
	.create-btn {
		padding: 8px 20px;
		background: var(--accent);
		color: white;
		border-radius: 8px;
		font-weight: 500;
	}
	.create-btn:hover {
		background: var(--accent-hover);
	}
	.error {
		color: var(--error);
		font-size: 13px;
		margin-bottom: 16px;
	}
	.create-form {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-bottom: 24px;
		padding: 20px;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 12px;
	}
	.create-form input, .create-form textarea {
		padding: 10px 14px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-tertiary);
		outline: none;
		resize: none;
	}
	.create-form input:focus, .create-form textarea:focus {
		border-color: var(--accent);
	}
	.submit-btn {
		padding: 10px 20px;
		background: var(--accent);
		color: white;
		border-radius: 8px;
		font-weight: 500;
		align-self: flex-start;
	}
	.submit-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.project-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 16px;
	}
	.project-card {
		display: flex;
		flex-direction: column;
		padding: 20px;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 12px;
		text-align: left;
		cursor: pointer;
		transition: border-color 0.15s, box-shadow 0.15s;
	}
	.project-card:hover {
		border-color: var(--accent);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}
	.card-icon {
		color: var(--accent);
		margin-bottom: 12px;
	}
	.card-name {
		font-size: 16px;
		font-weight: 600;
		margin-bottom: 4px;
	}
	.card-desc {
		font-size: 13px;
		color: var(--text-secondary);
		margin-bottom: 12px;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.card-meta {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-top: auto;
		padding-top: 12px;
		border-top: 1px solid var(--border);
	}
	.member-count {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: 12px;
		color: var(--text-muted);
	}
	.role-badge {
		font-size: 11px;
		padding: 2px 8px;
		border-radius: 4px;
		background: var(--bg-tertiary);
		color: var(--text-muted);
		text-transform: capitalize;
	}
	.empty-text {
		color: var(--text-muted);
		font-size: 14px;
		grid-column: 1 / -1;
	}
</style>
