"use client";

import { useEffect, useState } from "react";
import { gems as gemsApi, EvalCase, EvalCheck, EvalEstimate, EvalRun, EvalRunReport, Gem } from "@/lib/api";
import { explain, providerLabel } from "@/lib/words";
import { FlaskConical, Loader2, Play, Plus, Trash2, Check, X, Flag, ChevronDown, ChevronRight } from "lucide-react";
import clsx from "clsx";

const CHECKS: { id: EvalCheck; label: string; hint: string }[] = [
  { id: "contains", label: "the answer contains", hint: "a word or phrase, any case" },
  { id: "not_contains", label: "the answer does not contain", hint: "a word or phrase that must not appear" },
  { id: "all_of", label: "the answer contains all of", hint: "one phrase per line" },
  { id: "equals", label: "the answer is exactly", hint: "the whole answer, ignoring spaces at the ends" },
  { id: "json", label: "the answer is JSON", hint: "optional: a JSON schema with type, required, properties, items, enum" },
  { id: "judge", label: "an AI judges it against", hint: "what a good answer does, in plain words; costs one more call" },
];
const checkLabel = (c: string) => CHECKS.find((x) => x.id === c)?.label ?? c;
/** "the AI on this PC" reads better than providerLabel's "on this PC" after "calls to". */
const aiName = (provider: string) => (provider === "local" ? "the AI on this PC" : providerLabel(provider));

