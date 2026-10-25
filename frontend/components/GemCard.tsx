import Link from "next/link";
import { Gem } from "@/lib/api";
import { Cpu, Tag, Variable, LinkIcon, Clock, Bot } from "lucide-react";
import clsx from "clsx";

interface GemCardProps {
  gem: Gem;
  onDelete?: (id: string) => void;
}

const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  openai:    "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
};

export default function GemCard({ gem, onDelete }: GemCardProps) {
  const hasRefs = gem.system_prompt.includes("{{gem:");
  const timeAgo = getRelativeTime(gem.updated_at);

  return (
    <div className="group relative bg-gem-card border border-gem-border rounded-xl p-5 hover:border-violet-500/40 hover:bg-gem-hover transition-all duration-200 fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <Link
            href={`/gems/${gem.id}`}
            className="font-mono text-sm font-semibold text-violet-300 hover:text-violet-200 transition-colors block truncate"
          >
            {gem.name}
          </Link>
          <p className="text-slate-400 text-sm mt-1 line-clamp-2">
            {gem.description || "No description."}
          </p>
        </div>
        <span
          className={clsx(
            "shrink-0 px-2 py-0.5 rounded-md text-xs border font-medium",
            PROVIDER_COLORS[gem.provider] || "bg-slate-500/10 text-slate-400 border-slate-500/20"
          )}
        >
          {gem.provider}
        </span>
      </div>

      {/* Metadata chips */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {gem.kind === "agent" && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-violet-500/10 text-violet-300 border border-violet-500/20">
            <Bot className="w-3 h-3" />
            agent{gem.tools && gem.tools.length > 0 ? `, ${gem.tools.length} tool${gem.tools.length !== 1 ? "s" : ""}` : ""}
          </span>
        )}
        {gem.tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-gem-border text-slate-400"
          >
            <Tag className="w-3 h-3" />
            {tag}
          </span>
        ))}
        {gem.variables.length > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Variable className="w-3 h-3" />
            {gem.variables.length} var{gem.variables.length !== 1 ? "s" : ""}
          </span>
        )}
        {hasRefs && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-violet-500/10 text-violet-400 border border-violet-500/20">
            <LinkIcon className="w-3 h-3" />
            recursive
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-gem-border">
        <div className="flex items-center gap-1 text-xs text-slate-500">
          <Cpu className="w-3 h-3" />
          {gem.model}
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-xs text-slate-500">
            <Clock className="w-3 h-3" />
            {timeAgo}
          </span>
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Link
              href={`/gems/${gem.id}/edit`}
              className="px-2 py-1 text-xs rounded-md text-slate-400 hover:text-slate-200 hover:bg-gem-border transition-colors"
            >
              Edit
            </Link>
            {onDelete && (
              <button
                onClick={() => onDelete(gem.id)}
                className="px-2 py-1 text-xs rounded-md text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
              >
                Delete
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function getRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1)  return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24)  return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}
