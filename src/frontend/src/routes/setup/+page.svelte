<script>
	import { goto } from '$app/navigation';
	import { putSettings, checkClaudeCli } from '$lib/api/client.js';

	let step = $state(1);
	let provider = $state('anthropic');
	let apiKey = $state('');
	let saving = $state(false);
	let error = $state('');
	let claudeStatus = $state(null);

	const totalSteps = 4;

	function next() {
		error = '';
		step++;
		if (step === 4) {
			loadClaudeStatus();
		}
	}

	function back() {
		error = '';
		step--;
	}

	async function saveApiKey() {
		if (!apiKey.trim()) {
			error = 'Please enter an API key.';
			return;
		}
		saving = true;
		error = '';
		try {
			const keyMap = {
				anthropic: 'ANTHROPIC_API_KEY',
				openai: 'OPENAI_API_KEY'
			};
			const envKey = keyMap[provider];
			if (envKey) {
				await putSettings({
					[envKey]: apiKey.trim(),
					DEFAULT_PROVIDER: provider
				});
			}
			next();
		} catch (err) {
			error = `Failed to save: ${err.message}`;
		} finally {
			saving = false;
		}
	}

	async function saveOllamaSettings() {
		saving = true;
		error = '';
		try {
			await putSettings({
				DEFAULT_PROVIDER: 'ollama',
				OLLAMA_BASE_URL: 'http://localhost:11434'
			});
			next();
		} catch (err) {
			error = `Failed to save: ${err.message}`;
		} finally {
			saving = false;
		}
	}

	async function loadClaudeStatus() {
		try {
			claudeStatus = await checkClaudeCli();
		} catch {
			claudeStatus = { available: false, path: null, install_url: 'https://docs.anthropic.com/en/docs/claude-code/overview' };
		}
	}

	function finish() {
		goto('/');
	}
</script>

