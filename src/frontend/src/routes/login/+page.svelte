<script>
	import { goto } from '$app/navigation';
	import { signIn, signUp } from '$lib/auth.js';
	import { GATEWAY_URL } from '$lib/config.js';
	import { setBackendUrl, waitForBackend } from '$lib/api/client.js';

	let isSignUp = $state(false);
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);
	let loadingMessage = $state('');

	async function handleSubmit() {
		if (!email.trim() || !password.trim()) {
			error = 'Please enter your email and password.';
			return;
		}
		if (password.length < 6) {
			error = 'Password must be at least 6 characters.';
			return;
		}

		error = '';
		loading = true;

		try {
			if (isSignUp) {
				loadingMessage = 'Creating your account...';
				const data = await signUp(email, password);

				// If email confirmation is required
				if (!data.session) {
					loading = false;
					error = 'Check your email to confirm your account, then sign in.';
					isSignUp = false;
					return;
				}
			} else {
				loadingMessage = 'Signing in...';
				await signIn(email, password);
			}

			// Connect to gateway to get a backend instance
			loadingMessage = 'Setting up your workspace...';
			await connectToGateway();

			goto('/');
		} catch (err) {
			error = err.message || 'Something went wrong. Try again.';
			loading = false;
			loadingMessage = '';
		}
	}

	async function connectToGateway() {
		const { getAccessToken } = await import('$lib/auth.js');
		const token = await getAccessToken();
		if (!token) throw new Error('Not authenticated');

		const res = await fetch(`${GATEWAY_URL}/gateway/session`, {
			method: 'POST',
			headers: {
				'Authorization': `Bearer ${token}`,
				'Content-Type': 'application/json',
			},
		});

		if (!res.ok) {
			const body = await res.text();
			throw new Error(`Failed to start workspace: ${body}`);
		}

		const { backend_url } = await res.json();
		setBackendUrl(backend_url);

		loadingMessage = 'Connecting to Ash...';
		await waitForBackend();
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') {
			handleSubmit();
		}
	}
</script>

<div class="login-page">
	{#if loading}
		<div class="loading-content">
			<h1 class="loading-logo">AshAI</h1>
			<div class="spinner"></div>
			<p class="loading-message">{loadingMessage}</p>
		</div>
	{:else}
		<div class="login-card">
			<h1 class="logo">AshAI</h1>
			<p class="tagline">{isSignUp ? 'Create your account' : 'Welcome back'}</p>

			<div class="form">
				<input
					type="email"
					bind:value={email}
					onkeydown={handleKeydown}
					placeholder="Email"
					autocomplete="email"
				/>
				<input
					type="password"
					bind:value={password}
					onkeydown={handleKeydown}
					placeholder="Password"
					autocomplete={isSignUp ? 'new-password' : 'current-password'}
				/>

				{#if error}
					<p class="error">{error}</p>
				{/if}

				<button class="btn-primary" onclick={handleSubmit}>
					{isSignUp ? 'Create account' : 'Sign in'}
				</button>
			</div>

			<p class="toggle">
				{isSignUp ? 'Already have an account?' : "Don't have an account?"}
				<button class="toggle-btn" onclick={() => { isSignUp = !isSignUp; error = ''; }}>
					{isSignUp ? 'Sign in' : 'Sign up'}
				</button>
			</p>
		</div>
	{/if}
</div>

<style>
	.login-page {
		height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--bg-primary);
		padding: 20px;
	}

	.login-card {
		max-width: 400px;
		width: 100%;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 14px;
		padding: 40px;
		text-align: center;
	}

	.logo {
		font-size: 32px;
		font-weight: 700;
		color: var(--accent);
		margin-bottom: 8px;
	}

	.tagline {
		color: var(--text-secondary);
		font-size: 15px;
		margin-bottom: 28px;
	}

	.form {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	input {
		width: 100%;
		padding: 12px 14px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 10px;
		font-size: 14px;
		outline: none;
		transition: border-color 0.15s;
	}

	input:focus {
		border-color: var(--accent);
	}

	input::placeholder {
		color: var(--text-muted);
	}

	.error {
		color: var(--error);
		font-size: 13px;
	}

	.btn-primary {
		padding: 12px;
		background: var(--accent);
		color: white;
		border-radius: 10px;
		font-weight: 600;
		font-size: 15px;
		transition: background 0.15s;
		margin-top: 4px;
	}

	.btn-primary:hover {
		background: var(--accent-hover);
	}

	.toggle {
		margin-top: 20px;
		color: var(--text-secondary);
		font-size: 13px;
	}

	.toggle-btn {
		color: var(--accent);
		font-weight: 600;
		font-size: 13px;
		padding: 0;
	}

	.toggle-btn:hover {
		text-decoration: underline;
	}

	/* Loading state */
	.loading-content {
		text-align: center;
	}

	.loading-logo {
		font-size: 36px;
		font-weight: 700;
		color: var(--accent);
		margin-bottom: 24px;
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
		font-size: 14px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
