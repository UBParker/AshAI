/**
 * AshAI API client — HTTP, SSE, and WebSocket.
 * In web mode, all requests go through the gateway proxy with JWT auth.
 */

import { getAccessToken, isAuthEnabled } from '$lib/auth.js';

let _backendBase = '';  // proxied via vite in dev, set dynamically in Tauri

/** Check if running inside a Tauri webview */
export function isTauri() {
	return typeof window !== 'undefined' && window.__TAURI_INTERNALS__ !== undefined;
}

/** Set the backend base URL (called when Tauri sidecar reports its port) */
export function setBackendUrl(url) {
	_backendBase = url.replace(/\/$/, '');
}

/** Wait for the backend to be ready by polling /api/health */
export async function waitForBackend(maxRetries = 30, intervalMs = 500) {
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
async function _authHeaders() {
	if (!isAuthEnabled() || isTauri()) return {};
	const token = await getAccessToken();
	if (!token) return {};
	return { 'Authorization': `Bearer ${token}` };
}

/** Standard JSON fetch wrapper */
async function apiFetch(path, options = {}) {
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

export function listAgents() {
	return apiFetch('/api/agents');
}

export function getAgent(id) {
	return apiFetch(`/api/agents/${id}`);
}

export function getThread(agentId) {
	return apiFetch(`/api/agents/${agentId}/thread`);
}

export function destroyAgent(id) {
	return apiFetch(`/api/agents/${id}`, { method: 'DELETE' });
}

export function createAgent(data) {
	return apiFetch('/api/agents', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

// --- Providers ---

export function listProviders() {
	return apiFetch('/api/providers');
}

export function listModels(providerName) {
	return apiFetch(`/api/providers/${providerName}/models`);
}

// --- Tools ---

export function listTools() {
	return apiFetch('/api/tools');
}

// --- Approvals ---

export function listPendingApprovals() {
	return apiFetch('/api/approvals');
}

export function approveAction(id) {
	return apiFetch(`/api/approvals/${id}/approve`, { method: 'POST' });
}

export function denyAction(id) {
	return apiFetch(`/api/approvals/${id}/deny`, { method: 'POST' });
}

// --- Settings ---

export function getSettings() {
	return apiFetch('/api/settings');
}

export function putSettings(data) {
	return apiFetch('/api/settings', {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export function checkClaudeCli() {
	return apiFetch('/api/settings/claude-cli');
}

// --- Health ---

export function health() {
	return apiFetch('/api/health');
}

// --- Knowledge Base ---

export function listKnowledge() {
	return apiFetch('/api/knowledge');
}

export function addKnowledge(data) {
	return apiFetch('/api/knowledge', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function updateKnowledge(id, data) {
	return apiFetch(`/api/knowledge/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export function deleteKnowledge(id) {
	return apiFetch(`/api/knowledge/${id}`, { method: 'DELETE' });
}

// --- Instance Info ---

export function getInstanceInfo() {
	return apiFetch('/api/instance-info');
}

// --- SSE Chat ---

/**
 * Send a chat message and receive streaming SSE events.
 * @param {string} message
 * @param {string|null} agentId — null for Eve
 * @param {function} onEvent — called with each parsed event {type, ...data}
 * @param {string|null} senderName — display name for shared projects
 * @returns {Promise<void>} resolves when stream ends
 */
export async function chatStream(message, agentId, onEvent, senderName = null) {
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

	const reader = res.body.getReader();
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

let _ws = null;
let _shouldReconnect = true;
let _wsOnEvent = null;

/**
 * Disconnect the WebSocket cleanly (for context switching).
 */
export function disconnectWebSocket() {
	_shouldReconnect = false;
	if (_ws) {
		_ws.close();
		_ws = null;
	}
}

/**
 * Connect to the agent events WebSocket.
 * @param {function} onEvent — called with each parsed event
 * @returns {{ close: function }}
 */
export async function connectWebSocket(onEvent) {
	_shouldReconnect = true;
	_wsOnEvent = onEvent;

	let wsUrl;
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

	ws.onmessage = (event) => {
		try {
			const data = JSON.parse(event.data);
			onEvent(data);
		} catch {
			// skip
		}
	};

	ws.onclose = () => {
		if (_shouldReconnect && _wsOnEvent) {
			// Reconnect after 2s
			setTimeout(() => connectWebSocket(_wsOnEvent), 2000);
		}
	};

	return { close: () => ws.close() };
}
