"use client";

import { useEffect, useState } from "react";
import { gems as gemsApi, Gem, GemDiff, GemVersionSummary } from "@/lib/api";
import { explain } from "@/lib/words";
import { History, Loader2, RotateCcw } from "lucide-react";
import clsx from "clsx";

const FIELD_WORDS: Record<string, string> = {
  system_prompt: "the prompt",
  description: "description",
  model: "model",
  provider: "which AI",
  tags: "tags",
  kind: "what it is",
  tools: "tools",
  memory: "remembers earlier work",
  name: "name",
};

const SOURCE_WORDS: Record<string, string> = {
  api: "saved here",
  mcp: "saved from an AI app",
  revert: "restored",
  baseline: "before history was kept",
};

function show(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "(none)";
  if (value === null || value === undefined || value === "") return "(empty)";
  return String(value);
}

/** The gem's history: every saved version, what changed, a diff, and Restore (roadmap 14). */
export default function GemHistory({ gem, onRestored }: { gem: Gem; onRestored: (g: Gem) => void }) {
  const [versions, setVersions] = useState<GemVersionSummary[] | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  // Versions never change once saved, so each diff is fetched once and kept by version number.
  const [diffs, setDiffs] = useState<Record<number, GemDiff>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    gemsApi.versions(gem.id)
      .then((list) => { if (!cancelled) { setVersions(list); setPicked((p) => p ?? list[0]?.version ?? null); } })
      .catch((e) => { if (!cancelled) setError(explain(e, "Could not load the history.")); });
    return () => { cancelled = true; };
  }, [gem.id, gem.updated_at, reload]);

  useEffect(() => {
    if (!picked || picked <= 1 || diffs[picked]) return;
    let cancelled = false;
    gemsApi.diff(gem.id, picked - 1, picked)
      .then((d) => { if (!cancelled) setDiffs((prev) => ({ ...prev, [picked]: d })); })
      .catch((e) => { if (!cancelled) setError(explain(e, "Could not compare the versions.")); });
    return () => { cancelled = true; };
  }, [gem.id, picked, diffs]);

  const diff = picked ? diffs[picked] ?? null : null;

  const restore = async (version: number) => {
    const note = prompt(`Restore version ${version}? It is saved as a new version, so nothing is lost.\n\nWhy (optional):`, "");
    if (note === null) return;
    setBusy(true);
    try {
      const g = await gemsApi.revert(gem.id, version, note);
      onRestored(g);
      setPicked(null);
      setReload((n) => n + 1);
    } catch (e) {
      alert(explain(e, "Could not restore it."));
    } finally {
      setBusy(false);
    }
  };

  const current = versions?.find((v) => v.current)?.version;

  return (
    <div className="bg-gem-card border border-gem-border rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gem-border">
        <span className="text-sm font-medium text-slate-300 flex items-center gap-2">
          <History className="w-4 h-4 text-violet-400" /> History
          <span className="font-normal text-slate-500">(every save is kept; pick one to see what changed)</span>
        </span>
      </div>
      {error && <p className="px-4 py-3 text-xs text-red-400">{error}</p>}
      {!versions && !error && <div className="px-4 py-6 text-slate-500 text-sm flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {versions && (
        <div className="grid grid-cols-1 md:grid-cols-5">
          <ul className="md:col-span-2 border-b md:border-b-0 md:border-r border-gem-border max-h-96 overflow-y-auto">
            {versions.map((v) => (
              <li key={v.version}>
                <button
                  onClick={() => setPicked(v.version)}
                  className={clsx("w-full text-left px-4 py-2.5 border-b border-gem-border/60 transition-colors", picked === v.version ? "bg-violet-600/10" : "hover:bg-gem-hover")}
                >
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-violet-300">v{v.version}</span>
                    {v.current && <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">current</span>}
                    <span className="text-slate-500 ml-auto">{new Date(v.created_at).toLocaleString()}</span>
                  </div>
                  <div className="text-xs text-slate-300 mt-1">{v.note || <span className="text-slate-600">no note</span>}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {SOURCE_WORDS[v.source] ?? v.source}
                    {v.changed.length > 0 && <> · changed {v.changed.map((f) => FIELD_WORDS[f] ?? f).join(", ")}</>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
          <div className="md:col-span-3 p-4 space-y-3 min-h-[200px]">
            {picked === null ? null : picked <= 1 ? (
              <p className="text-sm text-slate-500">Version 1 is where the history starts, so there is nothing before it to compare.</p>
            ) : !diff ? (
              <div className="text-slate-500 text-sm flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Comparing...</div>
            ) : (
              <>
                <p className="text-xs text-slate-400">What changed from v{diff.from_version} to v{diff.to_version}{diff.changed.length === 0 ? ": nothing" : ""}</p>
                {Object.entries(diff.fields).map(([field, ft]) => (
                  <div key={field} className="text-xs">
                    <span className="text-slate-500">{FIELD_WORDS[field] ?? field}: </span>
                    <span className="text-red-400 line-through">{show(ft.from)}</span>{" "}
                    <span className="text-emerald-400">{show(ft.to)}</span>
                  </div>
                ))}
                {diff.prompt_diff && (
                  <pre className="text-xs font-mono leading-relaxed bg-gem-surface border border-gem-border rounded-lg p-3 overflow-x-auto max-h-80">
                    {diff.prompt_diff.split("\n").map((line, i) => (
                      <div key={i} className={clsx(
                        line.startsWith("+") && !line.startsWith("+++") ? "text-emerald-400 bg-emerald-500/5" :
                        line.startsWith("-") && !line.startsWith("---") ? "text-red-400 bg-red-500/5" :
                        line.startsWith("@@") ? "text-violet-300" : "text-slate-500"
                      )}>{line || " "}</div>
                    ))}
                  </pre>
                )}
              </>
            )}
            {picked !== null && picked !== current && (
              <button disabled={busy} onClick={() => restore(picked)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs disabled:opacity-50">
                {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />} Restore version {picked}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
