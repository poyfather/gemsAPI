"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { runs as runsApi, RunResult } from "@/lib/api";
import { explain, providerLabel, statusLabel } from "@/lib/words";
import RunEvents from "@/components/RunEvents";
import { ArrowLeft, Loader2, AlertTriangle, Bot, MessageSquare } from "lucide-react";
import clsx from "clsx";

const STATUS_STYLES: Record<string, string> = {
  finished:  "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  waiting_approval: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  failed:    "bg-red-500/10 text-red-400 border-red-500/20",
  max_steps: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  running:   "bg-blue-500/10 text-blue-400 border-blue-500/20",
};

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);

  const decide = async (approve: boolean) => {
    setDeciding(true);
    try {
      await runsApi.approve(id, approve, (event) => {
        setResult((r) => (r ? { ...r, events: [...r.events, event] } : r));
      });
      const fresh = await runsApi.get(id);
      setResult(fresh);
    } catch (e) {
      setError(explain(e, "Could not continue."));
    } finally {
      setDeciding(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    runsApi
      .get(id)
      .then((r) => { if (!cancelled) setResult(r); })
      .catch((e) => { if (!cancelled) setError(explain(e, "That run was not found.")); });
    return () => { cancelled = true; };
  }, [id]);

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p>{error}</p>
        <Link href="/chat" className="ml-auto text-sm underline">Back to chat</Link>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...
      </div>
    );
  }

  const { run, events } = result;
  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link href="/chat" className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-gem-hover transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-violet-400" />
            What <span className="font-mono text-violet-300">{run.gem_name}</span> did
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">Everything the assistant did for one request, kept so you can check it later or continue it if it is waiting for you.<span className="font-mono"> {run.id}</span></p>
        </div>
        <span className={clsx("px-2 py-0.5 rounded-md text-xs border", STATUS_STYLES[run.status] ?? "")}>{statusLabel(run.status)}</span>
        <Link
          href={`/chat?gem=${run.gem_name}`}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 text-sm transition-colors"
        >
          <MessageSquare className="w-4 h-4" />
          Ask it again
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        {[
          ["Which AI", `${providerLabel(run.provider)}, ${run.model}`],
          ["Steps", String(run.steps)],
          ["Tokens (in, out)", `${run.input_tokens}, ${run.output_tokens}`],
          ["Started", new Date(run.created_at).toLocaleString()],
        ].map(([label, value]) => (
          <div key={label} className="bg-gem-card border border-gem-border rounded-xl p-3">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="text-slate-300 mt-0.5 break-words">{value}</p>
          </div>
        ))}
      </div>

      {run.error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400 font-mono">{run.error}</div>
      )}

      <section className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2">
        <h2 className="text-xs font-medium text-slate-400">What you asked</h2>
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200">{run.input}</pre>
      </section>

      <section className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2">
        <h2 className="text-xs font-medium text-slate-400">What happened, step by step</h2>
        <RunEvents events={events} onDecide={run.status === "waiting_approval" ? decide : undefined} deciding={deciding} />
      </section>

      <section className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-2">
        <h2 className="text-xs font-medium text-slate-400">What it answered</h2>
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200">{run.output ?? ""}</pre>
      </section>
    </div>
  );
}
