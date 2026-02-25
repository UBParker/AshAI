/**
 * Chat store — messages for the current thread.
 * Persists messages to localStorage so they survive page reloads.
 */
import { writable, get } from 'svelte/store';
import type { Message, ToolCall } from '$lib/types.js';

const STORAGE_KEY = 'ashai_chat_messages';
const STORAGE_AGENT_KEY = 'ashai_chat_agent_id';

/** Load persisted messages from localStorage */
function loadPersistedMessages(): Message[] {
	if (typeof window === 'undefined') return [];
	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored) {
			const parsed = JSON.parse(stored) as Message[];
			// Ensure no stale streaming state
			return parsed.map(m => ({ ...m, streaming: false }));
		}
	} catch {
		// corrupted data, start fresh
	}
	return [];
}

/** Load persisted agent ID from localStorage */
function loadPersistedAgentId(): string | null {
	if (typeof window === 'undefined') return null;
	try {
		return localStorage.getItem(STORAGE_AGENT_KEY);
	} catch {
		return null;
	}
}

/** Save messages to localStorage (debounced to avoid excessive writes) */
let _saveTimer: ReturnType<typeof setTimeout> | null = null;
function persistMessages(msgs: Message[]): void {
	if (typeof window === 'undefined') return;
	if (_saveTimer) clearTimeout(_saveTimer);
	_saveTimer = setTimeout(() => {
		try {
			// Only persist finalized messages (not streaming)
			const toStore = msgs.filter(m => !m.streaming);
			localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
		} catch {
			// storage full or unavailable
		}
	}, 300);
}

function persistAgentId(agentId: string | null): void {
	if (typeof window === 'undefined') return;
	try {
		if (agentId) {
			localStorage.setItem(STORAGE_AGENT_KEY, agentId);
		} else {
			localStorage.removeItem(STORAGE_AGENT_KEY);
		}
	} catch {
		// storage unavailable
	}
}

export const messages = writable<Message[]>(loadPersistedMessages());
export const isStreaming = writable<boolean>(false);
export const currentAgentId = writable<string | null>(loadPersistedAgentId());  // null = Eve

// Auto-persist on message changes
messages.subscribe(persistMessages);
currentAgentId.subscribe(persistAgentId);

export function addUserMessage(content: string, senderName: string | null = null): void {
	messages.update(msgs => [...msgs, { role: 'user', content, sender_name: senderName }]);
}

export function addAssistantChunk(text: string): void {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.role === 'assistant' && last.streaming) {
			return [...msgs.slice(0, -1), { ...last, content: last.content + text }];
		}
		return [...msgs, { role: 'assistant', content: text, streaming: true, tool_calls: [] }];
	});
}

export function finalizeAssistant(): void {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.streaming) {
			return [...msgs.slice(0, -1), { ...last, streaming: false }];
		}
		return msgs;
	});
}

export function addToolCall(name: string, args: string, id?: string): void {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.role === 'assistant') {
			const toolCalls: ToolCall[] = [...(last.tool_calls || []), {
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

export function updateToolResult(name: string, result: string): void {
	messages.update(msgs => {
		const last = msgs[msgs.length - 1];
		if (last && last.role === 'assistant' && last.tool_calls) {
			const toolCalls = last.tool_calls.map(tc => {
				if (tc.name === name && tc.status === 'running') {
					return { ...tc, status: 'done' as const, result };
				}
				return tc;
			});
			return [...msgs.slice(0, -1), { ...last, tool_calls: toolCalls }];
		}
		return msgs;
	});
}

export function setMessages(newMessages: Array<{ role: string; content: string; sender_name?: string; tool_calls?: ToolCall[] }>): void {
	messages.set(newMessages.map(m => ({
		role: m.role as Message['role'],
		content: m.content,
		sender_name: m.sender_name || null,
		streaming: false,
		tool_calls: m.tool_calls || []
	})).filter(m => m.role !== 'system'));
}

export function clearMessages(): void {
	messages.set([]);
}
