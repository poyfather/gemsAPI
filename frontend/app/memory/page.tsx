"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { memory as memoryApi, Memory, MemoryKind, MEMORY_KINDS } from "@/lib/api";
import { explain } from "@/lib/words";
import { Brain, Search, Loader2, AlertTriangle, Trash2, Plus, Tag, Bot } from "lucide-react";
import clsx from "clsx";

const KIND_STYLES: Record<string, string> = {
  observation: "bg-slate-500/10 text-slate-300 border-slate-500/20",
  summary:     "bg-sky-500/10 text-sky-300 border-sky-500/20",
  decision:    "bg-violet-500/10 text-violet-300 border-violet-500/20",
  preference:  "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  lesson:      "bg-amber-500/10 text-amber-300 border-amber-500/20",
  handoff:     "bg-pink-500/10 text-pink-300 border-pink-500/20",
  note:        "bg-blue-500/10 text-blue-300 border-blue-500/20",
};

const KIND_WORDS: Record<string, string> = {
  observation: "what an assistant did",
  summary: "a summary",
  decision: "a decision",
  preference: "a preference",
  lesson: "a lesson",
  handoff: "a handoff for next time",
  note: "a note",
};

export default function MemoryPage() {
  const [items, setItems]     = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [query, setQuery]     = useState("");
  const [scope, setScope]     = useState("default");
  const [kind, setKind]       = useState<string>("");
  const [text, setText]       = useState("");
  const [newKind, setNewKind] = useState<MemoryKind>("note");
  const [newTags, setNewTags] = useState("");
  const [saving, setSaving]   = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await memoryApi.list(query, scope, kind ? [kind] : []));
    } catch (e) {
      setError(explain(e, "Could not load your memory."));
    } finally {
      setLoading(false);
    }
  }, [query, scope, kind]);

  useEffect(() => {
    const t = setTimeout(load, query ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, query]);

  const remember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try {
      await memoryApi.remember({ text: text.trim(), kind: newKind, scope, tags: newTags.split(",").map((t) => t.trim()).filter(Boolean) });
      setText(""); setNewTags("");
      await load();
    } catch (err) {
      alert(explain(err, "Could not save that."));
    } finally {
      setSaving(false);
    }
  };

  const forget = async (m: Memory) => {
    if (!confirm("Forget this? It cannot be brought back.")) return;
    try {
      await memoryApi.forget(m.id);
      setItems((prev) => prev.filter((x) => x.id !== m.id));
    } catch (err) {
      alert(explain(err, "Could not forget it."));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Brain className="w-6 h-6 text-violet-400" />
          Memory
        </h1>
        <p className="text-slate-400 mt-1 text-sm max-w-3xl">
          What Lapidary remembers across runs, chats and apps: what each assistant did, plus the notes, decisions, preferences and lessons you or they wrote down. A prompt marked &quot;remembers earlier work&quot; gets the best matches before each message. Anything inside &lt;private&gt; tags is never stored, and you can forget anything here.
        </p>
      </div>

      <form onSubmit={remember} className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-3">
        <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> Remember something</label>
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="A decision, a preference, a lesson, or a note for next time..."
          className="w-full px-3 py-2 rounded-lg bg-gem-surface border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 resize-y"
        />
        <div className="flex flex-wrap gap-2 items-center">
          <select value={newKind} onChange={(e) => setNewKind(e.target.value as MemoryKind)} className="px-2.5 py-1.5 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs">
            {MEMORY_KINDS.filter((k) => k !== "observation").map((k) => <option key={k} value={k}>{KIND_WORDS[k]}</option>)}
          </select>
          <input value={newTags} onChange={(e) => setNewTags(e.target.value)} placeholder="tags, comma separated" className="px-2.5 py-1.5 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs w-56" />
          <button type="submit" disabled={saving || !text.trim()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs">
            {saving && <Loader2 className="w-3 h-3 animate-spin" />} Remember
          </button>
        </div>
      </form>

      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search what was remembered..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500"
          />
        </div>
        <select value={kind} onChange={(e) => setKind(e.target.value)} className="px-2.5 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-300 text-sm">
          <option value="">every kind</option>
          {MEMORY_KINDS.map((k) => <option key={k} value={k}>{KIND_WORDS[k]}</option>)}
        </select>
        <input value={scope} onChange={(e) => setScope(e.target.value || "default")} title="Scope keeps projects apart" className="px-2.5 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-300 text-sm w-32" />
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16 text-slate-500"><Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...</div>
      )}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <div><p className="font-medium text-sm">Could not load your memory</p><p className="text-xs mt-0.5 text-red-400/70">{error}</p></div>
          <button onClick={load} className="ml-auto px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-xs">Retry</button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <div className="text-center py-16 text-slate-500 text-sm">
          {query ? "Nothing matches." : "Nothing remembered yet. Run an assistant, or write a note above."}
        </div>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="space-y-2">
          {items.map((m) => (
            <div key={m.id} className="group bg-gem-card border border-gem-border rounded-xl p-4 flex gap-3 items-start">
              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className={clsx("px-2 py-0.5 rounded-md border", KIND_STYLES[m.kind] ?? KIND_STYLES.note)}>{KIND_WORDS[m.kind] ?? m.kind}</span>
                  <span className="text-slate-500">{new Date(m.created_at).toLocaleString()}</span>
                  {m.gem_name && <span className="flex items-center gap-1 text-slate-500"><Bot className="w-3 h-3" /><span className="font-mono">{m.gem_name}</span></span>}
                  {m.run_id && <Link href={`/runs/${m.run_id}`} className="text-violet-400 hover:text-violet-300 underline">see what it did</Link>}
                  {m.tags.map((t) => <span key={t} className="flex items-center gap-1 text-slate-500"><Tag className="w-3 h-3" />{t}</span>)}
                </div>
                <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200">{m.text}</pre>
              </div>
              <button onClick={() => forget(m)} title="Forget" className="p-1.5 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
