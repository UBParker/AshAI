<script>
	import { goto } from '$app/navigation';
	import { getSettings, putSettings, checkClaudeCli, listProviders, listModels } from '$lib/api/client.js';

	let step = $state(1);
	let provider = $state('anthropic');
	let apiKey = $state('');
	let model = $state('');
	let availableModels = $state([]);
	let saving = $state(false);
	let testing = $state(false);
	let error = $state('');
	let claudeStatus = $state(null);
	let currentSettings = $state(null);

	const totalSteps = 4;

	const providerInfo = {
		anthropic: {
			name: 'Anthropic (Claude)',
			description: 'Best for complex reasoning and coding',
			keyPrefix: 'sk-ant-',
			keyUrl: 'https://console.anthropic.com/settings/keys',
			billingUrl: 'https://console.anthropic.com/settings/billing',
			envKey: 'ANTHROPIC_API_KEY'
		},
		openai: {
			name: 'OpenAI (GPT)',
			description: 'Widely used, great general-purpose',
			keyPrefix: 'sk-',
			keyUrl: 'https://platform.openai.com/api-keys',
			billingUrl: 'https://platform.openai.com/usage',
			envKey: 'OPENAI_API_KEY'
		},
		ollama: {
			name: 'Ollama (Local)',
			description: 'Free, private, runs entirely on your machine',
			keyPrefix: '',
			keyUrl: '',
			billingUrl: '',
			envKey: ''
		},
		gemini: {
			name: 'Google Gemini',
			description: 'Google\'s multimodal AI models',
			keyPrefix: '',
			keyUrl: 'https://aistudio.google.com/app/apikey',
			billingUrl: '',
			envKey: 'GEMINI_API_KEY'
		}
	};

	async function loadCurrentSettings() {
		try {
			currentSettings = await getSettings();
			// Pre-select current provider if one exists
			if (currentSettings.has_anthropic_key) provider = 'anthropic';
			else if (currentSettings.has_openai_key) provider = 'openai';
			else if (currentSettings.has_gemini_key) provider = 'gemini';
		} catch {
			// Settings not available yet
		}
	}

	async function loadModels() {
		if (provider === 'ollama') {
			// For Ollama, we'll show common models
			availableModels = [
				{ id: 'llama3.2', name: 'Llama 3.2 (Latest)' },
				{ id: 'llama3.1', name: 'Llama 3.1' },
				{ id: 'mistral', name: 'Mistral' },
				{ id: 'codellama', name: 'Code Llama' },
				{ id: 'gemma2', name: 'Gemma 2' }
			];
			model = 'llama3.2';
			return;
		}

		try {
			testing = true;
			const response = await listModels(provider);
			availableModels = response.models.map(m => ({
				id: m,
				name: formatModelName(m)
			}));
			// Select the best model by default
			if (availableModels.length > 0) {
				model = availableModels[0].id;
			}
		} catch (err) {
			// If we can't load models, provide sensible defaults
			if (provider === 'anthropic') {
				availableModels = [
					{ id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4 (Latest)' },
					{ id: 'claude-haiku-4-20250414', name: 'Claude Haiku 4 (Fast)' },
					{ id: 'claude-opus-4-20250514', name: 'Claude Opus 4 (Most capable)' }
				];
				model = 'claude-sonnet-4-20250514';
			} else if (provider === 'openai') {
				availableModels = [
					{ id: 'gpt-4-turbo-preview', name: 'GPT-4 Turbo' },
					{ id: 'gpt-4', name: 'GPT-4' },
					{ id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo' }
				];
				model = 'gpt-4-turbo-preview';
			} else if (provider === 'gemini') {
				availableModels = [
					{ id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro' },
					{ id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash' }
				];
				model = 'gemini-1.5-pro';
			}
		} finally {
			testing = false;
		}
	}

	function formatModelName(modelId) {
		// Clean up model IDs for display
		return modelId
			.replace(/-\d{8}$/, '') // Remove date suffixes
			.replace(/-/g, ' ')
			.replace(/\b\w/g, l => l.toUpperCase());
	}

	function next() {
		error = '';
		step++;
		if (step === 3) {
			loadModels();
		} else if (step === 4) {
			loadClaudeStatus();
		}
	}

	function back() {
		error = '';
		step--;
	}

	async function testConnection() {
		if (!apiKey.trim() && provider !== 'ollama') {
			error = 'Please enter an API key.';
			return;
		}

		testing = true;
		error = '';

		try {
			// Save settings temporarily
			const settings = {
				DEFAULT_PROVIDER: provider,
				DEFAULT_MODEL: model
			};

			if (provider !== 'ollama') {
				const envKey = providerInfo[provider].envKey;
				settings[envKey] = apiKey.trim();
			}

			await putSettings(settings);

			// Try to list models to verify the key works
			try {
				await listModels(provider);
				// Success! Move to next step
				next();
			} catch (testErr) {
				// Check if it's a credit/billing issue
				if (testErr.message.includes('credit') || testErr.message.includes('billing')) {
					error = `API key is valid but you need to add credits. Visit ${providerInfo[provider].billingUrl}`;
				} else if (testErr.message.includes('401') || testErr.message.includes('403')) {
					error = 'Invalid API key. Please check and try again.';
				} else {
					error = `Connection failed: ${testErr.message}`;
				}
			}
		} catch (err) {
			error = `Failed to save settings: ${err.message}`;
		} finally {
			testing = false;
		}
	}

	async function saveOllamaSettings() {
		saving = true;
		error = '';
		try {
			await putSettings({
				DEFAULT_PROVIDER: 'ollama',
				DEFAULT_MODEL: model,
				OLLAMA_BASE_URL: 'http://localhost:11434'
			});

			// Try to verify Ollama is running
			try {
				await listModels('ollama');
				next();
			} catch {
				error = 'Cannot connect to Ollama. Make sure it\'s running at http://localhost:11434';
			}
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
			claudeStatus = {
				available: false,
				path: null,
				install_url: 'https://docs.anthropic.com/en/docs/claude-code/overview'
			};
		}
	}

	function finish() {
		goto('/');
	}

	$effect(() => {
		if (step === 1) {
			loadCurrentSettings();
		}
	});
</script>

<div class="setup">
	<button class="back-button" onclick={() => goto('/')} title="Back to Chat">
		<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M15 18l-6-6 6-6"/>
		</svg>
		Back to Chat
	</button>

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
						<span class="feature-icon">◈</span>
						<div>
							<strong>Multi-agent coordination</strong>
							<p>Ash orchestrates specialized agents that work together</p>
						</div>
					</div>
					<div class="feature">
						<span class="feature-icon">◈</span>
						<div>
							<strong>Local-first</strong>
							<p>Your data stays on your machine, always</p>
						</div>
					</div>
					<div class="feature">
						<span class="feature-icon">◈</span>
						<div>
							<strong>Provider-agnostic</strong>
							<p>Works with Anthropic, OpenAI, Gemini, or local models via Ollama</p>
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
					{#each Object.entries(providerInfo) as [key, info]}
						<label class="provider-card" class:selected={provider === key}>
							<input type="radio" bind:group={provider} value={key} />
							<strong>{info.name}</strong>
							<p>{info.description}</p>
							{#if currentSettings && key === 'anthropic' && currentSettings.has_anthropic_key}
								<span class="status-badge">Configured ✓</span>
							{:else if currentSettings && key === 'openai' && currentSettings.has_openai_key}
								<span class="status-badge">Configured ✓</span>
							{:else if currentSettings && key === 'gemini' && currentSettings.has_gemini_key}
								<span class="status-badge">Configured ✓</span>
							{/if}
						</label>
					{/each}
				</div>

				<div class="btn-row">
					<button class="btn-secondary" onclick={back}>Back</button>
					<button class="btn-primary" onclick={next}>Next</button>
				</div>
			</div>

		{:else if step === 3}
			<div class="step">
				<h2>Configure {providerInfo[provider].name}</h2>

				{#if provider === 'ollama'}
					<p class="subtitle">Select a model and ensure Ollama is running.</p>

					<div class="form-group">
						<label>Model</label>
						<select bind:value={model} class="model-select">
							{#each availableModels as m}
								<option value={m.id}>{m.name}</option>
							{/each}
						</select>
					</div>

					<div class="info-box">
						<p>Ollama should be running at <code>http://localhost:11434</code></p>
						<p>To install a model: <code>ollama pull {model}</code></p>
						<p>If you haven't installed Ollama yet, visit <a href="https://ollama.com" target="_blank" rel="noopener">ollama.com</a></p>
					</div>

					{#if error}
						<div class="error-box">{error}</div>
					{/if}

					<div class="btn-row">
						<button class="btn-secondary" onclick={back}>Back</button>
						<button class="btn-primary" onclick={saveOllamaSettings} disabled={saving}>
							{saving ? 'Verifying...' : 'Verify & Continue'}
						</button>
					</div>
				{:else}
					<p class="subtitle">Enter your API key and select a model.</p>

					<div class="form-group">
						<label>
							API Key
							<a href={providerInfo[provider].keyUrl} target="_blank" rel="noopener" class="help-link">
								Get your key →
							</a>
						</label>
						<input
							type="password"
							class="key-input"
							bind:value={apiKey}
							placeholder={providerInfo[provider].keyPrefix + '...'}
						/>
					</div>

					<div class="form-group">
						<label>Model</label>
						{#if testing}
							<div class="loading-text">Loading available models...</div>
						{:else}
							<select bind:value={model} class="model-select">
								{#each availableModels as m}
									<option value={m.id}>{m.name}</option>
								{/each}
							</select>
						{/if}
					</div>

					{#if error}
						<div class="error-box">
							{error}
							{#if error.includes('credit') || error.includes('billing')}
								<a href={providerInfo[provider].billingUrl} target="_blank" rel="noopener" class="error-link">
									Add credits →
								</a>
							{/if}
						</div>
					{/if}

					<div class="btn-row">
						<button class="btn-secondary" onclick={back}>Back</button>
						<button class="btn-primary" onclick={testConnection} disabled={testing || !model}>
							{testing ? 'Testing...' : 'Test & Continue'}
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
						<strong>✓ Claude CLI found</strong>
						<p>{claudeStatus.path}</p>
					</div>
				{:else}
					<div class="status-box warning">
						<strong>Claude CLI not found</strong>
						<p>This is optional — AshAI works without it.</p>
						<a href={claudeStatus.install_url} target="_blank" rel="noopener">Install Claude CLI →</a>
					</div>
				{/if}

				<div class="success-message">
					<h3>✨ Setup Complete!</h3>
					<p>Your AI provider is configured and ready to use.</p>
				</div>

				<div class="btn-row">
					<button class="btn-secondary" onclick={back}>Back</button>
					<button class="btn-primary" onclick={finish}>Start Using AshAI</button>
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

	.back-button {
		position: absolute;
		top: 20px;
		left: 20px;
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 16px;
		border-radius: 6px;
		background: var(--bg-secondary);
		color: var(--text-secondary);
		font-size: 14px;
		border: 1px solid var(--border);
		transition: all 0.15s;
	}

	.back-button:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
		border-color: var(--text-muted);
	}

	.setup-card {
		max-width: 560px;
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
		gap: 20px;
	}

	h1 {
		font-size: 28px;
		font-weight: 700;
		color: var(--accent);
		text-align: center;
		margin: 0;
	}

	h2 {
		font-size: 22px;
		font-weight: 600;
		text-align: center;
		margin: 0;
	}

	h3 {
		font-size: 18px;
		font-weight: 600;
		margin: 0;
	}

	.subtitle {
		color: var(--text-secondary);
		text-align: center;
		font-size: 14px;
		margin: 0;
	}

	.features {
		display: flex;
		flex-direction: column;
		gap: 16px;
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
		margin: 0;
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
		transition: all 0.15s;
		position: relative;
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
		margin: 0;
	}

	.status-badge {
		position: absolute;
		top: 14px;
		right: 16px;
		font-size: 12px;
		color: var(--success);
		font-weight: 600;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.form-group label {
		font-size: 14px;
		font-weight: 600;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.help-link {
		font-size: 12px;
		font-weight: normal;
		color: var(--accent);
		text-decoration: none;
	}

	.help-link:hover {
		text-decoration: underline;
	}

	.key-input, .model-select {
		width: 100%;
		padding: 10px 14px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		font-size: 14px;
		color: var(--text-primary);
	}

	.key-input {
		font-family: monospace;
	}

	.key-input:focus, .model-select:focus {
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
		background: var(--bg-primary);
		padding: 2px 4px;
		border-radius: 3px;
	}

	.info-box p {
		margin: 0;
	}

	.info-box p + p {
		margin-top: 8px;
	}

	.error-box {
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 8px;
		padding: 12px 16px;
		color: var(--error);
		font-size: 13px;
	}

	.error-link {
		display: inline-block;
		margin-top: 8px;
		color: var(--accent);
		font-size: 12px;
		text-decoration: none;
	}

	.error-link:hover {
		text-decoration: underline;
	}

	.status-box {
		padding: 14px 16px;
		border-radius: 8px;
		border: 1px solid var(--border);
	}

	.status-box.success {
		border-color: var(--success);
		background: rgba(34, 197, 94, 0.05);
	}

	.status-box.warning {
		border-color: var(--warning);
		background: rgba(251, 146, 60, 0.05);
	}

	.status-box strong {
		display: block;
		margin-bottom: 4px;
		color: var(--text-primary);
	}

	.status-box p {
		color: var(--text-secondary);
		font-size: 13px;
		margin: 0;
	}

	.status-box a {
		display: inline-block;
		margin-top: 8px;
		font-size: 13px;
		color: var(--accent);
		text-decoration: none;
	}

	.status-box a:hover {
		text-decoration: underline;
	}

	.success-message {
		background: rgba(34, 197, 94, 0.05);
		border: 1px solid rgba(34, 197, 94, 0.3);
		border-radius: 8px;
		padding: 16px;
		text-align: center;
	}

	.success-message h3 {
		color: var(--success);
		margin-bottom: 8px;
	}

	.success-message p {
		color: var(--text-secondary);
		font-size: 14px;
		margin: 0;
	}

	.loading-text {
		color: var(--text-muted);
		text-align: center;
		padding: 10px;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		font-size: 13px;
	}

	.btn-row {
		display: flex;
		gap: 12px;
		justify-content: center;
	}

	.btn-primary, .btn-secondary {
		padding: 10px 28px;
		border-radius: 8px;
		font-size: 14px;
		font-weight: 600;
		transition: all 0.15s;
		border: none;
		cursor: pointer;
	}

	.btn-primary {
		background: var(--accent);
		color: white;
	}

	.btn-primary:hover:not(:disabled) {
		background: var(--accent-hover);
	}

	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-secondary {
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		color: var(--text-secondary);
	}

	.btn-secondary:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}
</style>