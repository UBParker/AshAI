<script>
	import MessageBubble from './MessageBubble.svelte';
	import { messages, isStreaming, addUserMessage, addAssistantChunk, finalizeAssistant, addToolCall, updateToolResult } from '$lib/stores/chat.js';
	import { chatStream, cancelAgent } from '$lib/api/client.js';
	import { currentProject } from '$lib/stores/projects.js';
	import { currentUser } from '$lib/auth.js';
	import { onMount } from 'svelte';

	let { agentId = null } = $props();
	let inputText = $state('');
	let messagesEl = $state(null);
	let currentStreamAbortController = null;

	function scrollToBottom() {
		if (messagesEl) {
			requestAnimationFrame(() => {
				messagesEl.scrollTop = messagesEl.scrollHeight;
			});
		}
	}

	// Auto-scroll on new messages
	$effect(() => {
		// Access $messages to track dependency
		$messages;
		scrollToBottom();
	});

	async function handleSend() {
		const text = inputText.trim();
		if (!text || $isStreaming) return;

		// In project mode, include sender name
		const senderName = $currentProject ? ($currentUser?.email?.split('@')[0] || null) : null;

		inputText = '';
		addUserMessage(text, senderName);
		isStreaming.set(true);
		let wasQueued = false;

		try {
			// Store abort controller for potential cancellation
			currentStreamAbortController = new AbortController();

			await chatStream(text, agentId, (event) => {
				if (event.type === 'content') {
					addAssistantChunk(event.text);
				} else if (event.type === 'tool_call') {
					addToolCall(event.name, event.arguments);
				} else if (event.type === 'tool_result') {
					updateToolResult(event.name, event.result);
				} else if (event.type === 'queued') {
					// Mark as queued but keep streaming state so user can cancel
					wasQueued = true;
					addAssistantChunk(`Ash is responding to another team member. Your message is queued (position ${event.position})...\n\n`);
				} else if (event.type === 'cancelled') {
					addAssistantChunk('\n[Response cancelled]');
					finalizeAssistant();
					wasQueued = false;  // Cancelled, so not queued anymore
				} else if (event.type === 'done') {
					finalizeAssistant();
					wasQueued = false;  // Completed, so not queued anymore
				}
			}, senderName);
		} catch (e) {
			addAssistantChunk(`\n[Error: ${e.message}]`);
			finalizeAssistant();
			wasQueued = false;
		} finally {
			// Only set isStreaming to false if not queued
			// If queued, keep it true so user can cancel
			if (!wasQueued) {
				isStreaming.set(false);
			}
			currentStreamAbortController = null;
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	async function handleCancel() {
		if (!$isStreaming || !agentId) return;

		try {
			// Cancel the agent operation
			await cancelAgent(agentId);

			// Abort the stream if possible
			if (currentStreamAbortController) {
				currentStreamAbortController.abort();
			}

			// Reset streaming state and add cancelled message
			isStreaming.set(false);
			addAssistantChunk('\n[Response cancelled by user]');
			finalizeAssistant();
		} catch (e) {
			console.error('Failed to cancel:', e);
		}
	}

	// Global ESC key handler
	onMount(() => {
		function handleGlobalKeydown(e) {
			if (e.key === 'Escape' && $isStreaming) {
				e.preventDefault();
				handleCancel();
			}
		}

		document.addEventListener('keydown', handleGlobalKeydown);
		return () => document.removeEventListener('keydown', handleGlobalKeydown);
	});
</script>

<div class="chat-panel">
	<div class="messages" bind:this={messagesEl}>
		{#if $messages.length === 0}
			<div class="empty">
				<p class="greeting">Hello! I'm Ash, your AI assistant.</p>
				<p class="hint">How can I help you today?</p>
			</div>
		{:else}
			{#each $messages as message, i (i)}
				<MessageBubble {message} />
			{/each}
		{/if}
	</div>
	<div class="input-area">
		<textarea
			bind:value={inputText}
			onkeydown={handleKeydown}
			placeholder="Message Ash..."
			rows="1"
			disabled={$isStreaming}
		></textarea>
		{#if $isStreaming}
			<button class="cancel-btn" onclick={handleCancel} title="Cancel (ESC)">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<rect x="4" y="4" width="16" height="16" rx="2"/>
				</svg>
			</button>
		{:else}
			<button class="send-btn" onclick={handleSend} disabled={!inputText.trim()}>
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<line x1="22" y1="2" x2="11" y2="13"/>
					<polygon points="22 2 15 22 11 13 2 9 22 2"/>
				</svg>
			</button>
		{/if}
	</div>
</div>

<style>
	.chat-panel {
		display: flex;
		flex-direction: column;
		height: 100%;
		flex: 1;
	}
	.messages {
		flex: 1;
		overflow-y: auto;
		padding: 20px;
		display: flex;
		flex-direction: column;
	}
	.empty {
		margin: auto;
		text-align: center;
	}
	.greeting {
		font-size: 20px;
		font-weight: 600;
		margin-bottom: 8px;
	}
	.hint {
		color: var(--text-secondary);
	}
	.input-area {
		padding: 12px 20px 20px;
		display: flex;
		gap: 8px;
		align-items: flex-end;
	}
	textarea {
		flex: 1;
		resize: none;
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 10px 14px;
		min-height: 44px;
		max-height: 160px;
		outline: none;
	}
	textarea:focus {
		border-color: var(--accent);
	}
	.send-btn {
		width: 44px;
		height: 44px;
		border-radius: 12px;
		background: var(--accent);
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.send-btn:hover:not(:disabled) {
		background: var(--accent-hover);
	}
	.send-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.cancel-btn {
		width: 44px;
		height: 44px;
		border-radius: 12px;
		background: var(--error);
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.cancel-btn:hover {
		background: var(--error-hover);
	}
</style>