/** Tests for a prompt (roadmap 28): cases, the cost before a run, the score, and regressions against the baseline. */
export default function GemEvals({ gem }: { gem: Gem }) {
  const [cases, setCases] = useState<EvalCase[] | null>(null);
  const [estimate, setEstimate] = useState<EvalEstimate | null>(null);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [report, setReport] = useState<EvalRunReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [reload, setReload] = useState(0);
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [draft, setDraft] = useState({ name: "", input: "", check: "contains" as EvalCheck, expected: "", variables: {} as Record<string, string> });

  useEffect(() => {
    let cancelled = false;
    Promise.all([gemsApi.evals.list(gem.id), gemsApi.evals.estimate(gem.id), gemsApi.evals.runs(gem.id)])
      .then(([c, e, r]) => { if (!cancelled) { setCases(c); setEstimate(e); setRuns(r); } })
      .catch((e) => { if (!cancelled) setError(explain(e, "Could not load the tests.")); });
    return () => { cancelled = true; };
  }, [gem.id, gem.updated_at, reload]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await gemsApi.evals.add(gem.id, draft);
      setDraft({ name: "", input: "", check: draft.check, expected: "", variables: {} });
      setAdding(false);
      setReload((n) => n + 1);
    } catch (err) {
      alert(explain(err, "Could not add the test."));
    }
  };

  const remove = async (c: EvalCase) => {
    if (!confirm(`Remove the test "${c.name || c.input.slice(0, 40)}"?`)) return;
    try { await gemsApi.evals.remove(gem.id, c.id); setReload((n) => n + 1); } catch (err) { alert(explain(err, "Could not remove it.")); }
  };

  const runAll = async () => {
    if (!estimate) return;
    const cost = estimate.free ? "It runs on this PC, so it is free." : `It is billed to your ${providerLabel(estimate.provider)} account.`;
    if (!confirm(`Run ${estimate.cases} test${estimate.cases === 1 ? "" : "s"}? That is ${estimate.calls} call${estimate.calls === 1 ? "" : "s"} to ${estimate.model}, about ${estimate.input_tokens.toLocaleString()} tokens in and at most ${estimate.max_output_tokens.toLocaleString()} out. ${cost}`)) return;
    setRunning(true); setReport(null);
    try {
      setReport(await gemsApi.evals.run(gem.id));
      setReload((n) => n + 1);
    } catch (err) {
      setError(explain(err, "The tests could not run."));
    } finally {
      setRunning(false);
    }
  };

  const makeBaseline = async (r: EvalRun) => {
    try { await gemsApi.evals.setBaseline(gem.id, r.id); setReload((n) => n + 1); } catch (err) { alert(explain(err, "Could not change the baseline.")); }
  };

  const hint = CHECKS.find((c) => c.id === draft.check)?.hint ?? "";
  const input = "w-full px-2.5 py-1.5 rounded-md bg-gem-surface border border-gem-border text-slate-200 text-xs placeholder:text-slate-600 focus:outline-hidden focus:ring-1 focus:ring-violet-500";

  return (
    <div className="bg-gem-card border border-gem-border rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gem-border gap-3">
        <span className="text-sm font-medium text-slate-300 flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-violet-400" /> Tests
          <span className="font-normal text-slate-500 hidden sm:inline">(questions with the answer you expect; run them before and after a change)</span>
        </span>
        <div className="flex gap-2 shrink-0">
          <button onClick={() => setAdding(!adding)} className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-gem-border hover:bg-gem-hover text-slate-300 text-xs"><Plus className="w-3 h-3" /> Add</button>
          <button onClick={runAll} disabled={running || !cases?.length} className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 text-xs disabled:opacity-40">
            {running ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Run
          </button>
        </div>
      </div>

      {error && <p className="px-4 py-2 text-xs text-red-400">{error}</p>}

      {adding && (
        <form onSubmit={add} className="px-4 py-3 border-b border-gem-border space-y-2">
          <input className={input} placeholder="A short name (optional)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <textarea className={input} rows={2} required placeholder="What the prompt is asked" value={draft.input} onChange={(e) => setDraft({ ...draft, input: e.target.value })} />
          {gem.variables.map((v) => (
            <div key={v} className="flex items-center gap-2">
              <code className="text-xs text-blue-400 w-28 shrink-0">{"{" + v + "}"}</code>
              <input className={input} placeholder={`Value for ${v}`} value={draft.variables[v] ?? ""} onChange={(e) => setDraft({ ...draft, variables: { ...draft.variables, [v]: e.target.value } })} />
            </div>
          ))}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 shrink-0">Pass when</span>
            <select className={input} value={draft.check} onChange={(e) => setDraft({ ...draft, check: e.target.value as EvalCheck })}>
              {CHECKS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </div>
          <textarea className={clsx(input, draft.check === "json" && "font-mono")} rows={draft.check === "all_of" || draft.check === "json" || draft.check === "judge" ? 3 : 1}
            required={draft.check !== "json"} placeholder={hint} value={draft.expected} onChange={(e) => setDraft({ ...draft, expected: e.target.value })} />
          <div className="flex gap-2">
            <button type="submit" className="px-3 py-1 rounded-md bg-violet-600 hover:bg-violet-500 text-white text-xs">Add test</button>
            <button type="button" onClick={() => setAdding(false)} className="px-3 py-1 rounded-md bg-gem-border text-slate-300 text-xs">Cancel</button>
          </div>
        </form>
      )}

      <div className="px-4 py-3 space-y-3">
        {!cases && !error && <div className="text-slate-500 text-sm flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
        {cases && cases.length === 0 && !adding && (
          <p className="text-sm text-slate-500">No tests yet. Add a question and what a good answer must contain, then run it whenever you change the prompt; Lapidary remembers each score with the version it tested.</p>
        )}
        {cases && cases.length > 0 && (
          <ul className="space-y-1.5">
            {cases.map((c) => (
              <li key={c.id} className="group flex items-start gap-2 text-xs">
                <div className="flex-1 min-w-0">
                  <span className="text-slate-300">{c.name || c.input.slice(0, 60)}</span>
                  <span className="text-slate-500"> · {checkLabel(c.check)} </span>
                  <span className="text-slate-400 font-mono break-words">{c.expected.length > 80 ? c.expected.slice(0, 80) + "..." : c.expected || "(any valid JSON)"}</span>
                </div>
                <button onClick={() => remove(c)} title="Remove" className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
        {estimate && estimate.cases > 0 && (
          <p className="text-xs text-slate-500">
            A run makes {estimate.calls} call{estimate.calls === 1 ? "" : "s"} to {aiName(estimate.provider)} ({estimate.model}), about {estimate.input_tokens.toLocaleString()} tokens in.{" "}
            <span className={estimate.free ? "text-emerald-400" : "text-amber-300"}>{estimate.free ? "Free: it runs on this PC." : "Billed to your own account."}</span>
          </p>
        )}

        {report && (
          <div className="rounded-lg border border-gem-border bg-gem-surface p-3 space-y-2">
            <p className="text-sm text-slate-200">
              <b className={report.run.passed === report.run.total ? "text-emerald-400" : "text-amber-300"}>{report.run.passed} of {report.run.total} passed</b>
              <span className="text-slate-500"> on version {report.run.gem_version}</span>
              {report.baseline && <span className="text-slate-500"> · baseline had {report.baseline.passed} of {report.baseline.total} on version {report.baseline.gem_version}</span>}
            </p>
            {report.regressions.length > 0 && <p className="text-xs text-red-400">Worse than the baseline: {report.regressions.join(", ")}</p>}
            {report.fixed.length > 0 && <p className="text-xs text-emerald-400">Better than the baseline: {report.fixed.join(", ")}</p>}
            <ul className="space-y-1">
              {report.run.results.map((r) => (
                <li key={r.case_id} className="text-xs">
                  <button onClick={() => setOpen(open === r.case_id ? null : r.case_id)} className="flex items-start gap-1.5 text-left w-full">
                    {open === r.case_id ? <ChevronDown className="w-3.5 h-3.5 text-slate-500 mt-0.5" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-500 mt-0.5" />}
                    {r.passed ? <Check className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" /> : <X className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />}
                    <span className="text-slate-300">{r.name}</span><span className="text-slate-500">: {r.detail}</span>
                  </button>
                  {open === r.case_id && <pre className="mt-1 ml-8 whitespace-pre-wrap font-sans text-slate-400 max-h-48 overflow-y-auto">{r.output || "(no answer)"}</pre>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {runs.length > 0 && (
          <div className="pt-1">
            <p className="text-xs text-slate-500 mb-1">Past runs</p>
            <ul className="space-y-1">
              {runs.slice(0, 8).map((r) => (
                <li key={r.id} className="flex items-center gap-2 text-xs">
                  <span className={clsx("font-mono", r.passed === r.total ? "text-emerald-400" : "text-amber-300")}>{r.passed}/{r.total}</span>
                  <span className="text-slate-400">v{r.gem_version}</span>
                  <span className="text-slate-500 truncate">{providerLabel(r.provider)} · {new Date(r.created_at).toLocaleString()}</span>
                  {r.baseline
                    ? <span className="ml-auto flex items-center gap-1 text-violet-300"><Flag className="w-3 h-3" /> baseline</span>
                    : <button onClick={() => makeBaseline(r)} className="ml-auto text-slate-500 hover:text-violet-300">make baseline</button>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
