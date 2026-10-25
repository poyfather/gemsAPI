"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { gems as gemsApi, chat as chatApi, agents as agentsApi, runs as runsApi, Gem, ChatMessage, AvailableModels, RunEvent, errorMessage } from "@/lib/api";
import RunEvents from "@/components/RunEvents";
import Link from "next/link";
import {
  Send, Loader2, Gem as GemIcon, Variable, ChevronDown,
  RotateCcw, MessageSquare, Settings, Bot
} from "lucide-react";
import clsx from "clsx";

interface Message extends ChatMessage {
  id: string;
  loading?: boolean;
  /** Agent runs: the events streamed so far, and the run id once known. */
  events?: RunEvent[];
  runId?: string;
}

function ChatPageInner() {
  const searchParams = useSearchParams();
  const initialGem   = searchParams.get("gem") || "";

  const [allGems, setAllGems]       = useState<Gem[]>([]);
  const [selectedGem, setSelectedGem] = useState<string>(initialGem);
  const [messages, setMessages]     = useState<Message[]>([]);
  const [input, setInput]           = useState("");
  const [sending, setSending]       = useState(false);
  const [varValues, setVarValues]   = useState<Record<string, string>>({});
  const [models, setModels]         = useState<AvailableModels>({});
  const [modelOverride, setModelOverride] = useState("");
  const [providerOverride, setProviderOverride] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [allowRisky, setAllowRisky] = useState(false);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  // Approve or deny the risky call a run in the conversation is waiting on, streaming the rest into its bubble.
  const decide = async (msgId: string, runId: string, approve: boolean) => {
    setDecidingId(msgId);
    const patchMsg = (update: (m: Message) => Partial<Message>) =>
      setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, ...update(m) } : m)));
    try {
      await runsApi.approve(runId, approve, (event) => {
        patchMsg((m) => {
          const next: Partial<Message> = { events: [...(m.events ?? []), event] };
          if (event.type === "model_turn" && typeof event.data.text === "string" && event.data.text) next.content = event.data.text;
          if (event.type === "run_failed") next.content = `Run failed: ${String(event.data.error)}`;
          return next;
        });
      });
    } catch (err) {
      patchMsg((m) => ({ content: `${m.content}\n\nError: ${errorMessage(err)}` }));
    } finally {
      setDecidingId(null);
    }
  };

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);

  const currentGem = allGems.find((g) => g.name === selectedGem);
  const isAgent = currentGem?.kind === "agent";

  // Load gems and models on mount
  useEffect(() => {
    const load = async () => {
      try {
        const [gemList, modelList] = await Promise.all([
          gemsApi.list(),
          chatApi.models(),
        ]);
        setAllGems(gemList);
        setModels(modelList);
        if (!initialGem && gemList.length > 0) {
          setSelectedGem(gemList[0].name);
        }
      } catch (e) {
        console.error("Failed to load data", e);
      }
    };
    load();
  }, [initialGem]);

  // Reset vars when gem changes
  useEffect(() => {
    setVarValues({});
  }, [selectedGem]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !selectedGem || sending) return;

    const userMsg: Message = {
      id:      crypto.randomUUID(),
      role:    "user",
      content: input.trim(),
    };
    const loadingMsg: Message = {
      id:      crypto.randomUUID(),
      role:    "assistant",
      content: "",
      loading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput("");
    setSending(true);

    // Build history (exclude loading placeholder)
    const history: ChatMessage[] = messages.map(({ role, content }) => ({ role, content }));
    history.push({ role: "user", content: userMsg.content });

    const patch = (update: Partial<Message> | ((m: Message) => Partial<Message>)) =>
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingMsg.id ? { ...m, ...(typeof update === "function" ? update(m) : update) } : m))
      );

    try {
      if (isAgent) {
        // Agent gem: one run per message, events as they happen (ADR-007).
        await agentsApi.stream(
          selectedGem,
          {
            message:           userMsg.content,
            variables:         varValues,
            model_override:    modelOverride || undefined,
            provider_override: providerOverride || undefined,
            allow_risky:       allowRisky,
          },
          (event) => {
            patch((m) => {
              const events = [...(m.events ?? []), event];
              const next: Partial<Message> = { events, loading: false };
              if (event.type === "run_started" && typeof event.data.run_id === "string") next.runId = event.data.run_id;
              if (event.type === "model_turn" && typeof event.data.text === "string" && event.data.text) next.content = event.data.text;
              if (event.type === "run_failed") next.content = `Run failed: ${String(event.data.error)}`;
              if (event.type === "approval_requested" && !m.content) next.content = "Paused: waiting for your decision on a risky tool call.";
              return next;
            });
          }
        );
      } else {
        // Prompt gem: stream the reply token by token (roadmap item 13).
        let streamed = "";
        await chatApi.stream(
          {
            gem_name:          selectedGem,
            messages:          history,
            variables:         varValues,
            model_override:    modelOverride || undefined,
            provider_override: providerOverride || undefined,
          },
          (chunk) => {
            streamed += chunk;
            patch({ content: streamed, loading: false });
          }
        );
        if (!streamed) patch({ content: "", loading: false });
      }
    } catch (err) {
      patch((m) => ({ content: m.content ? `${m.content}\n\nError: ${errorMessage(err)}` : `Error: ${errorMessage(err)}`, loading: false }));
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClear = () => {
    if (messages.length === 0 || confirm("Clear the conversation?")) {
      setMessages([]);
    }
  };

  const availableModels =
    providerOverride
      ? models[providerOverride] || []
      : currentGem
        ? models[currentGem.provider] || []
        : [];

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem-4rem)] max-h-[900px]">
      <div className="flex flex-1 gap-4 min-h-0">

        {/* ── Left panel: gem selector + settings ── */}
        <div className="w-72 shrink-0 flex flex-col gap-4">

          {/* Gem selector */}
          <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-3">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <GemIcon className="w-3.5 h-3.5 text-violet-400" />
              Active Gem
            </label>
            <div className="relative">
              <select
                value={selectedGem}
                onChange={(e) => setSelectedGem(e.target.value)}
                className="w-full pl-3 pr-8 py-2 rounded-lg bg-gem-surface border border-gem-border text-slate-200 text-sm appearance-none focus:outline-hidden focus:ring-2 focus:ring-violet-500"
              >
                <option value="" disabled>Select a gem…</option>
                {allGems.map((g) => (
                  <option key={g.id} value={g.name}>{g.name}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
            </div>
            {currentGem?.description && (
              <p className="text-xs text-slate-500 leading-relaxed">{currentGem.description}</p>
            )}
            {isAgent && (
              <div className="pt-2 border-t border-gem-border space-y-2">
                <p className="text-xs text-violet-300 flex items-center gap-1.5">
                  <Bot className="w-3.5 h-3.5" />
                  Agent, tools: <span className="font-mono text-slate-400">{(currentGem?.tools ?? []).join(", ") || "none"}</span>
                </p>
                <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
                  <input type="checkbox" checked={allowRisky} onChange={(e) => setAllowRisky(e.target.checked)} className="accent-violet-500" />
                  Allow risky tools in this run
                </label>
                <p className="text-xs text-slate-600">Each message starts a fresh run; earlier messages are not sent along.</p>
              </div>
            )}
          </div>

          {/* Variable inputs */}
          {currentGem && currentGem.variables.length > 0 && (
            <div className="bg-gem-card border border-gem-border rounded-xl p-4 space-y-3">
              <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Variable className="w-3.5 h-3.5 text-blue-400" />
                Variables
              </label>
              {currentGem.variables.map((v) => (
                <div key={v} className="space-y-1">
                  <label className="text-xs text-blue-400 font-mono">{"{" + v + "}"}</label>
                  <input
                    type="text"
                    placeholder={`Value for ${v}`}
                    value={varValues[v] ?? ""}
                    onChange={(e) => setVarValues((p) => ({ ...p, [v]: e.target.value }))}
                    className="w-full px-2.5 py-1.5 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs placeholder:text-slate-600 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              ))}
            </div>
          )}

          {/* Model override (collapsible) */}
          <div className="bg-gem-card border border-gem-border rounded-xl overflow-hidden">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-gem-hover transition-colors"
            >
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Settings className="w-3.5 h-3.5" />
                Model Override
              </span>
              <ChevronDown className={clsx("w-4 h-4 text-slate-500 transition-transform", showSettings && "rotate-180")} />
            </button>
            {showSettings && (
              <div className="px-4 pb-4 space-y-3 border-t border-gem-border pt-3">
                <div>
                  <label className="text-xs text-slate-500 mb-1 block">Provider</label>
                  <select
                    value={providerOverride}
                    onChange={(e) => { setProviderOverride(e.target.value); setModelOverride(""); }}
                    className="w-full px-2.5 py-1.5 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs focus:outline-hidden focus:ring-1 focus:ring-violet-500"
                  >
                    <option value="">Use gem default</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="openai">OpenAI</option>
                  </select>
                </div>
                {availableModels.length > 0 && (
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Model</label>
                    <select
                      value={modelOverride}
                      onChange={(e) => setModelOverride(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-md bg-gem-surface border border-gem-border text-slate-300 text-xs focus:outline-hidden focus:ring-1 focus:ring-violet-500"
                    >
                      <option value="">Use gem default</option>
                      {availableModels.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Clear button */}
          <button
            onClick={handleClear}
            className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gem-card border border-gem-border text-slate-400 hover:text-slate-200 hover:bg-gem-hover text-sm transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Clear Conversation
          </button>
        </div>

        {/* ── Right panel: chat ── */}
        <div className="flex-1 flex flex-col min-w-0 bg-gem-card border border-gem-border rounded-xl overflow-hidden">

          {/* Chat header */}
          <div className="px-4 py-3 border-b border-gem-border flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-violet-400" />
            <span className="text-sm font-medium text-slate-300">
              {selectedGem
                ? <>{isAgent ? "Running" : "Testing"} <span className="font-mono text-violet-300">{selectedGem}</span></>
                : "Select a gem to start chatting"
              }
            </span>
            {currentGem && (
              <span className={clsx(
                "ml-auto px-2 py-0.5 rounded-md text-xs",
                currentGem.provider === "anthropic"
                  ? "bg-orange-500/10 text-orange-400"
                  : "bg-emerald-500/10 text-emerald-400"
              )}>
                {modelOverride || currentGem.model}
              </span>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-3 text-slate-600">
                <MessageSquare className="w-10 h-10" />
                <div>
                  <p className="text-sm">No messages yet.</p>
                  <p className="text-xs mt-1">
                    {selectedGem
                      ? `Send a message to test the "${selectedGem}" gem.`
                      : "Select a gem from the left panel to get started."}
                  </p>
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={clsx(
                    "flex slide-in",
                    msg.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  <div
                    className={clsx(
                      "max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed",
                      msg.role === "user"
                        ? "bg-violet-600 text-white rounded-br-sm"
                        : "bg-gem-surface border border-gem-border text-slate-200 rounded-bl-sm"
                    )}
                  >
                    {msg.loading ? (
                      <span className="flex items-center gap-2 text-slate-400">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Thinking…
                      </span>
                    ) : (
                      <>
                        {msg.events && msg.events.length > 0 && (
                          <div className="mb-3 pb-3 border-b border-gem-border">
                            <RunEvents
                              events={msg.events}
                              hideFinalText
                              onDecide={msg.runId ? (approve) => decide(msg.id, msg.runId as string, approve) : undefined}
                              deciding={decidingId === msg.id}
                            />
                          </div>
                        )}
                        <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
                        {msg.runId && (
                          <Link href={`/runs/${msg.runId}`} className="block mt-2 text-xs text-violet-400 hover:text-violet-300 underline">
                            Open run {msg.runId.slice(0, 8)}
                          </Link>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input area */}
          <div className="p-4 border-t border-gem-border">
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                rows={1}
                placeholder={
                  selectedGem
                    ? "Type a message… (Enter to send, Shift+Enter for newline)"
                    : "Select a gem first…"
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={!selectedGem || sending}
                className="flex-1 px-3 py-2.5 rounded-xl bg-gem-surface border border-gem-border text-slate-100 text-sm placeholder:text-slate-600 focus:outline-hidden focus:ring-2 focus:ring-violet-500 resize-none disabled:opacity-50 transition max-h-40 overflow-y-auto"
                style={{ height: "auto" }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = Math.min(el.scrollHeight, 160) + "px";
                }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || !selectedGem || sending}
                className="p-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white transition-colors shrink-0"
              >
                {sending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// useSearchParams() needs a Suspense boundary so the page can be prerendered.
export default function ChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatPageInner />
    </Suspense>
  );
}
