// Plain words for the screen (ADR-012, roadmap item 48). The API keeps its own
// vocabulary (gem, agent, provider, run); these helpers translate it for a person
// who has never heard those words. Keep every string here a short phrase.

import { ApiError } from "@/lib/api";

/** Which AI: the provider as a person would name it. */
export function providerLabel(provider: string): string {
  switch (provider) {
    case "anthropic": return "Claude";
    case "openai": return "ChatGPT";
    case "local": return "on this PC";
    case "auto": return "decided per call";
    default: return provider;
  }
}

/** A prompt or an assistant. */
export function kindLabel(kind: string | undefined): string {
  return kind === "agent" ? "assistant" : "prompt";
}

/** How a run ended, in words. */
export function statusLabel(status: string): string {
  switch (status) {
    case "finished": return "finished";
    case "waiting_approval": return "waiting for you";
    case "failed": return "stopped with an error";
    case "max_steps": return "stopped at the step limit";
    case "running": return "running";
    default: return status;
  }
}

/** How a pipeline run stands, in words. */
export function pipelineStatusLabel(status: string): string {
  switch (status) {
    case "passed": return "passed";
    case "waiting_acceptance": return "waiting for you to accept";
    case "waiting_approval": return "waiting for an approval";
    case "failed": return "stopped with an error";
    case "max_attempts": return "gave up after the last attempt";
    case "running": return "running";
    default: return status;
  }
}

/** The error's message followed by what to do next, from the status code and the message. */
export function explain(e: unknown, fallback = "Something went wrong."): string {
  const message = e instanceof Error && e.message ? e.message : fallback;
  const status = e instanceof ApiError ? e.status : 0;
  const lower = message.toLowerCase();
  let next = "";
  if (status === 401) next = "The web UI's key does not match the backend. Set GEMS_API_KEY to the same value on both and reload.";
  else if (status === 404) next = "It may have been renamed or deleted. Go back to the library and pick it again.";
  else if (status === 409) next = "Reload the page to see its current state.";
  else if (status === 502 || lower.includes("provider")) next = "The AI did not answer. Check the key for that AI, or that the model server on this PC is running, then try again.";
  else if (status >= 500) next = "Lapidary hit a problem on its side. Try again in a moment, and look at its logs if it keeps happening.";
  else if (status === 0 && (lower.includes("fetch") || lower.includes("network") || lower.includes("load"))) next = "Lapidary is not answering. Start the backend on port 8000 and try again.";
  return next ? `${message} ${next}` : message;
}
