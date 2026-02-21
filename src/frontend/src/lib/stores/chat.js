/**
 * Chat store — messages for the current thread.
 */
import { writable, get } from 'svelte/store';

export const messages = writable([]);
export const isStreaming = writable(false);
export const currentAgentId = writable(null);  // null = Eve

export function addUserMessage(content, senderName = null) {
	messages.update(msgs => [...msgs, { role: 'user', content, sender_name: senderName }]);
}

export function addAssistantChunk(text) {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.role === 'assistant' && last.streaming) {
			return [...msgs.slice(0, -1), { ...last, content: last.content + text }];
		}
		return [...msgs, { role: 'assistant', content: text, streaming: true, tool_calls: [] }];
	});
}

export function finalizeAssistant() {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.streaming) {
			return [...msgs.slice(0, -1), { ...last, streaming: false }];
		}
		return msgs;
	});
}

export function addToolCall(name, args, id) {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.role === 'assistant') {
			const toolCalls = [...(last.tool_calls || []), {
				id: id || `tc_${Date.now()}`,
				name,
				arguments: args,
				status: 'running',
				result: null
			}];
			return [...msgs.slice(0, -1), { ...last, tool_calls: toolCalls }];
		}
		return msgs;
	});
}

export function updateToolResult(name, result) {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.role === 'assistant' && last.tool_calls) {
			const toolCalls = last.tool_calls.map(tc => {
				if (tc.name === name && tc.status === 'running') {
					return { ...tc, status: 'done', result };
				}
				return tc;
			});
			return [...msgs.slice(0, -1), { ...last, tool_calls: toolCalls }];
		}
		return msgs;
	});
}

export function setMessages(newMessages) {
	messages.set(newMessages.map(m => ({
		role: m.role,
		content: m.content,
		sender_name: m.sender_name || null,
		streaming: false,
		tool_calls: m.tool_calls || []
	})).filter(m => m.role !== 'system'));
}

export function clearMessages() {
	messages.set([]);
}
