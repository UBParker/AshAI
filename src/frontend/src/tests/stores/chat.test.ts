import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
	messages,
	isStreaming,
	addUserMessage,
	addAssistantChunk,
	finalizeAssistant,
	addToolCall,
	updateToolResult,
	setMessages,
	clearMessages
} from '$lib/stores/chat.js';

describe('Chat Store', () => {
	beforeEach(() => {
		clearMessages();
		isStreaming.set(false);
		localStorage.clear();
	});

	it('starts with empty messages', () => {
		expect(get(messages)).toEqual([]);
	});

	it('adds a user message', () => {
		addUserMessage('Hello');
		const msgs = get(messages);
		expect(msgs).toHaveLength(1);
		expect(msgs[0]).toEqual({ role: 'user', content: 'Hello', sender_name: null });
	});

	it('adds a user message with sender name', () => {
		addUserMessage('Hello', 'Alice');
		const msgs = get(messages);
		expect(msgs[0].sender_name).toBe('Alice');
	});

	it('adds assistant chunks and creates streaming message', () => {
		addAssistantChunk('Hello');
		const msgs = get(messages);
		expect(msgs).toHaveLength(1);
		expect(msgs[0].role).toBe('assistant');
		expect(msgs[0].content).toBe('Hello');
		expect(msgs[0].streaming).toBe(true);
	});

	it('appends to existing streaming assistant message', () => {
		addAssistantChunk('Hello ');
		addAssistantChunk('world');
		const msgs = get(messages);
		expect(msgs).toHaveLength(1);
		expect(msgs[0].content).toBe('Hello world');
	});

	it('creates new assistant message after finalization', () => {
		addAssistantChunk('First');
		finalizeAssistant();
		addAssistantChunk('Second');
		const msgs = get(messages);
		expect(msgs).toHaveLength(2);
		expect(msgs[0].content).toBe('First');
		expect(msgs[0].streaming).toBe(false);
		expect(msgs[1].content).toBe('Second');
		expect(msgs[1].streaming).toBe(true);
	});

	it('finalizes assistant message', () => {
		addAssistantChunk('Done');
		finalizeAssistant();
		const msgs = get(messages);
		expect(msgs[0].streaming).toBe(false);
	});

	it('finalizeAssistant is safe when no messages exist', () => {
		finalizeAssistant();
		expect(get(messages)).toEqual([]);
	});

	it('adds tool calls to assistant message', () => {
		addAssistantChunk('Using tool...');
		addToolCall('read_file', '{"path": "/tmp/test"}', 'tc_1');
		const msgs = get(messages);
		expect(msgs[0].tool_calls).toHaveLength(1);
		expect(msgs[0].tool_calls[0].name).toBe('read_file');
		expect(msgs[0].tool_calls[0].status).toBe('running');
	});

	it('adds multiple tool calls to same message', () => {
		addAssistantChunk('Using tools...');
		addToolCall('read_file', '{}', 'tc_1');
		addToolCall('write_file', '{}', 'tc_2');
		const msgs = get(messages);
		expect(msgs[0].tool_calls).toHaveLength(2);
		expect(msgs[0].tool_calls[0].name).toBe('read_file');
		expect(msgs[0].tool_calls[1].name).toBe('write_file');
	});

	it('updates tool result', () => {
		addAssistantChunk('Using tool...');
		addToolCall('read_file', '{}', 'tc_1');
		updateToolResult('read_file', 'file contents');
		const msgs = get(messages);
		expect(msgs[0].tool_calls[0].status).toBe('done');
		expect(msgs[0].tool_calls[0].result).toBe('file contents');
	});

	it('updateToolResult updates all running tools with matching name', () => {
		addAssistantChunk('Using tools...');
		addToolCall('read_file', '{"path": "/a"}', 'tc_1');
		addToolCall('read_file', '{"path": "/b"}', 'tc_2');
		updateToolResult('read_file', 'result');
		const msgs = get(messages);
		// Both matching running tools get updated
		expect(msgs[0].tool_calls[0].status).toBe('done');
		expect(msgs[0].tool_calls[1].status).toBe('done');
	});

	it('sets messages from thread history', () => {
		setMessages([
			{ role: 'system', content: 'System prompt' },
			{ role: 'user', content: 'Hi' },
			{ role: 'assistant', content: 'Hello!' }
		]);
		const msgs = get(messages);
		// System messages are filtered out
		expect(msgs).toHaveLength(2);
		expect(msgs[0].role).toBe('user');
		expect(msgs[1].role).toBe('assistant');
		expect(msgs[1].streaming).toBe(false);
	});

	it('setMessages preserves sender_name', () => {
		setMessages([
			{ role: 'user', content: 'Hi', sender_name: 'Alice' }
		]);
		const msgs = get(messages);
		expect(msgs[0].sender_name).toBe('Alice');
	});

	it('clears all messages', () => {
		addUserMessage('test');
		addAssistantChunk('response');
		clearMessages();
		expect(get(messages)).toEqual([]);
	});

	it('handles interleaved user and assistant messages', () => {
		addUserMessage('Q1');
		addAssistantChunk('A1');
		finalizeAssistant();
		addUserMessage('Q2');
		addAssistantChunk('A2');
		finalizeAssistant();
		const msgs = get(messages);
		expect(msgs).toHaveLength(4);
		expect(msgs.map(m => m.role)).toEqual(['user', 'assistant', 'user', 'assistant']);
	});

	it('persists finalized messages to localStorage', async () => {
		addUserMessage('Hello');
		addAssistantChunk('Hi there');
		finalizeAssistant();

		// Wait for debounced save (300ms)
		await new Promise(r => setTimeout(r, 400));

		const stored = localStorage.getItem('ashai_chat_messages');
		expect(stored).not.toBeNull();
		const parsed = JSON.parse(stored!);
		expect(parsed).toHaveLength(2);
		expect(parsed[0].content).toBe('Hello');
		expect(parsed[1].content).toBe('Hi there');
	});

	it('does not persist streaming messages', async () => {
		addUserMessage('Hello');
		addAssistantChunk('Still typing...');
		// Don't finalize — message is still streaming

		await new Promise(r => setTimeout(r, 400));

		const stored = localStorage.getItem('ashai_chat_messages');
		expect(stored).not.toBeNull();
		const parsed = JSON.parse(stored!);
		// Only the user message is persisted, not the streaming assistant message
		expect(parsed).toHaveLength(1);
		expect(parsed[0].role).toBe('user');
	});

	it('clearMessages also clears localStorage', async () => {
		addUserMessage('Hello');
		await new Promise(r => setTimeout(r, 400));
		expect(localStorage.getItem('ashai_chat_messages')).not.toBeNull();

		clearMessages();
		await new Promise(r => setTimeout(r, 400));

		const stored = JSON.parse(localStorage.getItem('ashai_chat_messages')!);
		expect(stored).toEqual([]);
	});
});
