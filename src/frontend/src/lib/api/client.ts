/**
 * AshAI API client — HTTP, SSE, and WebSocket.
 * In web mode, all requests go through the gateway proxy with JWT auth.
 */

import { getAccessToken, isAuthEnabled } from '$lib/auth.js';
import type {
	Agent,
	AgentCreateData,
	AgentUpdateData,
	AgentTemplate,
	Message,
	Settings,
	KnowledgeItem,
	Provider,
	PendingApproval,
	ChatStreamEvent,
	WebSocketEvent,
} from '$lib/types.js';

let _backendBase = '';  // proxied via vite in dev, set dynamically in Tauri

/** Check if running inside a Tauri webview */
export function isTauri(): boolean {
	return typeof window !== 'undefined' && (window as any).__TAURI_INTERNALS__ !== undefined;
}

/** Set the backend base URL (called when Tauri sidecar reports its port) */
export function setBackendUrl(url: string): void {
	_backendBase = url.replace(/\/$/, '');
}

/** Wait for the backend to be ready by polling /api/health */
export async function waitForBackend(maxRetries: number = 30, intervalMs: number = 500): Promise<boolean> {
	for (let i = 0; i < maxRetries; i++) {
		try {
			const headers = await _authHeaders();
			const res = await fetch(`${_backendBase}/api/health`, { headers });
			if (res.ok) return true;
		} catch {
			// not ready yet
		}
		await new Promise(r => setTimeout(r, intervalMs));
	}
	throw new Error('Backend did not start in time');
}

/** Build auth headers for gateway proxy mode */
async function _authHeaders(): Promise<Record<string, string>> {
	if (!isAuthEnabled() || isTauri()) return {};
	const token = await getAccessToken();
	if (!token) return {};
	return { 'Authorization': `Bearer ${token}` };
}

/** Standard JSON fetch wrapper */
async function apiFetch<T = any>(path: string, options: RequestInit = {}): Promise<T> {
	const authHeaders = await _authHeaders();
	const res = await fetch(`${_backendBase}${path}`, {
		headers: { 'Content-Type': 'application/json', ...authHeaders, ...options.headers },
		...options
	});
	if (!res.ok) {
		const body = await res.text();
		throw new Error(`API ${res.status}: ${body}`);
	}
	return res.json();
}

// --- Agents ---

export function listAgents(): Promise<Agent[]> {
	return apiFetch<Agent[]>('/api/agents');
}

export function getAgent(id: string): Promise<Agent> {
	return apiFetch<Agent>(`/api/agents/${id}`);
}

export function getThread(agentId: string): Promise<Message[]> {
	return apiFetch<Message[]>(`/api/agents/${agentId}/thread`);
}

export function destroyAgent(id: string): Promise<void> {
	return apiFetch(`/api/agents/${id}`, { method: 'DELETE' });
}

