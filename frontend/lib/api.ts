// API client — all calls go through Next.js rewrites to the FastAPI backend.
// In development: Next.js dev server proxies /api/* -> http://localhost:8000/*
// In production:  Set BACKEND_URL in next.config.ts

export type VariableType = "text" | "long_text" | "number" | "choice" | "boolean";

/** What a {blank} expects (roadmap 29). */
export interface VariableSpec {
  description: string;
  type: VariableType;
  options: string[];
  default?: string | null;
  required: boolean;
}

/** A worked example (roadmap 31): rendered into the prompt as literal text; the note is for people. */
export interface Example { input: string; output: string; note?: string }

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
  memory?: boolean;
  variable_specs?: Record<string, VariableSpec>;
  examples?: Example[];
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
  memory?: boolean;
  variable_specs?: Record<string, VariableSpec>;
  examples?: Example[];
}

export type GemUpdate = Partial<GemCreate> & { note?: string };

// ─── Version history (roadmap 14) ──────────────────────────────────────────────

export interface GemVersionSummary {
  version: number;
  note: string;
  source: "api" | "mcp" | "revert" | "baseline" | string;
  created_at: string;
  changed: string[];
  current: boolean;
}

// ─── Evals per gem (roadmap 28) ────────────────────────────────────────────────

export type EvalCheck = "contains" | "not_contains" | "all_of" | "equals" | "json" | "judge";

export interface EvalCase {
  id: string;
  gem_id: string;
  name: string;
  input: string;
  variables: Record<string, string>;
  check: EvalCheck;
  expected: string;
  created_at: string;
}

export interface EvalCaseResult { case_id: string; name: string; passed: boolean; output: string; detail: string }

export interface EvalEstimate {
  cases: number;
  calls: number;
  provider: string;
  model: string;
  free: boolean;
  input_tokens: number;
  max_output_tokens: number;
  max_calls: number;
}

export interface EvalRun {
  id: string;
  gem_id: string;
  gem_version: number;
  provider: string;
  model: string;
  passed: number;
  total: number;
  results: EvalCaseResult[];
  baseline: boolean;
  created_at: string;
}

export interface EvalRunReport { run: EvalRun; baseline?: EvalRun | null; regressions: string[]; fixed: string[] }

// ─── Side-by-side runs (roadmap 30) ────────────────────────────────────────────

export interface CompareVariant { label?: string; version?: number | null; provider_override?: string; model_override?: string }
export interface CompareRequest { message?: string; variables?: Record<string, string>; variants: CompareVariant[] }
export interface CompareColumn {
  label: string; version: number; provider: string; model: string; reason: string;
  output: string; error: string; seconds: number; run_id?: string | null;
}
export interface CompareResult { gem_name: string; message: string; columns: CompareColumn[] }
export interface CompareEstimate {
  calls: number; tests: number; free: boolean; max_calls: number;
  columns: { label: string; version: number; provider: string; model: string; free: boolean }[];
}
export interface CompareTestsResult {
  gem_name: string; columns: CompareColumn[]; totals: number[];
  cases: { name: string; results: { passed: boolean; detail: string }[] }[];
}

export interface GemDiff {
  gem_name: string;
  from_version: number;
  to_version: number;
  changed: string[];
  fields: Record<string, { from: unknown; to: unknown }>;
  prompt_diff: string;
}

// ─── Memory (ADR-010) ──────────────────────────────────────────────────────────

export type MemoryKind = "observation" | "summary" | "decision" | "preference" | "lesson" | "handoff" | "note";
export const MEMORY_KINDS: MemoryKind[] = ["observation", "summary", "decision", "preference", "lesson", "handoff", "note"];

export interface Memory {
  id: string;
  kind: MemoryKind | string;
  text: string;
  source: string;
  gem_name?: string | null;
  run_id?: string | null;
  tags: string[];
  scope: string;
  created_at: string;
}

export interface MemoryCreate {
  text: string;
  kind?: MemoryKind;
  tags?: string[];
  scope?: string;
}

export interface ResolveResponse {
  gem_name: string;
  resolved_prompt: string;
  referenced_gems: string[];
  variables_used: string[];
  variables_missing: string[];
  variables_defaulted?: string[];
  variable_errors?: string[];
  examples_used?: number;
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

  versions: (idOrName: string): Promise<GemVersionSummary[]> =>
    request<GemVersionSummary[]>(`/gems/${encodeURIComponent(idOrName)}/versions`),

  diff: (idOrName: string, fromVersion?: number, toVersion?: number): Promise<GemDiff> => {
    const params = new URLSearchParams();
    if (fromVersion) params.set("from_version", String(fromVersion));
    if (toVersion) params.set("to_version", String(toVersion));
    return request<GemDiff>(`/gems/${encodeURIComponent(idOrName)}/diff?${params.toString()}`);
  },

  revert: (idOrName: string, version: number, note = ""): Promise<Gem> =>
    request<Gem>(`/gems/${encodeURIComponent(idOrName)}/versions/${version}/revert`, { method: "POST", body: JSON.stringify({ note }) }),

