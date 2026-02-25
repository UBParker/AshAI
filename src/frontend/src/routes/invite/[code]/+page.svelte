<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { currentUser, isAuthEnabled, initAuth } from '$lib/auth.js';
	import { getInviteByCode, useInvite, createFriendRequest, addProjectMember, updateFriendshipStatus } from '$lib/supabase.js';

	let invite = $state(null);
	let loading = $state(true);
	let accepting = $state(false);
	let error = $state('');
	let success = $state('');

	$effect(() => {
		const code = $page.params.code;
		if (code) loadInvite(code);
	});

	async function loadInvite(code) {
		loading = true;
		error = '';
		try {
			// Ensure user is authenticated
			if (isAuthEnabled()) {
				const session = await initAuth();
				if (!session) {
					goto(`/login?redirect=/invite/${code}`);
					return;
				}
			}

			invite = await getInviteByCode(code);

			// Check if expired or used up
			if (invite.expires_at && new Date(invite.expires_at) < new Date()) {
				error = 'This invite has expired.';
				invite = null;
			} else if (invite.max_uses && invite.uses >= invite.max_uses) {
				error = 'This invite has been used up.';
				invite = null;
			}
		} catch (e) {
			error = 'Invite not found or invalid.';
		} finally {
			loading = false;
		}
	}

	async function handleAccept() {
		if (!invite || !$currentUser) return;

		accepting = true;
		error = '';

		try {
			if (invite.type === 'friend') {
				// Create a friendship and immediately accept it (invite-based)
				const friendship = await createFriendRequest(invite.creator_id, $currentUser.id);
				if (friendship?.id) {
					await updateFriendshipStatus(friendship.id, 'accepted').catch(() => {});
				}

				success = `You are now friends with ${invite.creator.display_name || invite.creator.email}!`;
			} else if (invite.type === 'project') {
				// Add current user as project member
				await addProjectMember(invite.project_id, $currentUser.id, 'editor');
				success = `You've joined the project "${invite.project.name}"!`;
			}

			// Mark invite as used
			await useInvite(invite.id);
		} catch (e) {
			error = e.message || 'Failed to accept invite';
		} finally {
			accepting = false;
		}
	}
</script>

<div class="invite-page">
	<div class="invite-card">
		{#if loading}
			<div class="loading">
				<div class="spinner"></div>
				<p>Loading invite...</p>
			</div>
		{:else if error && !invite}
			<div class="error-state">
				<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--error)" stroke-width="2">
					<circle cx="12" cy="12" r="10"/>
					<line x1="15" y1="9" x2="9" y2="15"/>
					<line x1="9" y1="9" x2="15" y2="15"/>
				</svg>
				<p>{error}</p>
				<button onclick={() => goto('/')}>Go Home</button>
			</div>
		{:else if success}
			<div class="success-state">
				<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2">
					<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
					<polyline points="22 4 12 14.01 9 11.01"/>
				</svg>
				<p>{success}</p>
				<button onclick={() => goto('/')}>Go to AshAI</button>
			</div>
		{:else if invite}
			<div class="invite-content">
				{#if invite.type === 'friend'}
					<div class="invite-icon">
						<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2">
							<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
							<circle cx="9" cy="7" r="4"/>
							<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
							<path d="M16 3.13a4 4 0 0 1 0 7.75"/>
						</svg>
					</div>
					<h2>Friend Request</h2>
					<p class="invite-desc">
						<strong>{invite.creator.display_name || invite.creator.email}</strong> wants to be friends with you on AshAI.
					</p>
				{:else if invite.type === 'project'}
					<div class="invite-icon">
						<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2">
							<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
						</svg>
					</div>
					<h2>Project Invite</h2>
					<p class="invite-desc">
						<strong>{invite.creator.display_name || invite.creator.email}</strong> invited you to join <strong>{invite.project?.name}</strong>.
					</p>
					{#if invite.project?.description}
						<p class="project-desc">{invite.project.description}</p>
					{/if}
				{/if}

				{#if error}
					<p class="error">{error}</p>
				{/if}

				<button class="accept-btn" onclick={handleAccept} disabled={accepting}>
					{accepting ? 'Accepting...' : 'Accept'}
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	.invite-page {
		height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--bg-primary);
		padding: 20px;
	}
	.invite-card {
		max-width: 420px;
		width: 100%;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 16px;
		padding: 40px;
		text-align: center;
	}
	.loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		color: var(--text-muted);
	}
	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	.error-state, .success-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 16px;
	}
	.error-state button, .success-state button {
		padding: 10px 24px;
		background: var(--accent);
		color: white;
		border-radius: 8px;
		font-weight: 500;
	}
	.invite-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 16px;
	}
	.invite-icon {
		margin-bottom: 8px;
	}
	h2 {
		font-size: 20px;
		font-weight: 700;
	}
	.invite-desc {
		color: var(--text-secondary);
		font-size: 15px;
		line-height: 1.5;
	}
	.project-desc {
		font-size: 13px;
		color: var(--text-muted);
		padding: 8px 12px;
		background: var(--bg-tertiary);
		border-radius: 8px;
		width: 100%;
	}
	.error {
		color: var(--error);
		font-size: 13px;
	}
	.accept-btn {
		padding: 12px 32px;
		background: var(--accent);
		color: white;
		border-radius: 10px;
		font-weight: 600;
		font-size: 15px;
		width: 100%;
	}
	.accept-btn:hover:not(:disabled) {
		background: var(--accent-hover);
	}
	.accept-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