export function createAgent(data: AgentCreateData): Promise<Agent> {
	return apiFetch<Agent>('/api/agents', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function updateAgent(id: string, data: AgentUpdateData): Promise<Agent> {
	return apiFetch<Agent>(`/api/agents/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export function cancelAgent(id: string): Promise<void> {
	return apiFetch(`/api/agents/${id}/cancel`, {
		method: 'POST'
	});
}

export async function sendMessage(agentId: string, message: string): Promise<string> {
	// Send message and collect the full response
	let fullResponse = '';
	await chatStream(
		message,
		agentId,
		(event) => {
			if (event.type === 'content') {
				fullResponse += event.text;
			}
		}
	);
	return fullResponse;
}

// --- Providers ---

export function listProviders(): Promise<Provider[]> {
	return apiFetch<Provider[]>('/api/providers');
}

export function listModels(providerName: string): Promise<string[]> {
	return apiFetch<{provider: string, models: string[]}>(`/api/providers/${providerName}/models`)
		.then(data => data.models || []);
}

// --- Tools ---

export function listTools(): Promise<any[]> {
	return apiFetch<any[]>('/api/tools');
}

// --- Approvals ---

export function listPendingApprovals(): Promise<PendingApproval[]> {
	return apiFetch<PendingApproval[]>('/api/approvals');
}

export function approveAction(id: string): Promise<void> {
	return apiFetch(`/api/approvals/${id}/approve`, { method: 'POST' });
}

export function denyAction(id: string): Promise<void> {
	return apiFetch(`/api/approvals/${id}/deny`, { method: 'POST' });
}

// --- Settings ---

export function getSettings(): Promise<Settings & { has_any_key?: boolean }> {
	return apiFetch('/api/settings');
}

export function putSettings(data: Partial<Settings>): Promise<Settings> {
	return apiFetch<Settings>('/api/settings', {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export function checkClaudeCli(): Promise<{ available: boolean }> {
	return apiFetch('/api/settings/claude-cli');
}

// --- Health ---

export function health(): Promise<{ status: string }> {
	return apiFetch('/api/health');
}

// --- Knowledge Base ---

export function listKnowledge(): Promise<KnowledgeItem[]> {
	return apiFetch<KnowledgeItem[]>('/api/knowledge');
}

export function addKnowledge(data: Omit<KnowledgeItem, 'id'>): Promise<KnowledgeItem> {
	return apiFetch<KnowledgeItem>('/api/knowledge', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function updateKnowledge(id: string, data: Partial<KnowledgeItem>): Promise<KnowledgeItem> {
	return apiFetch<KnowledgeItem>(`/api/knowledge/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export function deleteKnowledge(id: string): Promise<void> {
	return apiFetch(`/api/knowledge/${id}`, { method: 'DELETE' });
}

// --- Agent Templates ---

export function listTemplates(): Promise<AgentTemplate[]> {
	return apiFetch<AgentTemplate[]>('/api/templates');
}

export function createTemplate(data: Omit<AgentTemplate, 'id'>): Promise<AgentTemplate> {
	return apiFetch<AgentTemplate>('/api/templates', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function deleteTemplate(id: string): Promise<void> {
	return apiFetch(`/api/templates/${id}`, { method: 'DELETE' });
}

export function saveAgentAsTemplate(agentId: string, displayName: string, description: string = ''): Promise<AgentTemplate> {
	return apiFetch<AgentTemplate>(`/api/templates/from-agent/${agentId}`, {
		method: 'POST',
		body: JSON.stringify({ display_name: displayName, description })
	});
}

export async function exportTemplates(): Promise<void> {
	const authHeaders = await _authHeaders();
	const res = await fetch(`${_backendBase}/api/templates/export`, {
		headers: { ...authHeaders },
	});
	if (!res.ok) {
		throw new Error(`Export failed: ${res.status}`);
	}
	const blob = await res.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'agent_templates.json';
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
}

export async function importTemplates(file: File): Promise<{ imported: number; skipped: number }> {
	const authHeaders = await _authHeaders();
	const formData = new FormData();
	formData.append('file', file);
	const res = await fetch(`${_backendBase}/api/templates/import`, {
		method: 'POST',
		headers: { ...authHeaders },
		body: formData,
	});
	if (!res.ok) {
		const body = await res.text();
		throw new Error(`Import failed ${res.status}: ${body}`);
	}
	return res.json();
}

// --- Instance Info ---

export function getInstanceInfo(): Promise<Record<string, unknown>> {
	return apiFetch('/api/instance-info');
}

// --- SSE Chat ---

/**
 * Send a chat message and receive streaming SSE events.
 */
export async function chatStream(
	message: string,
	agentId: string | null,
	onEvent: (event: ChatStreamEvent) => void,
	senderName: string | null = null
): Promise<void> {
	const path = agentId ? `/api/agents/${agentId}/message` : '/api/chat';
	const body = agentId
		? { message, sender_name: senderName }
		: { message, agent_id: agentId, sender_name: senderName };

	const authHeaders = await _authHeaders();
	const res = await fetch(`${_backendBase}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', ...authHeaders },
		body: JSON.stringify(body)
	});

	if (!res.ok) {
		const text = await res.text();
		throw new Error(`Chat API ${res.status}: ${text}`);
	}

	const reader = res.body!.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;

		buffer += decoder.decode(value, { stream: true });
		const lines = buffer.split('\n');
		buffer = lines.pop() || '';

		for (const line of lines) {
			if (line.startsWith('data: ')) {
				try {
					const data = JSON.parse(line.slice(6));
					onEvent(data);
				} catch {
					// skip malformed
				}
			}
		}
	}
}

// --- WebSocket ---

let _ws: WebSocket | null = null;
let _shouldReconnect = true;
let _wsOnEvent: ((event: WebSocketEvent) => void) | null = null;
let _reconnectAttempt = 0;
const _WS_BASE_DELAY = 1000;
const _WS_MAX_DELAY = 30000;

/**
 * Disconnect the WebSocket cleanly (for context switching).
 */
export function disconnectWebSocket(): void {
	_shouldReconnect = false;
	_reconnectAttempt = 0;
	if (_ws) {
		_ws.close();
		_ws = null;
	}
}

/**
 * Connect to the agent events WebSocket.
 */
export async function connectWebSocket(onEvent: (event: WebSocketEvent) => void): Promise<{ close: () => void }> {
	_shouldReconnect = true;
	_wsOnEvent = onEvent;

	let wsUrl: string;
	if (_backendBase) {
		// Tauri/gateway mode: construct from backend base URL
		const base = _backendBase.replace(/^http/, 'ws');
		wsUrl = `${base}/api/ws`;
	} else {
		// Same-origin mode: use current page host
		const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
		wsUrl = `${protocol}//${location.host}/api/ws`;
	}

	// In web auth mode, pass token as query parameter
	if (isAuthEnabled() && !isTauri()) {
		const token = await getAccessToken();
		if (token) {
			wsUrl += `?token=${encodeURIComponent(token)}`;
		}
	}

	const ws = new WebSocket(wsUrl);
	_ws = ws;

	ws.onopen = () => {
		_reconnectAttempt = 0;
	};

	ws.onmessage = (event: MessageEvent) => {
		try {
			const data = JSON.parse(event.data);
			onEvent(data);
		} catch {
			// skip
		}
	};

	ws.onclose = () => {
		if (_shouldReconnect && _wsOnEvent) {
			const delay = Math.min(_WS_BASE_DELAY * Math.pow(2, _reconnectAttempt), _WS_MAX_DELAY);
			// Add jitter (±25%) to prevent thundering herd
			const jitter = delay * (0.75 + Math.random() * 0.5);
			_reconnectAttempt++;
			console.log(`[WS] Reconnecting in ${Math.round(jitter)}ms (attempt ${_reconnectAttempt})`);
			setTimeout(() => connectWebSocket(_wsOnEvent!), jitter);
		}
	};

	return { close: () => ws.close() };
}

// --- Exported for testing ---
export const _testing = {
	get WS_BASE_DELAY() { return _WS_BASE_DELAY; },
	get WS_MAX_DELAY() { return _WS_MAX_DELAY; },
};
