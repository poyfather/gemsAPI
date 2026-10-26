"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { gems as gemsApi, chat as chatApi, agents as agentsApi, GemCreate, Gem, AvailableModels, ToolInfo } from "@/lib/api";
import { explain } from "@/lib/words";
import { Info, Plus, X, Loader2, Eye, Bot } from "lucide-react";
import clsx from "clsx";


interface GemFormProps {
  initialGem?: Gem;
  mode: "create" | "edit";
}

export default function GemForm({ initialGem, mode }: GemFormProps) {
  const router = useRouter();
  const [form, setForm]     = useState<GemCreate>({
    name:          initialGem?.name          ?? "",
    description:   initialGem?.description   ?? "",
    system_prompt: initialGem?.system_prompt ?? "",
    model:         initialGem?.model         ?? "auto",
    provider:      initialGem?.provider      ?? "auto",
    tags:          initialGem?.tags          ?? [],
    kind:          initialGem?.kind          ?? "prompt",
    tools:         initialGem?.tools         ?? [],
    memory:        initialGem?.memory        ?? false,
  });
  const [tagInput, setTagInput]   = useState("");
  const [note, setNote]           = useState("");
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [preview, setPreview]     = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [varValues, setVarValues] = useState<Record<string, string>>({});
  // The backend owns the model list (GET /chat/models: live per provider, cached).
  const [models, setModels] = useState<AvailableModels>({});
  // Tools an agent gem may be given (GET /agents/tools).
  const [toolList, setToolList] = useState<ToolInfo[]>([]);

  useEffect(() => {
    let cancelled = false;
    chatApi
      .models()
      .then((list) => {
        if (cancelled) return;
        setModels(list);
        // A new gem starts on the provider's first model once the list is known.
        setForm((prev) => (prev.model || prev.provider === "auto" ? prev : { ...prev, model: list[prev.provider]?.[0] ?? "" }));
      })
      .catch(() => { /* the select still shows the gem's own model */ });
    agentsApi
      .tools()
      .then((list) => { if (!cancelled) setToolList(list); })
      .catch(() => { /* the picker stays empty */ });
    return () => { cancelled = true; };
  }, []);

  const toggleTool = (name: string) => {
    setForm((f) => {
      const tools = f.tools ?? [];
      return { ...f, tools: tools.includes(name) ? tools.filter((t) => t !== name) : [...tools, name] };
    });
  };

  // Detect variables in the prompt
  const detectedVars: string[] = [];
  const gemRefs:      string[] = [];
  const promptText = form.system_prompt;
  const varMatches = promptText.match(/\{([^{}]+)\}/g) || [];
  varMatches.forEach((m) => {
    const name = m.slice(1, -1);
    if (!detectedVars.includes(name)) detectedVars.push(name);
  });
  const gemRefMatches = promptText.match(/\{\{gem:([^}]+)\}\}/g) || [];
  gemRefMatches.forEach((m) => {
    const name = m.slice(6, -2).trim();
    if (!gemRefs.includes(name)) gemRefs.push(name);
  });

  const handleChange = (field: keyof GemCreate, value: string | string[]) => {
    setForm((f) => ({ ...f, [field]: value }));
  };

  const addTag = () => {
    const t = tagInput.trim().toLowerCase();
    if (t && !form.tags.includes(t)) {
      setForm((f) => ({ ...f, tags: [...f.tags, t] }));
    }
    setTagInput("");
  };

  const removeTag = (tag: string) => {
    setForm((f) => ({ ...f, tags: f.tags.filter((t) => t !== tag) }));
  };

  const handlePreview = async () => {
    if (!form.name && mode === "edit") return;
    const name = mode === "edit" && initialGem ? initialGem.name : form.name;
    if (!name) {
      setPreview(form.system_prompt);
      return;
    }
    setLoadingPreview(true);
    try {
      const res = await gemsApi.resolve(name, varValues);
      setPreview(res.resolved_prompt);
    } catch {
      setPreview(form.system_prompt);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (mode === "create") {
        await gemsApi.create(form);
      } else if (initialGem) {
        await gemsApi.update(initialGem.id, { ...form, note: note.trim() || undefined });
      }
      router.push("/gems");
      router.refresh();
    } catch (err) {
      setError(explain(err, "Could not save."));
    } finally {
      setSaving(false);
    }
  };

  const providerModels = models[form.provider] ?? [];
  // Keep the gem's current model selectable even if the provider no longer lists it.
  const modelOptions = form.model && !providerModels.includes(form.model) ? [form.model, ...providerModels] : providerModels;

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-6">

      {/* ── Left: Form fields ── */}
      <div className="space-y-5">

        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1.5">
            Name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            required
            placeholder="for example study_buddy"
            value={form.name}
            onChange={(e) => handleChange("name", e.target.value)}
            disabled={mode === "edit"}
            className={clsx(
              "w-full px-3 py-2 rounded-lg bg-gem-card border text-slate-100 font-mono text-sm",
              "placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition",
              mode === "edit"
                ? "border-gem-border text-slate-500 cursor-not-allowed"
                : "border-gem-border hover:border-slate-600"
            )}
          />
          <p className="mt-1 text-xs text-slate-500">lowercase words joined with underscores; no two prompts share a name</p>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1.5">Description</label>
          <input
            type="text"
            placeholder="What it is for, in one sentence"
            value={form.description}
            onChange={(e) => handleChange("description", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition"
          />
        </div>

        {/* Provider + Model */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Which AI</label>
            <select
              value={form.provider}
              onChange={(e) => {
                const provider = e.target.value as GemCreate["provider"];
                setForm((prev) => ({ ...prev, provider, model: provider === "auto" ? "auto" : (models[provider]?.[0] ?? "") }));
              }}
              className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition"
            >
              <option value="auto">Decide for me (follows the setting in the console)</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (ChatGPT)</option>
              <option value="local">The one on this PC (Ollama, LM Studio, oMLX, vLLM)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Model</label>
            <select
              disabled={form.provider === "auto"}
              value={form.provider === "auto" ? "auto" : form.model}
              onChange={(e) => handleChange("model", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition"
            >
              {form.provider === "auto" && <option value="auto">decided per call</option>}
              {modelOptions.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Kind + tools (ADR-007) */}
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">What it is</label>
            <select
              value={form.kind ?? "prompt"}
              onChange={(e) => handleChange("kind", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition"
            >
              <option value="prompt">A prompt (answers in one go)</option>
              <option value="agent">An assistant (can use tools, step by step)</option>
            </select>
          </div>
          {form.kind === "agent" && (
            <div className="rounded-lg border border-gem-border bg-gem-card p-3 space-y-2">
              <p className="text-xs text-slate-400 flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5 text-violet-400" />
                Tools this assistant may use
              </p>
              {toolList.length === 0 ? (
                <p className="text-xs text-slate-600">No tools to show. Start Lapidary and reload this page.</p>
              ) : (
                Array.from(new Set(toolList.map((t) => t.source))).map((source) => {
                  const group = toolList.filter((t) => t.source === source);
                  const wildcard = `${source}.*`;
                  const allChosen = (form.tools ?? []).includes(wildcard);
                  return (
                    <div key={source} className="space-y-1">
                      {source !== "builtin" && (
                        <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                          <input type="checkbox" checked={allChosen} onChange={() => toggleTool(wildcard)} className="accent-violet-500" />
                          <span>All {group.length} tools from <span className="font-mono text-violet-300">{source}</span> (<span className="font-mono">{wildcard}</span>)</span>
                        </label>
                      )}
                      {source === "builtin" && <p className="text-xs text-slate-500">Built in</p>}
                      <div className={source === "builtin" ? "space-y-1" : "pl-5 space-y-1 max-h-48 overflow-y-auto"}>
                        {group.map((t) => (
                          <label key={t.name} className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={allChosen || (form.tools ?? []).includes(t.name)}
                              disabled={allChosen}
                              onChange={() => toggleTool(t.name)}
                              className="mt-0.5 accent-violet-500"
                            />
                            <span>
                              <span className="font-mono text-violet-300">{t.name}</span>
                              {t.risky && <span className="ml-1.5 px-1.5 py-0.5 rounded bg-red-500/10 text-red-400" title="Can change things, so each call waits for your approval">asks first</span>}
                              <span className="block text-slate-500">{t.description}</span>
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Memory (ADR-010) */}
        <label className="flex items-start gap-2 text-sm text-slate-300 cursor-pointer">
          <input type="checkbox" checked={Boolean(form.memory)} onChange={(e) => setForm((f) => ({ ...f, memory: e.target.checked }))} className="mt-1 accent-violet-500" />
          <span>
            Remembers earlier work
            <span className="block text-xs text-slate-500">Before each message, the best matches from Memory (what assistants did, your notes and decisions) are added to the prompt, so it can build on them.</span>
          </span>
        </label>

        {/* Tags */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1.5">Tags</label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              placeholder="Add a tag..."
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
              className="flex-1 px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition"
            />
            <button
              type="button"
              onClick={addTag}
              className="px-3 py-2 rounded-lg bg-gem-border hover:bg-gem-hover text-slate-300 text-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {form.tags.map((tag) => (
              <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-gem-border text-slate-400">
                {tag}
                <button type="button" onClick={() => removeTag(tag)} className="hover:text-red-400 transition-colors">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* System prompt */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm font-medium text-slate-300">
              The prompt <span className="text-red-400">*</span>
            </label>
            <div className="flex items-center gap-1 text-xs text-slate-500">
              <Info className="w-3 h-3" />
              <span>
                <code className="text-violet-400">{"{{gem:name}}"}</code> pastes another prompt in, <code className="text-blue-400">{"{variable}"}</code> is a blank
              </span>
            </div>
          </div>
          <textarea
            required
            rows={14}
            placeholder={"You are a helpful assistant.\n\n{{gem:base_personality}}\n\nAnswer questions about {topic}."}
            value={form.system_prompt}
            onChange={(e) => handleChange("system_prompt", e.target.value)}
            className="prompt-textarea w-full px-3 py-2.5 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition"
          />

          {/* Detected variables / gem refs */}
          {(detectedVars.length > 0 || gemRefs.length > 0) && (
            <div className="mt-2 p-3 rounded-lg bg-gem-surface border border-gem-border space-y-2">
              {gemRefs.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center">
                  <span className="text-xs text-slate-500">Built from:</span>
                  {gemRefs.map((r) => (
                    <span key={r} className="px-2 py-0.5 rounded-md text-xs bg-violet-500/10 text-violet-400 border border-violet-500/20 font-mono">
                      {r}
                    </span>
                  ))}
                </div>
              )}
              {detectedVars.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center">
                  <span className="text-xs text-slate-500">Blanks:</span>
                  {detectedVars.map((v) => (
                    <span key={v} className="px-2 py-0.5 rounded-md text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono">
                      {"{" + v + "}"}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {mode === "edit" && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">What changed? <span className="font-normal text-slate-500">(optional, kept in the history)</span></label>
            <input
              type="text"
              placeholder="for example: shorter answers, added a step for edge cases"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 transition"
            />
          </div>
        )}

        {/* Error + Submit */}
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {mode === "create" ? "Save prompt" : "Save changes"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 rounded-lg bg-gem-border hover:bg-gem-hover text-slate-300 text-sm transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* ── Right: Preview panel ── */}
      <div className="space-y-4">
        <div className="bg-gem-card border border-gem-border rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gem-border">
            <span className="text-sm font-medium text-slate-300 flex items-center gap-2">
              <Eye className="w-4 h-4 text-violet-400" />
              Preview as sent
            </span>
            <button
              type="button"
              onClick={handlePreview}
              disabled={loadingPreview}
              className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 text-xs transition-colors"
            >
              {loadingPreview && <Loader2 className="w-3 h-3 animate-spin" />}
              Build it
            </button>
          </div>

          {/* Variable input area */}
          {detectedVars.length > 0 && (
            <div className="px-4 py-3 border-b border-gem-border space-y-2">
              <p className="text-xs text-slate-500">Fill the blanks for the preview:</p>
              {detectedVars.map((v) => (
                <div key={v} className="flex items-center gap-2">
                  <code className="text-xs text-blue-400 w-24 shrink-0">{"{" + v + "}"}</code>
                  <input
                    type="text"
                    placeholder={`Value for ${v}`}
                    value={varValues[v] ?? ""}
                    onChange={(e) => setVarValues((prev) => ({ ...prev, [v]: e.target.value }))}
                    className="flex-1 px-2 py-1 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs focus:outline-hidden focus:ring-1 focus:ring-violet-500"
                  />
                </div>
              ))}
            </div>
          )}

          <div className="p-4 min-h-[300px]">
            {preview === null ? (
              <p className="text-slate-600 text-sm italic">
                Press &quot;Build it&quot; to see the prompt as the AI will receive it, with other prompts pasted in.
              </p>
            ) : (
              <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300 leading-relaxed">
                {preview}
              </pre>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}
