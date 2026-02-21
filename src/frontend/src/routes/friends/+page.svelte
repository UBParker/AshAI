<script>
	import { onMount } from 'svelte';
	import { friends, friendRequests, loadFriends, loadFriendRequests, sendFriendRequest, acceptFriendRequest, declineFriendRequest } from '$lib/stores/friends.js';
	import { projects, loadProjects, inviteToProject } from '$lib/stores/projects.js';

	let emailInput = $state('');
	let error = $state('');
	let success = $state('');
	let loading = $state(false);

	onMount(() => {
		loadFriends();
		loadFriendRequests();
		loadProjects();
	});

	async function handleSendRequest() {
		const email = emailInput.trim();
		if (!email) return;

		error = '';
		success = '';
		loading = true;

		try {
			await sendFriendRequest(email);
			success = `Friend request sent to ${email}`;
			emailInput = '';
		} catch (e) {
			error = e.message || 'Failed to send request';
		} finally {
			loading = false;
		}
	}

	async function handleAccept(id) {
		try {
			await acceptFriendRequest(id);
		} catch (e) {
			error = e.message;
		}
	}

	async function handleDecline(id) {
		try {
			await declineFriendRequest(id);
		} catch (e) {
			error = e.message;
		}
	}

	async function handleInviteToProject(friendId, projectId) {
		try {
			await inviteToProject(projectId, friendId);
			success = 'Invited to project!';
		} catch (e) {
			error = e.message;
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleSendRequest();
		}
	}
</script>

<div class="friends-page">
	<h1>Friends</h1>

	<div class="add-friend">
		<input
			type="email"
			bind:value={emailInput}
			placeholder="Enter email address..."
			onkeydown={handleKeydown}
			disabled={loading}
		/>
		<button onclick={handleSendRequest} disabled={loading || !emailInput.trim()}>
			{loading ? 'Sending...' : 'Add Friend'}
		</button>
	</div>

	{#if error}
		<p class="error">{error}</p>
	{/if}
	{#if success}
		<p class="success">{success}</p>
	{/if}

	{#if $friendRequests.length > 0}
		<section class="section">
			<h2>Pending Requests</h2>
			<ul class="request-list">
				{#each $friendRequests as req (req.id)}
					<li class="request-item">
						<div class="request-info">
							<span class="name">{req.requester.display_name || req.requester.email}</span>
							<span class="email">{req.requester.email}</span>
						</div>
						<div class="request-actions">
							<button class="accept-btn" onclick={() => handleAccept(req.id)}>Accept</button>
							<button class="decline-btn" onclick={() => handleDecline(req.id)}>Decline</button>
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<section class="section">
		<h2>Your Friends ({$friends.length})</h2>
		{#if $friends.length === 0}
			<p class="empty-text">No friends yet. Add someone by email above.</p>
		{:else}
			<ul class="friend-list">
				{#each $friends as friend (friend.id)}
					<li class="friend-item">
						<div class="friend-avatar">
							{(friend.display_name || friend.email)[0].toUpperCase()}
						</div>
						<div class="friend-info">
							<span class="name">{friend.display_name || 'Unknown'}</span>
							<span class="email">{friend.email}</span>
						</div>
						{#if $projects.length > 0}
							<div class="invite-dropdown">
								<select onchange={(e) => { if (e.target.value) { handleInviteToProject(friend.id, e.target.value); e.target.value = ''; } }}>
									<option value="">Invite to project...</option>
									{#each $projects as project (project.id)}
										<option value={project.id}>{project.name}</option>
									{/each}
								</select>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
</div>

<style>
	.friends-page {
		padding: 32px;
		max-width: 640px;
		margin: 0 auto;
		width: 100%;
		overflow-y: auto;
	}
	h1 {
		font-size: 24px;
		font-weight: 700;
		margin-bottom: 24px;
	}
	h2 {
		font-size: 16px;
		font-weight: 600;
		margin-bottom: 12px;
		color: var(--text-secondary);
	}
	.add-friend {
		display: flex;
		gap: 8px;
		margin-bottom: 16px;
	}
	.add-friend input {
		flex: 1;
		padding: 10px 14px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-tertiary);
		outline: none;
	}
	.add-friend input:focus {
		border-color: var(--accent);
	}
	.add-friend button {
		padding: 10px 20px;
		background: var(--accent);
		color: white;
		border-radius: 8px;
		font-weight: 500;
		white-space: nowrap;
	}
	.add-friend button:hover:not(:disabled) {
		background: var(--accent-hover);
	}
	.add-friend button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.error {
		color: var(--error);
		font-size: 13px;
		margin-bottom: 16px;
	}
	.success {
		color: var(--success);
		font-size: 13px;
		margin-bottom: 16px;
	}
	.section {
		margin-bottom: 32px;
	}
	.request-list, .friend-list {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.request-item, .friend-item {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 16px;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	.friend-avatar {
		width: 40px;
		height: 40px;
		border-radius: 50%;
		background: var(--accent);
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 600;
		font-size: 16px;
		flex-shrink: 0;
	}
	.friend-info, .request-info {
		flex: 1;
		display: flex;
		flex-direction: column;
	}
	.name {
		font-weight: 500;
	}
	.email {
		font-size: 12px;
		color: var(--text-muted);
	}
	.request-actions {
		display: flex;
		gap: 8px;
	}
	.accept-btn {
		padding: 6px 16px;
		background: var(--success);
		color: white;
		border-radius: 6px;
		font-size: 13px;
	}
	.decline-btn {
		padding: 6px 16px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 6px;
		font-size: 13px;
	}
	.invite-dropdown select {
		padding: 6px 10px;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--bg-tertiary);
		font-size: 12px;
		cursor: pointer;
	}
	.empty-text {
		color: var(--text-muted);
		font-size: 14px;
	}
</style>
