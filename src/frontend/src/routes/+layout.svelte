<script>
	import '../app.css';
	import Header from '$lib/components/Header.svelte';
	import AgentSidebar from '$lib/components/AgentSidebar.svelte';
	import ApprovalDialog from '$lib/components/ApprovalDialog.svelte';
	import ErrorBoundary from '$lib/components/ErrorBoundary.svelte';
	import { refreshAgents, handleAgentEvent } from '$lib/stores/agents.js';
	import { handleApprovalEvent } from '$lib/stores/approvals.js';
	import { connectWebSocket, disconnectWebSocket, isTauri, setBackendUrl, waitForBackend, getSettings } from '$lib/api/client.js';
	import { isAuthEnabled, initAuth, getAccessToken, signOut, currentUser } from '$lib/auth.js';
	import { currentProject } from '$lib/stores/projects.js';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	let { children } = $props();
	let sidebarVisible = $state(true);
	let currentAgentId = $state(null);
	let backendReady = $state(false);
	let loadingMessage = $state('Starting AshAI...');

	// Pages that don't need the backend or auth gate
	function isPublicPage() {
		const path = $page?.url?.pathname;
		return path === '/login' || path?.startsWith('/invite/');
	}

	function wsEventHandler(event) {
		handleAgentEvent(event);
		handleApprovalEvent(event);
		// Dispatch custom event for message updates
		if (event.type === 'agent.message') {
			window.dispatchEvent(new CustomEvent('ws:message', { detail: event }));
		}
	}

	onMount(async () => {
		if (isTauri()) {
			// --- Tauri desktop mode (unchanged) ---
			loadingMessage = 'Starting AshAI backend...';

			try {
				const { invoke } = await import('@tauri-apps/api/core');
				const { listen } = await import('@tauri-apps/api/event');

				const unlisten = await listen('backend-ready', async (event) => {
					const port = event.payload;
					setBackendUrl(`http://127.0.0.1:${port}`);
					loadingMessage = 'Connecting to backend...';

					await waitForBackend();
					backendReady = true;
					unlisten();
					startApp();
				});

				const port = await invoke('get_backend_port');
				if (port) {
					setBackendUrl(`http://127.0.0.1:${port}`);
					await waitForBackend();
					backendReady = true;
					unlisten();
					startApp();
				}
			} catch (err) {
				loadingMessage = `Failed to start: ${err.message}`;
			}
		} else if (isAuthEnabled()) {
			// --- Web mode with auth (app.ashai.net) ---
			if (isPublicPage()) {
				backendReady = true;
				return;
			}

			loadingMessage = 'Checking session...';
			const session = await initAuth();

			if (!session) {
				goto('/login');
				return;
			}

			// We have a session — tell gateway to spawn our instance
			try {
				loadingMessage = 'Connecting to your workspace...';
				const token = await getAccessToken();
				const res = await fetch('/gateway/session', {
					method: 'POST',
					headers: {
						'Authorization': `Bearer ${token}`,
						'Content-Type': 'application/json',
					},
				});

				if (!res.ok) {
					throw new Error('Could not start workspace');
				}

				// Backend URL stays as '' — gateway proxies /api/* for us
				loadingMessage = 'Connecting to Ash...';
				await waitForBackend();
				backendReady = true;
				startApp();
			} catch (err) {
				loadingMessage = `Connection failed: ${err.message}`;
			}
		} else {
			// --- Local dev mode (no auth, direct backend) ---
			backendReady = true;
			startApp();
		}
	});

	async function startApp() {
		refreshAgents();
		await connectWebSocket(wsEventHandler);

		// Check if onboarding is needed
		try {
			const settings = await getSettings();
			const currentPath = $page?.url?.pathname;
			if (!settings.has_any_key && currentPath !== '/setup') {
				goto('/setup');
			}
		} catch {
			// Settings endpoint not available — skip check
		}
	}

	function handleSelectAgent(agentId) {
		currentAgentId = agentId;
		goto(`/agents/${agentId}`);
	}

	function toggleSidebar() {
		sidebarVisible = !sidebarVisible;
	}

	async function handleSignOut() {
		try {
			// Tell gateway to stop our instance
			const token = await getAccessToken();
			if (token) {
				await fetch('/gateway/logout', {
					method: 'POST',
					headers: { 'Authorization': `Bearer ${token}` },
				}).catch(() => {});
			}
			await signOut();
			goto('/login');
		} catch {
			goto('/login');
		}
	}

	function navigateTo(path) {
		goto(path);
	}
</script>

{#if isPublicPage()}
	{@render children()}
{:else if backendReady}
	<div class="app">
		<Header
			onToggleSidebar={toggleSidebar}
			onSignOut={isAuthEnabled() ? handleSignOut : undefined}
			projectName={$currentProject?.name || null}
			wsEventHandler={wsEventHandler}
		/>
		<div class="body">
			<AgentSidebar
				visible={sidebarVisible}
				{currentAgentId}
				onSelectAgent={handleSelectAgent}
			>
				{#if isAuthEnabled()}
					<div class="nav-links">
						<button class="nav-link" onclick={() => navigateTo('/friends')}>
							<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
								<circle cx="9" cy="7" r="4"/>
								<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
								<path d="M16 3.13a4 4 0 0 1 0 7.75"/>
							</svg>
							Friends
						</button>
						<button class="nav-link" onclick={() => navigateTo('/projects')}>
							<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
							</svg>
							Projects
						</button>
					</div>
				{/if}
			</AgentSidebar>
			<main class="main">
				<ErrorBoundary>
					{@render children()}
				</ErrorBoundary>
			</main>
		</div>
	</div>

	<ApprovalDialog />
{:else}
	<div class="loading-screen">
		<div class="loading-content">
			<h1 class="loading-logo">AshAI</h1>
			<p class="loading-tagline">Coordinates your teams of AI agents</p>
			<div class="spinner"></div>
			<p class="loading-message">{loadingMessage}</p>
		</div>
	</div>
{/if}

<style>
	.app {
		height: 100vh;
		display: flex;
		flex-direction: column;
	}
	.body {
		flex: 1;
		display: flex;
		overflow: hidden;
	}
	.main {
		flex: 1;
		overflow: hidden;
		display: flex;
	}

	.nav-links {
		padding: 8px 12px;
		border-top: 1px solid var(--border);
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.nav-link {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		border-radius: 6px;
		font-size: 13px;
		color: var(--text-secondary);
		text-align: left;
		width: 100%;
	}
	.nav-link:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}

	.loading-screen {
		height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--bg-primary);
	}
	.loading-content {
		text-align: center;
	}
	.loading-logo {
		font-size: 36px;
		font-weight: 700;
		color: var(--accent);
		margin-bottom: 8px;
	}
	.loading-tagline {
		color: var(--text-secondary);
		margin-bottom: 32px;
		font-size: 15px;
	}
	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		margin: 0 auto 16px;
		animation: spin 0.8s linear infinite;
	}
	.loading-message {
		color: var(--text-muted);
		font-size: 13px;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
