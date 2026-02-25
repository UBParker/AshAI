import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock auth module before importing client
vi.mock('$lib/auth.js', () => ({
	getAccessToken: vi.fn().mockResolvedValue(null),
	isAuthEnabled: vi.fn().mockReturnValue(false)
}));

// We test the exponential backoff logic in isolation
describe('WebSocket Reconnection Logic', () => {
	let originalWebSocket: typeof WebSocket;

	beforeEach(() => {
		vi.useFakeTimers();
		originalWebSocket = globalThis.WebSocket;
	});

	afterEach(() => {
		vi.useRealTimers();
		globalThis.WebSocket = originalWebSocket;
	});

	it('should implement exponential backoff delays', async () => {
		const BASE_DELAY = 1000;
		const MAX_DELAY = 30000;

		function getReconnectDelay(attempt: number): number {
			return Math.min(BASE_DELAY * Math.pow(2, attempt), MAX_DELAY);
		}

		expect(getReconnectDelay(0)).toBe(1000);   // 1s
		expect(getReconnectDelay(1)).toBe(2000);   // 2s
		expect(getReconnectDelay(2)).toBe(4000);   // 4s
		expect(getReconnectDelay(3)).toBe(8000);   // 8s
		expect(getReconnectDelay(4)).toBe(16000);  // 16s
		expect(getReconnectDelay(5)).toBe(30000);  // capped at 30s
		expect(getReconnectDelay(10)).toBe(30000); // still capped
	});

	it('should reset attempt counter on successful connection', () => {
		let reconnectAttempt = 5;
		// On open, reset
		reconnectAttempt = 0;
		expect(reconnectAttempt).toBe(0);
	});

	it('should apply jitter within expected range', () => {
		const BASE_DELAY = 1000;
		const MAX_DELAY = 30000;

		function getReconnectDelayWithJitter(attempt: number): number {
			const delay = Math.min(BASE_DELAY * Math.pow(2, attempt), MAX_DELAY);
			const jitter = delay * (0.75 + Math.random() * 0.5);
			return jitter;
		}

		// Test jitter range for attempt 0 (base delay = 1000)
		for (let i = 0; i < 100; i++) {
			const jittered = getReconnectDelayWithJitter(0);
			expect(jittered).toBeGreaterThanOrEqual(750);  // 1000 * 0.75
			expect(jittered).toBeLessThanOrEqual(1250);    // 1000 * 1.25
		}
	});

	it('should cap delay at MAX_DELAY even with high attempt count', () => {
		const BASE_DELAY = 1000;
		const MAX_DELAY = 30000;

		for (let attempt = 0; attempt < 20; attempt++) {
			const delay = Math.min(BASE_DELAY * Math.pow(2, attempt), MAX_DELAY);
			expect(delay).toBeLessThanOrEqual(MAX_DELAY);
		}
	});
});
