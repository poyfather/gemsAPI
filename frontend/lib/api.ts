// API client — all calls go through Next.js rewrites to the FastAPI backend.
// In development: Next.js dev server proxies /api/* -> http://localhost:8000/*
// In production:  Set BACKEND_URL in next.config.ts

export interface Gem {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  model: string;
  provider: "anthropic" | "openai";
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
  provider: "anthropic" | "openai";
  tags: string[];
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
}

export type AvailableModels = Record<string, string[]>;

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
};

/** Message for an unknown thrown value, for catch blocks. */
export function errorMessage(e: unknown, fallback = "Something went wrong."): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

export { ApiError };
