"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { pipelines as pipelinesApi, PipelineRun } from "@/lib/api";
import { explain, pipelineStatusLabel } from "@/lib/words";
import { ArrowLeft, Loader2, AlertTriangle, GitBranch, ShieldCheck, ShieldX, Hammer, Clock } from "lucide-react";
import clsx from "clsx";

const STATUS_STYLES: Record<string, string> = {
  passed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  waiting_acceptance: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  waiting_approval: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  max_attempts: "bg-red-500/10 text-red-400 border-red-500/20",
  running: "bg-blue-500/10 text-blue-400 border-blue-500/20",
};

export default function PipelineRunPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [log, setLog] = useState<string[]>([]);

  const load = useCallback(async () => {
    try { setRun(await pipelinesApi.getRun(id)); } catch (e) { setError(explain(e, "That pipeline run was not found.")); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const resume = async (data: { accept?: boolean; note?: string }) => {
    setBusy(true); setLog([]);
    try {
      await pipelinesApi.resume(id, data, (e) => setLog((prev) => [...prev, `${e.type}${e.data && "gem" in e.data ? ` ${String(e.data.gem)}` : ""}${e.data && "verdict" in e.data ? `: ${String(e.data.verdict)}` : ""}`]));
    } catch (e) {
      setLog((prev) => [...prev, explain(e)]);
    } finally {
      setBusy(false);
      await load();
    }
  };

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
        <AlertTriangle className="w-5 h-5 shrink-0" /><p>{error}</p>
        <Link href="/pipelines" className="ml-auto text-sm underline">Back to pipelines</Link>
      </div>
    );
  }
  if (!run) return <div className="flex items-center justify-center py-20 text-slate-500"><Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...</div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link href="/pipelines" className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-gem-hover transition-colors"><ArrowLeft className="w-5 h-5" /></Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-white flex items-center gap-2"><GitBranch className="w-5 h-5 text-violet-400" /> What <span className="font-mono text-violet-300">{run.pipeline_name}</span> did</h1>
          <p className="text-xs text-slate-500 mt-0.5">Every attempt, what each gate said, and where it stands. Each attempt and gate is an assistant run you can open.</p>
        </div>
        <span className={clsx("px-2 py-0.5 rounded-md text-xs border", STATUS_STYLES[run.status] ?? "")}>{pipelineStatusLabel(run.status)}</span>
      </div>

      <section className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2">
        <h2 className="text-xs font-medium text-slate-400">What you asked</h2>
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200">{run.input}</pre>
      </section>

      {run.status === "waiting_acceptance" && (
        <section className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-4 space-y-3">
          <p className="text-sm text-amber-300">Every gate passed. Look at the result below and decide.</p>
          <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="If you send it back, say what is wrong; the builder gets this as findings."
            className="w-full px-3 py-2 rounded-lg bg-gem-surface border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-amber-500 resize-y" />
          <div className="flex gap-2">
            <button disabled={busy} onClick={() => resume({ accept: true })} className="px-3 py-1.5 rounded-md bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 text-sm disabled:opacity-50">Accept</button>
            <button disabled={busy || !note.trim()} onClick={() => resume({ accept: false, note })} className="px-3 py-1.5 rounded-md bg-red-500/10 hover:bg-red-500/20 text-red-400 text-sm disabled:opacity-50">Send it back</button>
          </div>
        </section>
      )}
      {run.status === "waiting_approval" && (
        <section className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-4 space-y-3">
          <p className="text-sm text-amber-300">An assistant wants to use a tool that can change things. Approve or deny it on its run page, then continue here.</p>
          <div className="flex gap-2">
            {run.waiting_run_id && <Link href={`/runs/${run.waiting_run_id}`} className="px-3 py-1.5 rounded-md bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 text-sm">Open the run that is waiting</Link>}
            <button disabled={busy} onClick={() => resume({})} className="px-3 py-1.5 rounded-md bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 text-sm disabled:opacity-50">Continue the pipeline</button>
          </div>
        </section>
      )}
      {busy && <div className="flex items-center gap-2 text-sm text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> working...</div>}
      {log.length > 0 && <div className="rounded-lg bg-gem-surface border border-gem-border p-3 text-xs text-slate-400 space-y-1">{log.map((l, i) => <div key={i}>{l}</div>)}</div>}
      {run.error && <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400 font-mono">{run.error}</div>}

      {run.attempts.map((a) => (
        <section key={a.number} className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-3">
          <h2 className="text-sm font-medium text-slate-300 flex items-center gap-2"><Hammer className="w-4 h-4 text-violet-400" /> Attempt {a.number}
            <span className="text-xs text-slate-500">builder {a.builder_status}</span>
            {a.builder_run_id && <Link href={`/runs/${a.builder_run_id}`} className="text-xs text-violet-400 hover:text-violet-300 underline">see what the builder did</Link>}
          </h2>
          {a.feedback && <div className="text-xs text-amber-300/90 border-l-2 border-amber-500/40 pl-3 whitespace-pre-wrap">Told the builder: {a.feedback}</div>}
          {a.output && <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200 max-h-64 overflow-y-auto">{a.output}</pre>}
          <div className="space-y-2">
            {a.gates.map((g, i) => (
              <div key={i} className={clsx("rounded-lg border p-3 text-xs space-y-1", g.verdict === "pass" ? "border-emerald-500/30 bg-emerald-500/5" : g.verdict === "fail" ? "border-red-500/30 bg-red-500/5" : "border-amber-500/30 bg-amber-500/5")}>
                <div className="flex items-center gap-2">
                  {g.verdict === "pass" ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> : g.verdict === "fail" ? <ShieldX className="w-3.5 h-3.5 text-red-400" /> : <Clock className="w-3.5 h-3.5 text-amber-400" />}
                  <span className="text-slate-300">{g.role} gate</span><span className="font-mono text-violet-300">{g.gem}</span>
                  <span className={g.verdict === "pass" ? "text-emerald-400" : g.verdict === "fail" ? "text-red-400" : "text-amber-400"}>{g.verdict}</span>
                  {g.run_id && <Link href={`/runs/${g.run_id}`} className="ml-auto text-violet-400 hover:text-violet-300 underline">see what it checked</Link>}
                </div>
                {g.findings && <pre className="whitespace-pre-wrap font-sans text-slate-400">{g.findings}</pre>}
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
