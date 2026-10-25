"use client";

import { useState } from "react";
import { RunEvent } from "@/lib/api";
import { providerLabel, statusLabel } from "@/lib/words";
import { Wrench, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, Flag, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import clsx from "clsx";

interface RunEventsProps {
  events: RunEvent[];
  /** Hide the final model text (the chat bubble shows it itself). */
  hideFinalText?: boolean;
  /** When set, an undecided approval_requested event shows Approve and Deny buttons that call this. */
  onDecide?: (approve: boolean) => void;
  /** Disable the buttons while a decision is being sent. */
  deciding?: boolean;
}

function asString(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/** One tool result, collapsed by default because outputs can be long. */
function ToolResult({ event }: { event: RunEvent }) {
  const [open, setOpen] = useState(false);
  const isError = Boolean(event.data.is_error);
  const output = asString(event.data.output);
  return (
    <div className={clsx("rounded-lg border text-xs", isError ? "border-red-500/30 bg-red-500/5" : "border-gem-border bg-gem-surface")}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5 text-slate-500" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-500" />}
        {isError ? <AlertTriangle className="w-3.5 h-3.5 text-red-400" /> : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
        <span className="font-mono text-slate-300">{String(event.data.name)}</span>
        <span className="text-slate-500">{isError ? "the tool reported an error" : `${output.length} characters`}</span>
      </button>
      {open && (
        <pre className="px-3 pb-3 whitespace-pre-wrap font-mono text-slate-400 max-h-64 overflow-y-auto">{output}</pre>
      )}
    </div>
  );
}

/** The timeline of a run: model turns, tool calls and results, and how it ended. */
export default function RunEvents({ events, hideFinalText = false, onDecide, deciding = false }: RunEventsProps) {
  const lastTurnSeq = [...events].reverse().find((e) => e.type === "model_turn")?.seq;
  // The request is open when no later approval_decided event exists for the same call id.
  const decidedIds = new Set(events.filter((e) => e.type === "approval_decided").map((e) => String(e.data.id)));
  return (
    <div className="space-y-2">
      {events.map((e) => {
        switch (e.type) {
          case "run_started":
            return (
              <div key={e.seq} className="text-xs text-slate-500 flex items-center gap-2">
                <Flag className="w-3.5 h-3.5" />
                Started on {providerLabel(String(e.data.provider))} ({String(e.data.model)})
                {Array.isArray(e.data.tools) && e.data.tools.length > 0 && (
                  <span>with {e.data.tools.length} tool{e.data.tools.length !== 1 ? "s" : ""}</span>
                )}
                {Array.isArray(e.data.unknown_tools) && e.data.unknown_tools.length > 0 && (
                  <span className="text-amber-400">tools it cannot find: {e.data.unknown_tools.join(", ")}</span>
                )}
              </div>
            );
          case "model_turn": {
            const text = String(e.data.text ?? "");
            const calls = Array.isArray(e.data.tool_calls) ? e.data.tool_calls : [];
            const isFinal = e.seq === lastTurnSeq && calls.length === 0;
            if (!text || (hideFinalText && isFinal)) return null;
            return (
              <div key={e.seq} className="text-xs text-slate-400 border-l-2 border-gem-border pl-3">
                <span className="text-slate-600">step {String(e.data.step)}</span>
                <pre className="whitespace-pre-wrap font-sans text-slate-300 mt-0.5">{text}</pre>
              </div>
            );
          }
          case "tool_call":
            return (
              <div key={e.seq} className="flex items-start gap-2 text-xs text-slate-400">
                <Wrench className="w-3.5 h-3.5 text-violet-400 mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <span className="font-mono text-violet-300">{String(e.data.name)}</span>
                  <pre className="whitespace-pre-wrap font-mono text-slate-500 mt-0.5">{asString(e.data.input)}</pre>
                </div>
              </div>
            );
          case "tool_result":
            return <ToolResult key={e.seq} event={e} />;
          case "approval_requested": {
            const open = !decidedIds.has(String(e.data.id));
            return (
              <div key={e.seq} className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs space-y-2">
                <div className="flex items-center gap-2 text-amber-300">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  Wants to use <span className="font-mono">{String(e.data.name)}</span>, which can change things
                </div>
                <pre className="whitespace-pre-wrap font-mono text-slate-500">{asString(e.data.input)}</pre>
                {open && onDecide && (
                  <div className="flex gap-2">
                    <button type="button" disabled={deciding} onClick={() => onDecide(true)}
                      className="px-2.5 py-1 rounded-md bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 disabled:opacity-50">
                      Approve
                    </button>
                    <button type="button" disabled={deciding} onClick={() => onDecide(false)}
                      className="px-2.5 py-1 rounded-md bg-red-500/10 hover:bg-red-500/20 text-red-400 disabled:opacity-50">
                      Deny
                    </button>
                  </div>
                )}
                {open && !onDecide && <p className="text-slate-500">Waiting for Approve or Deny.</p>}
              </div>
            );
          }
          case "approval_decided":
            return (
              <div key={e.seq} className={clsx("text-xs flex items-center gap-2", e.data.approved ? "text-emerald-400" : "text-red-400")}>
                {e.data.approved ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldX className="w-3.5 h-3.5" />}
                {e.data.approved ? "Approved" : "Denied"} <span className="font-mono">{String(e.data.name)}</span>
              </div>
            );
          case "run_finished":
            return (
              <div key={e.seq} className="text-xs text-slate-500 flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                {statusLabel(String(e.data.status))} after {String(e.data.steps)} step{Number(e.data.steps) !== 1 ? "s" : ""},
                {" "}{Number(e.data.input_tokens) + Number(e.data.output_tokens)} tokens
              </div>
            );
          case "run_failed":
            return (
              <div key={e.seq} className="text-xs text-red-400 flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5" />
                Stopped at step {String(e.data.step)}: {String(e.data.error)}
              </div>
            );
          default:
            return (
              <div key={e.seq} className="text-xs text-slate-600">{e.type}</div>
            );
        }
      })}
    </div>
  );
}
