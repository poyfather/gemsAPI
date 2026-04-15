"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { gems as gemsApi, GemCreate, Gem, AvailableModels, chat as chatApi } from "@/lib/api";
import { Info, Plus, X, Loader2, Eye } from "lucide-react";
import clsx from "clsx";

const ANTHROPIC_MODELS = [
  "claude-opus-4-5",
  "claude-sonnet-4-5",
  "claude-haiku-4-5",
  "claude-3-5-sonnet-20241022",
  "claude-3-5-haiku-20241022",
];
const OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"];

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
    model:         initialGem?.model         ?? "claude-opus-4-5",
    provider:      initialGem?.provider      ?? "anthropic",
    tags:          initialGem?.tags          ?? [],
  });
  const [tagInput, setTagInput]   = useState("");
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [preview, setPreview]     = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [varValues, setVarValues] = useState<Record<string, string>>({});

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
    const name = m.slice(7, -2).trim();
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
        await gemsApi.update(initialGem.id, form);
      }
      router.push("/gems");
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Failed to save gem.");
    } finally {
      setSaving(false);
    }
  };

  const modelOptions = form.provider === "anthropic" ? ANTHROPIC_MODELS : OPENAI_MODELS;

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
            placeholder="e.g. code_reviewer"
            value={form.name}
            onChange={(e) => handleChange("name", e.target.value)}
            disabled={mode === "edit"}
            className={clsx(
              "w-full px-3 py-2 rounded-lg bg-gem-card border text-slate-100 font-mono text-sm",
              "placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-violet-500 transition",
              mode === "edit"
                ? "border-gem-border text-slate-500 cursor-not-allowed"
                : "border-gem-border hover:border-slate-600"
            )}
          />
          <p className="mt-1 text-xs text-slate-500">snake_case, unique across library</p>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1.5">Description</label>
          <input
            type="text"
            placeholder="What does this gem do?"
            value={form.description}
            onChange={(e) => handleChange("description", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-violet-500 transition"
          />
        </div>

        {/* Provider + Model */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Provider</label>
            <select
              value={form.provider}
              onChange={(e) => {
                handleChange("provider", e.target.value);
                handleChange("model", e.target.value === "anthropic" ? ANTHROPIC_MODELS[0] : OPENAI_MODELS[0]);
              }}
              className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 transition"
            >
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Model</label>
            <select
              value={form.model}
              onChange={(e) => handleChange("model", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 transition"
            >
              {modelOptions.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

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
              className="flex-1 px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-violet-500 transition"
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
              System Prompt <span className="text-red-400">*</span>
            </label>
            <div className="flex items-center gap-1 text-xs text-slate-500">
              <Info className="w-3 h-3" />
              <span>
                <code className="text-violet-400">{"{{gem:name}}"}</code> to embed, <code className="text-blue-400">{"{variable}"}</code> for vars
              </span>
            </div>
          </div>
          <textarea
            required
            rows={14}
            placeholder={"You are a helpful assistant.\n\n{{gem:base_personality}}\n\nAnswer questions about {topic}."}
            value={form.system_prompt}
            onChange={(e) => handleChange("system_prompt", e.target.value)}
            className="prompt-textarea w-full px-3 py-2.5 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-violet-500 transition"
          />

          {/* Detected variables / gem refs */}
          {(detectedVars.length > 0 || gemRefs.length > 0) && (
            <div className="mt-2 p-3 rounded-lg bg-gem-surface border border-gem-border space-y-2">
              {gemRefs.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center">
                  <span className="text-xs text-slate-500">Embeds:</span>
                  {gemRefs.map((r) => (
                    <span key={r} className="px-2 py-0.5 rounded-md text-xs bg-violet-500/10 text-violet-400 border border-violet-500/20 font-mono">
                      {r}
                    </span>
                  ))}
                </div>
              )}
              {detectedVars.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center">
                  <span className="text-xs text-slate-500">Variables:</span>
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
            {mode === "create" ? "Create Gem" : "Save Changes"}
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
              Resolved Preview
            </span>
            <button
              type="button"
              onClick={handlePreview}
              disabled={loadingPreview}
              className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 text-xs transition-colors"
            >
              {loadingPreview && <Loader2 className="w-3 h-3 animate-spin" />}
              Resolve
            </button>
          </div>

          {/* Variable input area */}
          {detectedVars.length > 0 && (
            <div className="px-4 py-3 border-b border-gem-border space-y-2">
              <p className="text-xs text-slate-500">Fill variables for preview:</p>
              {detectedVars.map((v) => (
                <div key={v} className="flex items-center gap-2">
                  <code className="text-xs text-blue-400 w-24 shrink-0">{"{" + v + "}"}</code>
                  <input
                    type="text"
                    placeholder={`Value for ${v}`}
                    value={varValues[v] ?? ""}
                    onChange={(e) => setVarValues((prev) => ({ ...prev, [v]: e.target.value }))}
                    className="flex-1 px-2 py-1 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
              ))}
            </div>
          )}

          <div className="p-4 min-h-[300px]">
            {preview === null ? (
              <p className="text-slate-600 text-sm italic">
                Click "Resolve" to see the fully expanded prompt including any referenced gems.
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
