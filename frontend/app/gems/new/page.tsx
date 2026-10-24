import GemForm from "@/components/GemForm";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function NewGemPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/gems"
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-gem-hover transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white">New Gem</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Create a reusable prompt. Use{" "}
            <code className="text-violet-400 bg-violet-500/10 px-1 rounded-sm">{"{{gem:name}}"}</code>{" "}
            to embed other gems and{" "}
            <code className="text-blue-400 bg-blue-500/10 px-1 rounded-sm">{"{variable}"}</code>{" "}
            for placeholders.
          </p>
        </div>
      </div>
      <GemForm mode="create" />
    </div>
  );
}
