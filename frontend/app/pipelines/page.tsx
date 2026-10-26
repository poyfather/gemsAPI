"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { pipelines as pipelinesApi, Pipeline, RunEvent } from "@/lib/api";
import { explain } from "@/lib/words";
import { GitBranch, Loader2, AlertTriangle, Play, ShieldCheck, Hammer } from "lucide-react";

export default function PipelinesPage() {
  const router = useRouter();
  const [items, setItems]     = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [picked, setPicked]   = useState<string>("");
  const [message, setMessage] = useState("");
  const [allowRisky, setAllowRisky] = useState(false);
  const [running, setRunning] = useState(false);
  const [log, setLog]         = useState<string[]>([]);
  const [runId, setRunId]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    pipelinesApi.list()
      .then((list) => { if (!cancelled) { setItems(list); if (list.length && !picked) setPicked(list[0].name); } })
      .catch((e) => { if (!cancelled) setError(explain(e, "Could not load the pipelines.")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const describe = (e: RunEvent): string => {
    const d = e.data as Record<string, unknown>;
    switch (e.type) {
      case "pipeline_started": return `Started: ${String(d.builder)} builds, then ${(d.gates as { gem: string }[]).map((g) => g.gem).join(", ") || "no gates"}; up to ${String(d.max_attempts)} attempts.`;
      case "attempt_started": return `Attempt ${String(d.attempt)}${d.feedback ? " with the findings from last time" : ""}.`;
      case "builder_finished": return `The builder ${String(d.status)} (attempt ${String(d.attempt)}).`;
      case "gate_started": return `${String(d.role)} gate: ${String(d.gem)} is checking...`;
      case "gate_finished": return `${String(d.role)} gate ${String(d.gem)}: ${String(d.verdict).toUpperCase()}${d.verdict === "fail" ? `. ${String(d.findings).slice(0, 200)}` : ""}`;
      case "pipeline_paused": return d.status === "waiting_acceptance" ? "Every gate passed. Waiting for you to accept." : "Paused: an agent run is waiting for your approval.";
      case "pipeline_finished": return `Finished: ${String(d.status)} after ${String(d.attempts ?? "")} attempt(s).`;
      default: return e.type;
    }
  };

  const start = async () => {
    if (!picked || !message.trim() || running) return;
    setRunning(true); setLog([]); setRunId(null);
    try {
      await pipelinesApi.stream(picked, { message: message.trim(), allow_risky: allowRisky }, (e) => {
        if (e.type === "pipeline_started") setRunId(String((e.data as { pipeline_run_id?: string }).pipeline_run_id ?? ""));
        setLog((prev) => [...prev, describe(e)]);
      });
    } catch (err) {
      setLog((prev) => [...prev, explain(err)]);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2"><GitBranch className="w-6 h-6 text-violet-400" /> Pipelines</h1>
        <p className="text-slate-400 mt-1 text-sm max-w-3xl">
          A builder assistant does the work, then gates check it: tests, a review that tries to break it, and finally you. A failed gate sends its findings back to the builder for another attempt, and becomes a lesson in Memory. Nothing is called done because the model said so.
        </p>
      </div>

      {loading && <div className="flex items-center justify-center py-16 text-slate-500"><Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...</div>}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
          <AlertTriangle className="w-5 h-5 shrink-0" /><p className="text-sm">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-3">
            {items.length === 0 && <p className="text-slate-500 text-sm">No pipelines yet. Create one with POST /pipelines/ or run the seed.</p>}
            {items.map((p) => (
              <button key={p.id} onClick={() => setPicked(p.name)} className={`w-full text-left bg-gem-card border rounded-xl p-4 transition-colors ${picked === p.name ? "border-violet-500/60" : "border-gem-border hover:border-violet-500/30"}`}>
                <div className="font-mono text-sm text-violet-300">{p.name}</div>
                {p.description && <p className="text-slate-400 text-sm mt-1">{p.description}</p>}
                <div className="flex flex-wrap gap-1.5 mt-3 text-xs">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-300 border border-violet-500/20"><Hammer className="w-3 h-3" />{p.builder}</span>
                  {p.gates.map((g, i) => (
                    <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/20"><ShieldCheck className="w-3 h-3" />{g.role}: {g.gem}{g.provider_override ? ` (${g.provider_override})` : ""}</span>
                  ))}
                  {p.acceptance && <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">then you accept</span>}
                  <span className="px-2 py-0.5 rounded-md bg-gem-border text-slate-400">up to {p.max_attempts} attempts</span>
                </div>
              </button>
            ))}
          </div>

          <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-3">
            <p className="text-xs font-medium text-slate-400">Run <span className="font-mono text-violet-300">{picked || "..."}</span></p>
            <textarea rows={4} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="What should be built? Say what it does and where the files should go."
              className="w-full px-3 py-2 rounded-lg bg-gem-surface border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 resize-y" />
            <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
              <input type="checkbox" checked={allowRisky} onChange={(e) => setAllowRisky(e.target.checked)} className="accent-violet-500" />
              Skip the approve step for tools that can change things (otherwise each one pauses for you)
            </label>
            <button onClick={start} disabled={!picked || !message.trim() || running} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm">
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Run
            </button>
            {log.length > 0 && (
              <div className="rounded-lg bg-gem-surface border border-gem-border p-3 text-xs text-slate-300 space-y-1 max-h-80 overflow-y-auto">
                {log.map((line, i) => <div key={i}>{line}</div>)}
              </div>
            )}
            {runId && !running && (
              <div className="flex gap-2">
                <Link href={`/pipelines/runs/${runId}`} className="px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 text-xs">See the attempts, gates and decide</Link>
                <button onClick={() => router.push(`/pipelines/runs/${runId}`)} className="hidden" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
