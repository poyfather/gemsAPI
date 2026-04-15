"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { gems as gemsApi, Gem } from "@/lib/api";
import GemForm from "@/components/GemForm";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

export default function EditGemPage() {
  const { id } = useParams<{ id: string }>();
  const [gem, setGem]     = useState<Gem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await gemsApi.get(id);
        setGem(data);
      } catch (e: any) {
        setError(e.message || "Gem not found.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading gem...
      </div>
    );
  }

  if (error || !gem) {
    return (
      <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
        {error || "Gem not found."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href={`/gems/${id}`}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-gem-hover transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white">
            Edit <span className="font-mono text-violet-300">{gem.name}</span>
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">Name cannot be changed after creation.</p>
        </div>
      </div>
      <GemForm mode="edit" initialGem={gem} />
    </div>
  );
}
