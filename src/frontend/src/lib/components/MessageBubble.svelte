<script>
	import { marked } from 'marked';
	import hljs from 'highlight.js';
	import ToolCallBlock from './ToolCallBlock.svelte';

	let { message } = $props();

	// Configure marked with highlight.js
	marked.setOptions({
		highlight: function(code, lang) {
			if (lang && hljs.getLanguage(lang)) {
				return hljs.highlight(code, { language: lang }).value;
			}
			return hljs.highlightAuto(code).value;
		},
		breaks: true,
		gfm: true
	});

	let renderedHtml = $derived(
		message.role !== 'user' && message.content
			? marked.parse(message.content)
			: ''
	);
</script>

<div class="bubble" class:user={message.role === 'user'} class:assistant={message.role !== 'user'}>
	<div class="role-label">{message.role === 'user' ? (message.sender_name || 'You') : 'Assistant'}</div>

	{#if message.tool_calls}
		{#each message.tool_calls as tc (tc.name + tc.id)}
			<ToolCallBlock toolCall={tc} />
		{/each}
	{/if}

	<div class="content">
		{#if message.role === 'user'}
			{message.content}
		{:else if renderedHtml}
			{@html renderedHtml}
		{/if}
		{#if message.streaming}
			<span class="cursor">|</span>
		{/if}
	</div>
</div>

<style>
	.bubble {
		max-width: 80%;
		padding: 10px 14px;
		border-radius: 12px;
		margin-bottom: 8px;
		word-wrap: break-word;
	}
	.user {
		background: var(--user-bubble);
		margin-left: auto;
		white-space: pre-wrap;
	}
	.assistant {
		background: var(--assistant-bubble);
		margin-right: auto;
	}
	.role-label {
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 4px;
		font-weight: 600;
	}
	.content {
		line-height: 1.6;
	}
	/* Markdown content styles */
	.content :global(pre) {
		background: var(--bg-tertiary);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 12px;
		overflow-x: auto;
		margin: 8px 0;
	}
	.content :global(code) {
		font-family: 'SF Mono', 'Fira Code', monospace;
		font-size: 13px;
	}
	.content :global(p code) {
		background: var(--bg-tertiary);
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 12px;
	}
	.content :global(p) {
		margin: 4px 0;
	}
	.content :global(ul), .content :global(ol) {
		padding-left: 20px;
		margin: 4px 0;
	}
	.content :global(blockquote) {
		border-left: 3px solid var(--accent);
		padding-left: 12px;
		color: var(--text-secondary);
		margin: 8px 0;
	}
	.content :global(h1), .content :global(h2), .content :global(h3) {
		margin: 12px 0 4px;
	}
	.content :global(table) {
		border-collapse: collapse;
		margin: 8px 0;
	}
	.content :global(th), .content :global(td) {
		border: 1px solid var(--border);
		padding: 6px 10px;
	}
	.cursor {
		animation: blink 0.8s infinite;
		color: var(--accent);
	}
	@keyframes blink {
		0%, 50% { opacity: 1; }
		51%, 100% { opacity: 0; }
	}
</style>
