"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { gems as gemsApi, Gem, ResolveResponse, errorMessage } from "@/lib/api";
import {
  ArrowLeft, Edit, Trash2, MessageSquare, Loader2,
  AlertTriangle, Variable, LinkIcon, Cpu, ChevronDown, ChevronUp, Bot
} from "lucide-react";
import clsx from "clsx";

export default function GemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [gem, setGem]               = useState<Gem | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [deleting, setDeleting]     = useState(false);
  const [resolve, setResolve]       = useState<ResolveResponse | null>(null);
  const [loadingResolve, setLoadingResolve] = useState(false);
  const [varValues, setVarValues]   = useState<Record<string, string>>({});
  const [showRaw, setShowRaw]       = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await gemsApi.get(id);
        setGem(data);
      } catch (e) {
        setError(errorMessage(e, "Failed to load the gem."));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleDelete = async () => {
    if (!confirm(`Delete gem "${gem?.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await gemsApi.delete(id);
      router.push("/gems");
    } catch (e) {
      alert(errorMessage(e, "Failed to delete the gem."));
      setDeleting(false);
    }
  };

  const handleResolve = async () => {
    if (!gem) return;
    setLoadingResolve(true);
    try {
      const res = await gemsApi.resolve(gem.name, varValues);
      setResolve(res);
    } catch (e) {
      alert(errorMessage(e, "Failed to resolve the gem."));
    } finally {
      setLoadingResolve(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...
      </div>
    );
  }

  if (error || !gem) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p>{error || "Gem not found."}</p>
        <Link href="/gems" className="ml-auto text-sm underline">Back to library</Link>
      </div>
    );
  }

  const gemRefs = Array.from(
    new Set((gem.system_prompt.match(/\{\{gem:([^}]+)\}\}/g) || []).map((m) => m.slice(7, -2).trim()))
  );

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3">
        <Link
          href="/gems"
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-gem-hover transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white font-mono">{gem.name}</h1>
          {gem.description && <p className="text-slate-400 text-sm mt-0.5">{gem.description}</p>}
        </div>
        <div className="flex gap-2">
          <Link
            href={`/chat?gem=${gem.name}`}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 text-sm transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            {gem.kind === "agent" ? "Run in Chat" : "Test in Chat"}
          </Link>
          <Link
            href={`/gems/${gem.id}/edit`}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gem-border hover:bg-gem-hover text-slate-300 text-sm transition-colors"
          >
            <Edit className="w-4 h-4" />
            Edit
          </Link>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-sm transition-colors"
          >
            {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            Delete
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Meta sidebar */}
        <div className="space-y-4 lg:col-span-1">
          {gem.kind === "agent" && (
            <div className="bg-gem-card border border-violet-500/30 rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-violet-400" />
                <span className="text-xs text-violet-300">Agent gem</span>
              </div>
              <p className="text-xs text-slate-500">May call these tools in a loop:</p>
              <div className="flex flex-wrap gap-1.5">
                {(gem.tools ?? []).length === 0
                  ? <span className="text-xs text-slate-600">no tools</span>
                  : (gem.tools ?? []).map((t) => (
                    <span key={t} className="px-2 py-0.5 rounded-md text-xs bg-violet-500/10 text-violet-300 border border-violet-500/20 font-mono">{t}</span>
                  ))}
              </div>
            </div>
          )}
          <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-slate-500" />
              <span className="text-xs text-slate-500">Provider / Model</span>
            </div>
            <div className="text-sm text-slate-300">
              <span className={clsx(
                "px-2 py-0.5 rounded-md text-xs mr-2",
                gem.provider === "anthropic"
                  ? "bg-orange-500/10 text-orange-400"
                  : "bg-emerald-500/10 text-emerald-400"
              )}>
                {gem.provider}
              </span>
              <code className="text-slate-400 text-xs">{gem.model}</code>
            </div>
          </div>

          {gem.tags.length > 0 && (
            <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2">
              <p className="text-xs text-slate-500">Tags</p>
              <div className="flex flex-wrap gap-1.5">
                {gem.tags.map((t) => (
                  <span key={t} className="px-2 py-0.5 rounded-md text-xs bg-gem-border text-slate-400">{t}</span>
                ))}
              </div>
            </div>
          )}

          {gem.variables.length > 0 && (
            <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2">
              <p className="text-xs text-slate-500 flex items-center gap-1">
                <Variable className="w-3 h-3" /> Variables
              </p>
              <div className="space-y-1">
                {gem.variables.map((v) => (
                  <code key={v} className="block text-xs text-blue-400 font-mono">{"{" + v + "}"}</code>
                ))}
              </div>
            </div>
          )}

          {gemRefs.length > 0 && (
            <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2">
              <p className="text-xs text-slate-500 flex items-center gap-1">
                <LinkIcon className="w-3 h-3" /> Embeds
              </p>
              <div className="space-y-1">
                {gemRefs.map((r) => (
                  <Link
                    key={r}
                    href={`/gems/${r}`}
                    className="block text-xs text-violet-400 font-mono hover:text-violet-300 transition-colors"
                  >
                    {r}
                  </Link>
                ))}
              </div>
            </div>
          )}

          <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2 text-xs text-slate-500">
            <div className="flex justify-between">
              <span>Created</span>
              <span>{new Date(gem.created_at).toLocaleDateString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Updated</span>
              <span>{new Date(gem.updated_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="lg:col-span-2 space-y-4">

          {/* Raw prompt toggle */}
          <div className="bg-gem-card border border-gem-border rounded-xl overflow-hidden">
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-gem-hover transition-colors"
            >
              <span className="text-sm font-medium text-slate-300">Raw System Prompt</span>
              {showRaw ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
            </button>
            {showRaw && (
              <div className="border-t border-gem-border p-4">
                <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300 leading-relaxed">
                  {gem.system_prompt}
                </pre>
              </div>
            )}
          </div>

          {/* Resolve panel */}
          <div className="bg-gem-card border border-gem-border rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gem-border">
              <span className="text-sm font-medium text-slate-300">Resolved Prompt</span>
              <button
                onClick={handleResolve}
                disabled={loadingResolve}
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 text-xs transition-colors"
              >
                {loadingResolve && <Loader2 className="w-3 h-3 animate-spin" />}
                Resolve
              </button>
            </div>

            {gem.variables.length > 0 && (
              <div className="px-4 py-3 border-b border-gem-border space-y-2">
                <p className="text-xs text-slate-500">Variable values (optional):</p>
                {gem.variables.map((v) => (
                  <div key={v} className="flex items-center gap-2">
                    <code className="text-xs text-blue-400 w-28 shrink-0">{"{" + v + "}"}</code>
                    <input
                      type="text"
                      placeholder={`Value for ${v}`}
                      value={varValues[v] ?? ""}
                      onChange={(e) => setVarValues((p) => ({ ...p, [v]: e.target.value }))}
                      className="flex-1 px-2 py-1 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs focus:outline-hidden focus:ring-1 focus:ring-violet-500"
                    />
                  </div>
                ))}
              </div>
            )}

            <div className="p-4 min-h-[200px]">
              {!resolve ? (
                <p className="text-slate-600 text-sm italic">
                  Click &quot;Resolve&quot; to expand recursive gem references and preview the final prompt.
                </p>
              ) : (
                <>
                  {resolve.variables_missing.length > 0 && (
                    <div className="mb-3 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-400">
                      Missing variables: {resolve.variables_missing.map((v) => "{" + v + "}").join(", ")}
                    </div>
                  )}
                  {resolve.referenced_gems.length > 0 && (
                    <div className="mb-3 flex flex-wrap gap-1.5 items-center">
                      <span className="text-xs text-slate-500">Expanded:</span>
                      {resolve.referenced_gems.map((r) => (
                        <span key={r} className="text-xs px-1.5 py-0.5 rounded-sm bg-violet-500/10 text-violet-400 font-mono">{r}</span>
                      ))}
                    </div>
                  )}
                  <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300 leading-relaxed">
                    {resolve.resolved_prompt}
                  </pre>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
