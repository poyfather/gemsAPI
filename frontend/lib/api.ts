// API client — all calls go through Next.js rewrites to the FastAPI backend.
// In development: Next.js dev server proxies /api/* -> http://localhost:8000/*
// In production:  Set BACKEND_URL in next.config.ts

export interface Gem {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  model: string;
  provider: "anthropic" | "openai" | "local" | "auto";
  tags: string[];
  variables: string[];
  kind?: "prompt" | "agent";
  tools?: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GemCreate {
  name: string;
  description: string;
  system_prompt: string;
  model: string;
  provider: "anthropic" | "openai" | "local" | "auto";
  tags: string[];
  kind?: "prompt" | "agent";
  tools?: string[];
}

export type GemUpdate = Partial<GemCreate>;

export interface ResolveResponse {
  gem_name: string;
  resolved_prompt: string;
  referenced_gems: string[];
  variables_used: string[];
  variables_missing: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  gem_name: string;
  messages: ChatMessage[];
  variables: Record<string, string>;
  model_override?: string;
  provider_override?: string;
  stream?: boolean;
}

export interface ChatResponse {
  content: string;
  model: string;
  provider: string;
  gem_name: string;
  reason?: string;
}

export interface ModelPolicy {
  policy: "local" | "online" | "mix" | "auto" | "manual";
  policies: string[];
  available: { anthropic: boolean; openai: boolean; local: boolean };
  local_base_url: string;
  local_models: string[];
  cloud_default: [string, string] | null;
  local_default: [string, string] | null;
}

export type AvailableModels = Record<string, string[]>;

// ─── Agent runs (ADR-007) ──────────────────────────────────────────────────────

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  risky: boolean;
  source: string;
}

export type RunStatus = "running" | "waiting_approval" | "finished" | "failed" | "max_steps";

export interface RunEvent {
  seq: number;
  type: "run_started" | "model_turn" | "tool_call" | "tool_result" | "approval_requested" | "approval_decided" | "run_finished" | "run_failed" | string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface Run {
  id: string;
  gem_name: string;
  status: RunStatus;
  model: string;
  provider: string;
  input: string;
  output: string | null;
  steps: number;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface RunResult {
  run: Run;
  events: RunEvent[];
}

export interface RunRequest {
  message: string;
  variables?: Record<string, string>;
  model_override?: string;
  provider_override?: string;
  allow_risky?: boolean;
  stream?: boolean;
}

// ─── HTTP helper ───────────────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

// ─── Server-Sent Events ────────────────────────────────────────────────────────

interface SseMessage {
  event: string;
  data: string;
}

/** Open a streaming POST and yield each SSE message until the body ends or `data: [DONE]` arrives. */
async function* sse(path: string, body: unknown): AsyncGenerator<SseMessage> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    let message = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      message = err.detail || err.message || message;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, message);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      sep = buffer.indexOf("\n\n");
      let event = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      const data = dataLines.join("\n");
      if (data === "[DONE]") return;
      if (dataLines.length > 0) yield { event, data };
    }
  }
}

// ─── Gems API ──────────────────────────────────────────────────────────────────

export const gems = {
  list: (): Promise<Gem[]> =>
    request<Gem[]>("/gems/"),

  get: (idOrName: string): Promise<Gem> =>
    request<Gem>(`/gems/${encodeURIComponent(idOrName)}`),

  create: (data: GemCreate): Promise<Gem> =>
    request<Gem>("/gems/", { method: "POST", body: JSON.stringify(data) }),

  update: (id: string, data: GemUpdate): Promise<Gem> =>
    request<Gem>(`/gems/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  delete: (id: string): Promise<{ message: string }> =>
    request(`/gems/${id}`, { method: "DELETE" }),

  resolve: (name: string, variables: Record<string, string> = {}): Promise<ResolveResponse> =>
    request<ResolveResponse>("/gems/resolve", {
      method: "POST",
      body: JSON.stringify({ gem_name: name, variables }),
    }),
};

// ─── Chat API ──────────────────────────────────────────────────────────────────

export const chat = {
  send: (data: ChatRequest): Promise<ChatResponse> =>
    request<ChatResponse>("/chat/", { method: "POST", body: JSON.stringify(data) }),

  models: (): Promise<AvailableModels> =>
    request<AvailableModels>("/chat/models"),

  policy: (): Promise<ModelPolicy> =>
    request<ModelPolicy>("/chat/policy"),

  /** Stream a reply token by token. Resolves when the stream ends; rejects on an HTTP or stream error. */
  stream: async (data: ChatRequest, onChunk: (text: string) => void): Promise<void> => {
    for await (const msg of sse("/chat/", { ...data, stream: true })) {
      const payload = JSON.parse(msg.data) as { content?: string; error?: string };
      if (payload.error) throw new ApiError(502, payload.error);
      if (payload.content) onChunk(payload.content);
    }
  },
};

// ─── Agents API ────────────────────────────────────────────────────────────────

export const agents = {
  tools: (): Promise<ToolInfo[]> =>
    request<ToolInfo[]>("/agents/tools"),

  run: (name: string, data: RunRequest): Promise<RunResult> =>
    request<RunResult>(`/agents/${encodeURIComponent(name)}/runs`, {
      method: "POST",
      body: JSON.stringify({ ...data, stream: false }),
    }),

  /** Run with events delivered as they happen. Resolves when the run ends. */
  stream: async (name: string, data: RunRequest, onEvent: (event: RunEvent) => void): Promise<void> => {
    for await (const msg of sse(`/agents/${encodeURIComponent(name)}/runs`, { ...data, stream: true })) {
      if (msg.event === "error") {
        const payload = JSON.parse(msg.data) as { error?: string };
        throw new ApiError(500, payload.error || "Run failed");
      }
      onEvent(JSON.parse(msg.data) as RunEvent);
    }
  },
};

export const runs = {
  get: (id: string): Promise<RunResult> =>
    request<RunResult>(`/runs/${encodeURIComponent(id)}`),

  /** Approve or deny the risky tool call a run is waiting on, streaming the rest of the run. */
  approve: async (id: string, approve: boolean, onEvent: (event: RunEvent) => void): Promise<void> => {
    for await (const msg of sse(`/runs/${encodeURIComponent(id)}/approve`, { approve, stream: true })) {
      if (msg.event === "error") {
        const payload = JSON.parse(msg.data) as { error?: string };
        throw new ApiError(409, payload.error || "Could not continue the run");
      }
      onEvent(JSON.parse(msg.data) as RunEvent);
    }
  },
};

/** Message for an unknown thrown value, for catch blocks. */
export function errorMessage(e: unknown, fallback = "Something went wrong."): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

export { ApiError };
