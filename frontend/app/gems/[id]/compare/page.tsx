"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { gems as gemsApi, chat as chatApi, AvailableModels, CompareResult, CompareTestsResult, CompareVariant, Gem, GemVersionSummary } from "@/lib/api";
import { explain, providerLabel } from "@/lib/words";
import { ArrowLeft, Columns2, Loader2, Plus, X, Check, Play, FlaskConical } from "lucide-react";
import clsx from "clsx";

type Column = { version: string; provider: string; model: string };
const blank: Column = { version: "", provider: "", model: "" };
const aiName = (p: string) => (p === "local" ? "the AI on this PC" : providerLabel(p));

/** Side by side (roadmap 30): one input, two to four versions or AIs, answers or test results next to each other. */
export default function ComparePage() {
  const { id } = useParams<{ id: string }>();
  const [gem, setGem] = useState<Gem | null>(null);
  const [versions, setVersions] = useState<GemVersionSummary[]>([]);
  const [models, setModels] = useState<AvailableModels>({});
  const [testCount, setTestCount] = useState(0);
  const [columns, setColumns] = useState<Column[]>([blank, blank]);
  const [message, setMessage] = useState("");
  const [vars, setVars] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"" | "answers" | "tests">("");
  const [answers, setAnswers] = useState<CompareResult | null>(null);
  const [grid, setGrid] = useState<CompareTestsResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([gemsApi.get(decodeURIComponent(id)), chatApi.models()])
      .then(async ([g, m]) => {
        const [v, cases] = await Promise.all([gemsApi.versions(g.id), gemsApi.evals.list(g.id)]);
        if (cancelled) return;
        setGem(g); setModels(m); setVersions(v); setTestCount(cases.length);
        // A sensible start: the version before the current one against the current one, when there is one.
        if (v.length > 1) setColumns([{ ...blank, version: String(v[1].version) }, { ...blank, version: String(v[0].version) }]);
      })
      .catch((e) => { if (!cancelled) setError(explain(e, "Could not load this prompt.")); });
    return () => { cancelled = true; };
  }, [id]);

  const variants = (): CompareVariant[] => columns.map((c) => ({
    version: c.version ? Number(c.version) : null,
    provider_override: c.provider || undefined,
    model_override: c.provider && c.model ? c.model : undefined,
  }));

  const go = async (kind: "answers" | "tests") => {
    if (!gem) return;
    setError(null);
    const body = { message, variables: vars, variants: variants() };
    try {
      const est = await gemsApi.compare.estimate(gem.id, body, kind === "tests");
      const cost = est.free ? "All of it runs on this PC, so it is free." : "Columns that use Claude or ChatGPT are billed to your own account.";
      const what = kind === "tests" ? `${est.tests} test${est.tests === 1 ? "" : "s"} in ${columns.length} columns` : `${columns.length} answers`;
      if (!confirm(`Compare ${what}? That is ${est.calls} model call${est.calls === 1 ? "" : "s"}. ${cost}`)) return;
      setBusy(kind);
      if (kind === "answers") { setGrid(null); setAnswers(await gemsApi.compare.run(gem.id, body)); }
      else { setAnswers(null); setGrid(await gemsApi.compare.tests(gem.id, body)); }
    } catch (e) {
      setError(explain(e, "The comparison could not run."));
    } finally {
      setBusy("");
    }
  };

  if (!gem) {
    return error
      ? <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>
      : <div className="flex items-center justify-center py-20 text-slate-500"><Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...</div>;
  }

  const field = "w-full px-2.5 py-1.5 rounded-md bg-gem-surface border border-gem-border text-slate-200 text-xs focus:outline-hidden focus:ring-1 focus:ring-violet-500";
  const isAgent = gem.kind === "agent";
  const best = grid ? Math.max(...grid.totals) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href={`/gems/${gem.id}`} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-gem-hover transition-colors"><ArrowLeft className="w-5 h-5" /></Link>
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2"><Columns2 className="w-5 h-5 text-violet-400" /> Compare <span className="font-mono text-violet-300">{gem.name}</span></h1>
          <p className="text-slate-400 text-sm mt-0.5">Same question, different versions or AIs, side by side. Or run the prompt&apos;s tests in every column to see which one does better.</p>
        </div>
      </div>

      <div className={clsx("grid gap-3", columns.length === 2 ? "grid-cols-1 md:grid-cols-2" : columns.length === 3 ? "grid-cols-1 md:grid-cols-3" : "grid-cols-1 md:grid-cols-2 xl:grid-cols-4")}>
        {columns.map((c, i) => (
          <div key={i} className="bg-gem-card border border-gem-border rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Column {i + 1}</span>
              {columns.length > 2 && <button onClick={() => setColumns(columns.filter((_, j) => j !== i))} title="Remove column" className="text-slate-500 hover:text-red-400"><X className="w-3.5 h-3.5" /></button>}
            </div>
            <select className={field} value={c.version} disabled={isAgent} onChange={(e) => setColumns(columns.map((x, j) => (j === i ? { ...x, version: e.target.value } : x)))}>
              <option value="">Current version</option>
              {versions.map((v) => <option key={v.version} value={v.version}>v{v.version}{v.current ? " (current)" : ""}{v.note ? `: ${v.note.slice(0, 40)}` : ""}</option>)}
            </select>
            <select className={field} value={c.provider} onChange={(e) => setColumns(columns.map((x, j) => (j === i ? { ...x, provider: e.target.value, model: "" } : x)))}>
              <option value="">The AI set on that version</option>
              <option value="anthropic">Claude</option>
              <option value="openai">ChatGPT</option>
              <option value="local">The AI on this PC</option>
            </select>
            {c.provider && (models[c.provider] ?? []).length > 0 && (
              <select className={field} value={c.model} onChange={(e) => setColumns(columns.map((x, j) => (j === i ? { ...x, model: e.target.value } : x)))}>
                <option value="">Its default model</option>
                {(models[c.provider] ?? []).map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            )}
          </div>
        ))}
      </div>
      {isAgent && <p className="text-xs text-slate-500">This is an assistant, so every column uses its current version; compare different AIs instead.</p>}
      {columns.length < 4 && (
        <button onClick={() => setColumns([...columns, blank])} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200"><Plus className="w-3.5 h-3.5" /> Add a column</button>
      )}

      <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-3">
        <textarea rows={3} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="The question every column answers"
          className="w-full px-3 py-2 rounded-lg bg-gem-surface border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 resize-y" />
        {gem.variables.map((v) => (
          <div key={v} className="flex items-center gap-2">
            <code className="text-xs text-blue-400 w-28 shrink-0">{"{" + v + "}"}</code>
            <input className={field} placeholder={`Value for ${v}`} value={vars[v] ?? ""} onChange={(e) => setVars({ ...vars, [v]: e.target.value })} />
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          <button onClick={() => go("answers")} disabled={!!busy || !message.trim()} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm">
            {busy === "answers" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Compare answers
          </button>
          <button onClick={() => go("tests")} disabled={!!busy || testCount === 0} title={testCount === 0 ? "Add tests on the prompt's page first" : ""}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gem-border hover:bg-gem-hover disabled:opacity-50 text-slate-200 text-sm">
            {busy === "tests" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />} Compare on the {testCount} test{testCount === 1 ? "" : "s"}
          </button>
        </div>
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>

      {answers && (
        <div className={clsx("grid gap-3", answers.columns.length === 2 ? "grid-cols-1 md:grid-cols-2" : answers.columns.length === 3 ? "grid-cols-1 md:grid-cols-3" : "grid-cols-1 md:grid-cols-2 xl:grid-cols-4")}>
          {answers.columns.map((c, i) => (
            <div key={i} className="bg-gem-card border border-gem-border rounded-xl overflow-hidden">
              <div className="px-3 py-2 border-b border-gem-border">
                <div className="text-xs text-violet-300 font-medium">{c.label}</div>
                <div className="text-xs text-slate-500">{aiName(c.provider)} · {c.seconds}s{c.run_id && <> · <Link href={`/runs/${c.run_id}`} className="underline">what it did</Link></>}</div>
              </div>
              {c.error
                ? <p className="p-3 text-xs text-red-400">{c.error}</p>
                : <pre className="p-3 whitespace-pre-wrap font-sans text-sm text-slate-200 max-h-[32rem] overflow-y-auto">{c.output}</pre>}
            </div>
          ))}
        </div>
      )}

      {grid && (
        <div className="bg-gem-card border border-gem-border rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gem-border">
                <th className="text-left px-3 py-2 text-slate-500 font-normal">Test</th>
                {grid.columns.map((c, i) => <th key={i} className="text-left px-3 py-2 text-violet-300 font-medium">{c.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {grid.cases.map((row, r) => (
                <tr key={r} className="border-b border-gem-border/60 align-top">
                  <td className="px-3 py-2 text-slate-300">{row.name}</td>
                  {row.results.map((res, i) => (
                    <td key={i} className="px-3 py-2">
                      <span className="flex items-start gap-1.5">
                        {res.passed ? <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" /> : <X className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />}
                        <span className="text-slate-500">{res.detail}</span>
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <td className="px-3 py-2 text-slate-400">Passed</td>
                {grid.totals.map((t, i) => (
                  <td key={i} className={clsx("px-3 py-2 font-mono", t === best && t > 0 ? "text-emerald-400" : "text-slate-300")}>{t} of {grid.cases.length}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
