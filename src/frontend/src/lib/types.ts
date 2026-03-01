/**
 * Shared TypeScript types for AshAI frontend.
 */

// --- Agents ---

export interface Agent {
	id: string;
	name: string;
	status: 'idle' | 'thinking' | 'tool_calling' | 'waiting_approval' | 'error' | 'destroyed';
	role?: string;
	model?: string;
	persona?: string;
	tools?: string[];
	created_at?: string;
}

export interface AgentCreateData {
	name: string;
	role?: string;
	model?: string;
	persona?: string;
	tools?: string[];
	initial_message?: string;
}

export interface AgentUpdateData {
	name?: string;
	role?: string;
	persona?: string;
}

// --- Chat ---

export interface ToolCall {
	id: string;
	name: string;
	arguments: string;
	status: 'running' | 'done' | 'error';
	result: string | null;
}

export interface Message {
	role: 'user' | 'assistant' | 'system';
	content: string;
	sender_name?: string | null;
	streaming?: boolean;
	tool_calls?: ToolCall[];
}

// --- Events ---

export interface AgentEvent {
	type: string;
	agent_id: string;
	data: Record<string, unknown>;
}

export interface ApprovalEvent {
	type: 'approval.requested' | 'approval.resolved';
	agent_id: string;
	data: {
		approval_id: string;
		tool_name?: string;
		arguments?: string;
		created_at?: string;
	};
}

export interface ChatStreamEvent {
	type: 'content' | 'tool_call' | 'tool_result' | 'done' | 'error';
	text?: string;
	tool_name?: string;
	arguments?: string;
	call_id?: string;
	result?: string;
	error?: string;
}

export type WebSocketEvent = AgentEvent | ApprovalEvent | ChatStreamEvent;

// --- Approvals ---

export interface PendingApproval {
	id: string;
	agent_id: string;
	tool_name: string;
	arguments: string;
	created_at: string;
}

// --- Settings ---

export interface Settings {
	default_model?: string;
	default_provider?: string;
	approval_mode?: 'always' | 'never' | 'dangerous';
	[key: string]: unknown;
}

// --- Knowledge ---

export interface KnowledgeItem {
	id: string;
	title: string;
	content: string;
	type?: string;
	created_at?: string;
	updated_at?: string;
}

// --- Projects ---

export interface Project {
	id: string;
	name: string;
	description?: string;
	owner_id: string;
	my_role?: string;
	created_at?: string;
}

// --- Agent Templates ---

export interface AgentTemplate {
	id: string;
	display_name: string;
	description: string;
	role: string;
	goal: string;
	provider_name: string;
	model_name: string;
	temperature: number;
	tool_names: string[];
}

// --- Providers ---

export interface Provider {
	name: string;
	models: string[];
}
