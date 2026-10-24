"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { gems as gemsApi, Gem, errorMessage } from "@/lib/api";
import GemCard from "@/components/GemCard";
import {
  Search, Plus, Loader2, AlertTriangle, Gem as GemIcon,
  LinkIcon, Variable, Tag
} from "lucide-react";
import clsx from "clsx";

export default function GemsPage() {
  const [allGems, setAllGems]     = useState<Gem[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [search, setSearch]       = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const fetchGems = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await gemsApi.list();
      setAllGems(data);
    } catch (e) {
      setError(errorMessage(e, "Failed to load gems. Is the backend running?"));
    } finally {
      setLoading(false);
    }
  };

  // Initial load. `loading` already starts true, so nothing is set synchronously here;
  // state updates happen once the request settles. fetchGems() stays for the Retry button.
  useEffect(() => {
    let cancelled = false;
    gemsApi
      .list()
      .then((data) => { if (!cancelled) setAllGems(data); })
      .catch((e) => { if (!cancelled) setError(errorMessage(e, "Failed to load gems. Is the backend running?")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this gem? This cannot be undone.")) return;
    try {
      await gemsApi.delete(id);
      setAllGems((prev) => prev.filter((g) => g.id !== id));
    } catch (e) {
      alert(errorMessage(e, "Failed to delete gem."));
    }
  };

  // All unique tags
  const allTags = Array.from(new Set(allGems.flatMap((g) => g.tags))).sort();

  // Filtered gems
  const filtered = allGems.filter((g) => {
    const matchSearch =
      !search ||
      g.name.toLowerCase().includes(search.toLowerCase()) ||
      g.description.toLowerCase().includes(search.toLowerCase()) ||
      g.tags.some((t) => t.toLowerCase().includes(search.toLowerCase()));
    const matchTag = !activeTag || g.tags.includes(activeTag);
    return matchSearch && matchTag;
  });

  // Stats
  const stats = {
    total:     allGems.length,
    recursive: allGems.filter((g) => g.system_prompt.includes("{{gem:")).length,
    withVars:  allGems.filter((g) => g.variables.length > 0).length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <GemIcon className="w-6 h-6 text-violet-400" />
            Gems Library
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Reusable prompts with variable substitution and recursive composition
          </p>
        </div>
        <Link
          href="/gems/new"
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Gem
        </Link>
      </div>

      {/* Stats bar */}
      {!loading && !error && allGems.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Total Gems",    value: stats.total,     icon: GemIcon,    color: "text-violet-400" },
            { label: "Recursive",     value: stats.recursive, icon: LinkIcon,   color: "text-blue-400" },
            { label: "With Variables",value: stats.withVars,  icon: Variable,   color: "text-emerald-400" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-gem-card border border-gem-border rounded-xl p-4 flex items-center gap-3">
              <Icon className={clsx("w-5 h-5", color)} />
              <div>
                <div className="text-xl font-bold text-white">{value}</div>
                <div className="text-xs text-slate-500">{label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Search + Tag filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search gems by name, description, or tag..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-gem-card border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-violet-500 transition"
          />
        </div>
        {allTags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setActiveTag(null)}
              className={clsx(
                "px-2.5 py-1 rounded-lg text-xs transition-colors",
                activeTag === null
                  ? "bg-violet-600 text-white"
                  : "bg-gem-border text-slate-400 hover:text-slate-200"
              )}
            >
              All
            </button>
            {allTags.map((tag) => (
              <button
                key={tag}
                onClick={() => setActiveTag(tag === activeTag ? null : tag)}
                className={clsx(
                  "flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs transition-colors",
                  tag === activeTag
                    ? "bg-violet-600 text-white"
                    : "bg-gem-border text-slate-400 hover:text-slate-200"
                )}
              >
                <Tag className="w-3 h-3" />
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-20 text-slate-500">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          Loading gems...
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <div>
            <p className="font-medium text-sm">Could not load gems</p>
            <p className="text-xs mt-0.5 text-red-400/70">{error}</p>
          </div>
          <button
            onClick={fetchGems}
            className="ml-auto px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-xs transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && allGems.length === 0 && (
        <div className="text-center py-20 space-y-3">
          <GemIcon className="w-12 h-12 text-slate-700 mx-auto" />
          <p className="text-slate-500">No gems yet.</p>
          <Link
            href="/gems/new"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create your first gem
          </Link>
        </div>
      )}

      {/* No results after filter */}
      {!loading && !error && allGems.length > 0 && filtered.length === 0 && (
        <div className="text-center py-16 text-slate-500 text-sm">
          No gems match &quot;{search}&quot;{activeTag ? ` in tag "${activeTag}"` : ""}.
        </div>
      )}

      {/* Gem grid */}
      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((gem) => (
            <GemCard key={gem.id} gem={gem} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
