<script>
	import { goto } from '$app/navigation';
	import { projects, currentProject, switchToProject, switchToPersonal, loadProjects } from '$lib/stores/projects.js';
	import { handleAgentEvent } from '$lib/stores/agents.js';
	import { handleApprovalEvent } from '$lib/stores/approvals.js';
	import { isAuthEnabled } from '$lib/auth.js';
	import { onMount } from 'svelte';

	let {
		onToggleSidebar = () => {},
		onSignOut = undefined,
		projectName = null,
		wsEventHandler = undefined,
	} = $props();

	let showSwitcher = $state(false);
	let showKnowledge = $state(false);
	let switching = $state(false);

	onMount(() => {
		if (isAuthEnabled()) {
			loadProjects();
		}
	});

	function defaultWsHandler(event) {
		handleAgentEvent(event);
		handleApprovalEvent(event);
	}

	async function handleSwitchToPersonal() {
		if (switching) return;
		switching = true;
		showSwitcher = false;
		try {
			await switchToPersonal(wsEventHandler || defaultWsHandler);
			goto('/');
		} catch (e) {
			console.error('Failed to switch to personal:', e);
		} finally {
			switching = false;
		}
	}

	async function handleSwitchToProject(project) {
		if (switching) return;
		switching = true;
		showSwitcher = false;
		try {
			await switchToProject(project, wsEventHandler || defaultWsHandler);
			goto('/');
		} catch (e) {
			console.error('Failed to switch to project:', e);
		} finally {
			switching = false;
		}
	}

	function toggleSwitcher() {
		showSwitcher = !showSwitcher;
		if (showSwitcher) loadProjects();
	}

	function handleClickOutside(e) {
		if (showSwitcher) showSwitcher = false;
	}
</script>

<svelte:window onclick={handleClickOutside} />

<header class="header">
	<button class="menu-btn" onclick={onToggleSidebar}>
		<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<line x1="3" y1="6" x2="21" y2="6"/>
			<line x1="3" y1="12" x2="21" y2="12"/>
			<line x1="3" y1="18" x2="21" y2="18"/>
		</svg>
	</button>
	<div class="title">
		<span class="logo">AshAI</span>
	</div>

	{#if isAuthEnabled()}
		<div class="switcher-wrapper" onclick={(e) => e.stopPropagation()}>
			<button
				class="switcher-btn"
				class:active={showSwitcher}
				onclick={toggleSwitcher}
				disabled={switching}
			>
				{#if switching}
					<span class="switcher-spinner"></span>
				{:else if projectName}
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
					</svg>
				{:else}
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
						<circle cx="12" cy="7" r="4"/>
					</svg>
				{/if}
				<span>{projectName || 'Personal'}</span>
				<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<polyline points="6 9 12 15 18 9"/>
				</svg>
			</button>

			{#if showSwitcher}
				<div class="switcher-dropdown">
					<button
						class="switcher-option"
						class:current={!projectName}
						onclick={handleSwitchToPersonal}
					>
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
							<circle cx="12" cy="7" r="4"/>
						</svg>
						Personal
					</button>

					{#if $projects.length > 0}
						<div class="switcher-divider"></div>
						<div class="switcher-label">Projects</div>
						{#each $projects as proj (proj.id)}
							<button
								class="switcher-option"
								class:current={$currentProject?.id === proj.id}
								onclick={() => handleSwitchToProject(proj)}
							>
								<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
								</svg>
								{proj.name}
							</button>
						{/each}
					{/if}

					<div class="switcher-divider"></div>
					<button class="switcher-option switcher-link" onclick={() => { showSwitcher = false; goto('/projects'); }}>
						All Projects...
					</button>
				</div>
			{/if}
		</div>
	{/if}

	<div class="spacer"></div>

	<button class="header-icon-btn" onclick={() => goto('/agents')} title="Agent Manager">
		<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
			<circle cx="9" cy="7" r="4"></circle>
			<path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
			<path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
		</svg>
	</button>

	<button class="header-icon-btn" onclick={() => goto('/setup')} title="Settings">
		<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M12 15a3 3 0 100-6 3 3 0 000 6z"/>
			<path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
		</svg>
	</button>

	{#if $currentProject}
		<button class="header-icon-btn" onclick={() => { showKnowledge = !showKnowledge; }} title="Knowledge Base">
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
				<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
			</svg>
		</button>
	{/if}

	{#if onSignOut}
		<button class="sign-out-btn" onclick={onSignOut} title="Sign out">
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
				<polyline points="16 17 21 12 16 7"/>
				<line x1="21" y1="12" x2="9" y2="12"/>
			</svg>
		</button>
	{/if}
</header>

{#if showKnowledge}
	{#await import('./KnowledgePanel.svelte') then { default: KnowledgePanel }}
		<KnowledgePanel onClose={() => showKnowledge = false} />
	{/await}
{/if}

<style>
	.header {
		height: var(--header-height);
		background: var(--bg-secondary);
		border-bottom: 1px solid var(--border);
		display: flex;
		align-items: center;
		padding: 0 16px;
		gap: 12px;
	}
	.menu-btn {
		padding: 4px;
		border-radius: 4px;
		color: var(--text-secondary);
	}
	.menu-btn:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}
	.title {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.logo {
		font-weight: 700;
		font-size: 16px;
		color: var(--accent);
	}

	/* Switcher */
	.switcher-wrapper {
		position: relative;
	}
	.switcher-btn {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 5px 10px;
		border-radius: 6px;
		font-size: 13px;
		color: var(--text-secondary);
		border: 1px solid var(--border);
		background: var(--bg-tertiary);
	}
	.switcher-btn:hover, .switcher-btn.active {
		border-color: var(--accent);
		color: var(--text-primary);
	}
	.switcher-btn:disabled {
		opacity: 0.6;
	}
	.switcher-spinner {
		width: 14px;
		height: 14px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.6s linear infinite;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	.switcher-dropdown {
		position: absolute;
		top: calc(100% + 4px);
		left: 0;
		min-width: 200px;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 4px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		z-index: 100;
	}
	.switcher-option {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 8px 12px;
		border-radius: 6px;
		font-size: 13px;
		text-align: left;
		color: var(--text-primary);
	}
	.switcher-option:hover {
		background: var(--bg-hover);
	}
	.switcher-option.current {
		background: var(--bg-tertiary);
		font-weight: 500;
	}
	.switcher-divider {
		height: 1px;
		background: var(--border);
		margin: 4px 0;
	}
	.switcher-label {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: var(--text-muted);
		padding: 4px 12px;
		font-weight: 600;
	}
	.switcher-link {
		color: var(--accent);
	}

	.spacer {
		flex: 1;
	}
	.header-icon-btn {
		padding: 6px;
		border-radius: 6px;
		color: var(--text-muted);
		transition: color 0.15s, background 0.15s;
	}
	.header-icon-btn:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}
	.sign-out-btn {
		padding: 6px;
		border-radius: 6px;
		color: var(--text-muted);
		transition: color 0.15s, background 0.15s;
	}
	.sign-out-btn:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}
</style>