<div class="setup">
	<div class="setup-card">
		<div class="progress">
			{#each Array(totalSteps) as _, i}
				<div class="progress-dot" class:active={i + 1 <= step}></div>
			{/each}
		</div>

		{#if step === 1}
			<div class="step">
				<h1>Welcome to AshAI</h1>
				<p class="subtitle">AshAI coordinates your teams of AI agents — right on your machine.</p>
				<div class="features">
					<div class="feature">
						<span class="feature-icon">&#9670;</span>
						<div>
							<strong>Multi-agent coordination</strong>
							<p>Ash orchestrates specialized agents that work together</p>
						</div>
					</div>
					<div class="feature">
						<span class="feature-icon">&#9670;</span>
						<div>
							<strong>Local-first</strong>
							<p>Your data stays on your machine, always</p>
						</div>
					</div>
					<div class="feature">
						<span class="feature-icon">&#9670;</span>
						<div>
							<strong>Provider-agnostic</strong>
							<p>Works with Anthropic, OpenAI, or local models via Ollama</p>
						</div>
					</div>
				</div>
				<button class="btn-primary" onclick={next}>Get Started</button>
			</div>

		{:else if step === 2}
			<div class="step">
				<h2>Choose your AI provider</h2>
				<p class="subtitle">You can change this later in settings.</p>

				<div class="provider-options">
					<label class="provider-card" class:selected={provider === 'anthropic'}>
						<input type="radio" bind:group={provider} value="anthropic" />
						<strong>Anthropic (Claude)</strong>
						<p>Best for complex reasoning and coding</p>
					</label>
					<label class="provider-card" class:selected={provider === 'openai'}>
						<input type="radio" bind:group={provider} value="openai" />
						<strong>OpenAI (GPT)</strong>
						<p>Widely used, great general-purpose</p>
					</label>
					<label class="provider-card" class:selected={provider === 'ollama'}>
						<input type="radio" bind:group={provider} value="ollama" />
						<strong>Ollama (Local)</strong>
						<p>Free, private, runs entirely on your machine</p>
					</label>
				</div>

				<div class="btn-row">
					<button class="btn-secondary" onclick={back}>Back</button>
					<button class="btn-primary" onclick={next}>Next</button>
				</div>
			</div>

		{:else if step === 3}
			<div class="step">
				<h2>
					{#if provider === 'ollama'}
						Ollama Setup
					{:else}
						Enter your API key
					{/if}
				</h2>

				{#if provider === 'ollama'}
					<p class="subtitle">Make sure Ollama is running on your machine.</p>
					<div class="info-box">
						<p>Ollama should be running at <code>http://localhost:11434</code>.</p>
						<p>If you haven't installed it yet, visit <a href="https://ollama.com" target="_blank" rel="noopener">ollama.com</a></p>
					</div>
					{#if error}
						<p class="error">{error}</p>
					{/if}
					<div class="btn-row">
						<button class="btn-secondary" onclick={back}>Back</button>
						<button class="btn-primary" onclick={saveOllamaSettings} disabled={saving}>
							{saving ? 'Saving...' : 'Next'}
						</button>
					</div>
				{:else}
					<p class="subtitle">
						{#if provider === 'anthropic'}
							Get your key at <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener">console.anthropic.com</a>
						{:else}
							Get your key at <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">platform.openai.com</a>
						{/if}
					</p>

					<input
						type="password"
						class="key-input"
						bind:value={apiKey}
						placeholder={provider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
					/>

					{#if error}
						<p class="error">{error}</p>
					{/if}

					<div class="btn-row">
						<button class="btn-secondary" onclick={back}>Back</button>
						<button class="btn-primary" onclick={saveApiKey} disabled={saving}>
							{saving ? 'Saving...' : 'Next'}
						</button>
					</div>
				{/if}
			</div>

		{:else if step === 4}
			<div class="step">
				<h2>Claude CLI (Optional)</h2>
				<p class="subtitle">The Claude CLI enables advanced agent capabilities.</p>

				{#if claudeStatus === null}
					<p class="loading-text">Checking...</p>
				{:else if claudeStatus.available}
					<div class="status-box success">
						<strong>Claude CLI found</strong>
						<p>{claudeStatus.path}</p>
					</div>
				{:else}
					<div class="status-box warning">
						<strong>Claude CLI not found</strong>
						<p>This is optional — AshAI works without it.</p>
						<a href={claudeStatus.install_url} target="_blank" rel="noopener">Install Claude CLI</a>
					</div>
				{/if}

				<div class="btn-row">
					<button class="btn-secondary" onclick={back}>Back</button>
					<button class="btn-primary" onclick={finish}>
						{claudeStatus?.available ? 'Done' : 'Skip & Finish'}
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.setup {
		height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--bg-primary);
		padding: 20px;
	}

	.setup-card {
		max-width: 520px;
		width: 100%;
		background: var(--bg-secondary);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 40px;
	}

	.progress {
		display: flex;
		gap: 8px;
		justify-content: center;
		margin-bottom: 32px;
	}

	.progress-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--border);
		transition: background 0.2s;
	}

	.progress-dot.active {
		background: var(--accent);
	}

	.step {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	h1 {
		font-size: 28px;
		font-weight: 700;
		color: var(--accent);
		text-align: center;
	}

	h2 {
		font-size: 22px;
		font-weight: 600;
		text-align: center;
	}

	.subtitle {
		color: var(--text-secondary);
		text-align: center;
		font-size: 14px;
	}

	.features {
		display: flex;
		flex-direction: column;
		gap: 16px;
		margin: 8px 0;
	}

	.feature {
		display: flex;
		gap: 12px;
		align-items: flex-start;
	}

	.feature-icon {
		color: var(--accent);
		font-size: 12px;
		margin-top: 4px;
	}

	.feature strong {
		display: block;
		margin-bottom: 2px;
	}

	.feature p {
		color: var(--text-secondary);
		font-size: 13px;
	}

	.provider-options {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.provider-card {
		display: block;
		padding: 14px 16px;
		border: 1px solid var(--border);
		border-radius: 8px;
		cursor: pointer;
		transition: border-color 0.15s;
	}

	.provider-card:hover {
		border-color: var(--text-muted);
	}

	.provider-card.selected {
		border-color: var(--accent);
		background: rgba(124, 92, 252, 0.05);
	}

	.provider-card input[type="radio"] {
		display: none;
	}

	.provider-card strong {
		display: block;
		margin-bottom: 2px;
	}

	.provider-card p {
		color: var(--text-secondary);
		font-size: 13px;
	}

	.key-input {
		width: 100%;
		padding: 10px 14px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		font-family: monospace;
		font-size: 14px;
	}

	.key-input:focus {
		outline: none;
		border-color: var(--accent);
	}

	.info-box {
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 14px 16px;
		font-size: 13px;
		color: var(--text-secondary);
	}

	.info-box code {
		color: var(--accent);
	}

	.info-box p + p {
		margin-top: 8px;
	}

	.status-box {
		padding: 14px 16px;
		border-radius: 8px;
		border: 1px solid var(--border);
	}

	.status-box.success {
		border-color: var(--success);
	}

	.status-box.warning {
		border-color: var(--warning);
	}

	.status-box strong {
		display: block;
		margin-bottom: 4px;
	}

	.status-box p {
		color: var(--text-secondary);
		font-size: 13px;
	}

	.status-box a {
		display: inline-block;
		margin-top: 8px;
		font-size: 13px;
	}

	.error {
		color: var(--error);
		font-size: 13px;
		text-align: center;
	}

	.loading-text {
		color: var(--text-muted);
		text-align: center;
	}

	.btn-row {
		display: flex;
		gap: 12px;
		justify-content: center;
		margin-top: 8px;
	}

	.btn-primary {
		padding: 10px 28px;
		background: var(--accent);
		color: white;
		border-radius: 8px;
		font-weight: 600;
		font-size: 14px;
		transition: background 0.15s;
	}

	.btn-primary:hover {
		background: var(--accent-hover);
	}

	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-secondary {
		padding: 10px 28px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		font-size: 14px;
		color: var(--text-secondary);
	}

	.btn-secondary:hover {
		background: var(--bg-hover);
	}
</style>