  evals: {
    list: (idOrName: string): Promise<EvalCase[]> => request<EvalCase[]>(`/gems/${encodeURIComponent(idOrName)}/evals`),
    add: (idOrName: string, data: Omit<EvalCase, "id" | "gem_id" | "created_at">): Promise<EvalCase> =>
      request<EvalCase>(`/gems/${encodeURIComponent(idOrName)}/evals`, { method: "POST", body: JSON.stringify(data) }),
    remove: async (idOrName: string, caseId: string): Promise<void> => {
      const res = await fetch(`/api/gems/${encodeURIComponent(idOrName)}/evals/${encodeURIComponent(caseId)}`, { method: "DELETE" });
      if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
    },
    estimate: (idOrName: string): Promise<EvalEstimate> => request<EvalEstimate>(`/gems/${encodeURIComponent(idOrName)}/evals/estimate`),
    run: (idOrName: string): Promise<EvalRunReport> =>
      request<EvalRunReport>(`/gems/${encodeURIComponent(idOrName)}/evals/run`, { method: "POST", body: JSON.stringify({}) }),
    runs: (idOrName: string): Promise<EvalRun[]> => request<EvalRun[]>(`/gems/${encodeURIComponent(idOrName)}/evals/runs`),
    setBaseline: (idOrName: string, runId: string): Promise<EvalRun> =>
      request<EvalRun>(`/gems/${encodeURIComponent(idOrName)}/evals/runs/${encodeURIComponent(runId)}/baseline`, { method: "POST" }),
  },

  exampleToTest: (idOrName: string, index: number): Promise<EvalCase> =>
    request<EvalCase>(`/gems/${encodeURIComponent(idOrName)}/examples/${index}/test`, { method: "POST" }),

  compare: {
    estimate: (idOrName: string, data: CompareRequest, tests = false): Promise<CompareEstimate> =>
      request<CompareEstimate>(`/gems/${encodeURIComponent(idOrName)}/compare/estimate${tests ? "?tests=true" : ""}`, { method: "POST", body: JSON.stringify(data) }),
    run: (idOrName: string, data: CompareRequest): Promise<CompareResult> =>
      request<CompareResult>(`/gems/${encodeURIComponent(idOrName)}/compare`, { method: "POST", body: JSON.stringify(data) }),
    tests: (idOrName: string, data: CompareRequest): Promise<CompareTestsResult> =>
      request<CompareTestsResult>(`/gems/${encodeURIComponent(idOrName)}/compare/tests`, { method: "POST", body: JSON.stringify(data) }),
  },

  resolve: (name: string, variables: Record<string, string> = {}): Promise<ResolveResponse> =>
    request<ResolveResponse>("/gems/resolve", {
      method: "POST",
      body: JSON.stringify({ gem_name: name, variables }),
    }),
};

// ─── Pipelines and gates (ADR-011) ─────────────────────────────────────────────

export interface PipelineGate {
  gem: string;
  role: "test" | "visual" | "review" | "custom" | string;
  provider_override?: string | null;
  model_override?: string | null;
  instructions?: string;
}

export interface Pipeline {
  id: string;
  name: string;
  description: string;
  builder: string;
  gates: PipelineGate[];
  max_attempts: number;
  acceptance: boolean;
  created_at: string;
  updated_at: string;
}

export interface GateResult {
  gem: string;
  role: string;
  run_id?: string | null;
  verdict: "pass" | "fail" | "waiting" | string;
  findings: string;
}

export interface Attempt {
  number: number;
  builder_run_id?: string | null;
  builder_status: string;
  output?: string | null;
  gates: GateResult[];
  feedback: string;
}

export type PipelineStatus = "running" | "waiting_approval" | "waiting_acceptance" | "passed" | "failed" | "max_attempts";

export interface PipelineRun {
  id: string;
  pipeline_name: string;
  status: PipelineStatus | string;
  input: string;
  output?: string | null;
  attempts: Attempt[];
  waiting_run_id?: string | null;
  error?: string | null;
  created_at: string;
  finished_at?: string | null;
}

export interface PipelineResult {
  run: PipelineRun;
  events: RunEvent[];
}

export const pipelines = {
  list: (): Promise<Pipeline[]> => request<Pipeline[]>("/pipelines/"),
  get: (name: string): Promise<Pipeline> => request<Pipeline>(`/pipelines/${encodeURIComponent(name)}`),
  getRun: (id: string): Promise<PipelineRun> => request<PipelineRun>(`/pipelines/runs/${encodeURIComponent(id)}`),

  /** Run a pipeline with its events delivered as they happen. Resolves when it finishes or pauses. */
  stream: async (name: string, data: { message: string; variables?: Record<string, string>; allow_risky?: boolean; memory_scope?: string }, onEvent: (event: RunEvent) => void): Promise<void> => {
    for await (const msg of sse(`/pipelines/${encodeURIComponent(name)}/runs`, { ...data, stream: true })) {
      if (msg.event === "error") {
        const payload = JSON.parse(msg.data) as { error?: string };
        throw new ApiError(500, payload.error || "Pipeline failed");
      }
      onEvent(JSON.parse(msg.data) as RunEvent);
    }
  },

  /** Continue a paused pipeline run: accept or reject at acceptance, or carry on after an approval. */
  resume: async (id: string, data: { accept?: boolean; note?: string }, onEvent: (event: RunEvent) => void): Promise<void> => {
    for await (const msg of sse(`/pipelines/runs/${encodeURIComponent(id)}/resume`, { ...data, stream: true })) {
      if (msg.event === "error") {
        const payload = JSON.parse(msg.data) as { error?: string };
        throw new ApiError(409, payload.error || "Could not continue the pipeline");
      }
      onEvent(JSON.parse(msg.data) as RunEvent);
    }
  },
};

// ─── Memory API ────────────────────────────────────────────────────────────────

export const memory = {
  list: (q = "", scope = "default", kinds: string[] = [], limit = 100): Promise<Memory[]> => {
    const params = new URLSearchParams({ q, scope, limit: String(limit) });
    for (const k of kinds) params.append("kind", k);
    return request<Memory[]>(`/memory/?${params.toString()}`);
  },
  remember: (data: MemoryCreate): Promise<Memory> =>
    request<Memory>("/memory/", { method: "POST", body: JSON.stringify(data) }),
  forget: async (id: string): Promise<void> => {
    const res = await fetch(`/api/memory/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
  },
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
