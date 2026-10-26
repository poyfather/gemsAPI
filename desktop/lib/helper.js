// Talks to Lapidary Helper, the Windows service that installs and updates as
// SYSTEM (desktop/helper/lapidary_helper.py), over its named pipe. One JSON
// request line goes in; progress lines {"line"} and a final {"done", "ok",
// "message"} come back. When the helper is not there (not Windows, not
// installed per machine, stopped) the caller falls back to running the
// install itself.

import { connect as netConnect } from "node:net";
import { COMPONENTS } from "./components.js";
import { TOOLBOX } from "./toolbox.js";

export const HELPER_PIPE = "\\\\.\\pipe\\LapidaryHelper";

/**
 * Send one request. Resolves with the final message, or null when the helper
 * cannot be reached. `onLine` gets each progress line. `connect` and `path`
 * are injectable for tests.
 */
export function helperRequest(request, { onLine = () => {}, path = HELPER_PIPE, connect = netConnect, timeoutMs = 30 * 60 * 1000 } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    let buffer = "";
    const finish = (value) => { if (!settled) { settled = true; clearTimeout(timer); sock.destroy(); resolve(value); } };
    const sock = connect(path);
    const timer = setTimeout(() => finish({ done: true, ok: false, message: "the helper did not answer in time" }), timeoutMs);
    sock.on("connect", () => sock.write(JSON.stringify(request) + "\n"));
    sock.on("data", (chunk) => {
      buffer += chunk.toString("utf8");
      let i;
      while ((i = buffer.indexOf("\n")) >= 0) {
        const raw = buffer.slice(0, i).trim();
        buffer = buffer.slice(i + 1);
        if (!raw) continue;
        let msg;
        try { msg = JSON.parse(raw); } catch { continue; }
        if (msg.done) return finish(msg);
        if (msg.line) onLine(msg.line);
      }
    });
    sock.on("error", () => finish(null));
    sock.on("close", () => finish(settled ? undefined : { done: true, ok: false, message: "the helper closed the connection" }));
  });
}

/** Is the helper running? Resolves with its ping answer or null. */
export async function helperPing(opts = {}) {
  const r = await helperRequest({ op: "ping" }, { ...opts, timeoutMs: 3000 });
  return r && r.ok ? r : null;
}

/**
 * Ping the helper; if it is installed but stopped, start it (signed-in users
 * may) and wait for it. Resolves with the ping answer or null. `start` runs
 * `sc start` and `ping`, `sleep` are injectable for tests.
 */
export async function ensureHelper({ ping = helperPing, start, sleep = (ms) => new Promise((r) => setTimeout(r, ms)), waitMs = 60000, stepMs = 2000 } = {}) {
  const first = await ping();
  if (first) return first;
  if (!start || !(await start())) return null;
  for (let waited = 0; waited < waitMs; waited += stepMs) {
    await sleep(stepMs);
    const r = await ping();
    if (r) return r;
  }
  return null;
}

/**
 * The helper's allowlist, built from the console's own catalog: every component
 * and toolbox entry that installs from winget or the PowerShell Gallery. CI
 * writes it next to the helper (scripts/allowlist.mjs); the helper installs
 * nothing else.
 */
export function buildAllowlist({ version, publisher = "" }) {
  const packages = {};
  for (const c of COMPONENTS) {
    if (c.install?.winget) packages[c.id] = { winget: c.install.winget };
  }
  for (const t of TOOLBOX) {
    if (t.source?.winget) packages[t.id] = { winget: t.source.winget };
    else if (t.source?.psgallery) packages[t.id] = { psgallery: t.source.psgallery };
  }
  return { console_version: version, publisher_subject: publisher, packages };
}

/** Can the helper install this id? Others (docker, pip, npm, raw commands) stay with the console. */
export function helperHandles(id) {
  return Object.hasOwn(buildAllowlist({ version: "" }).packages, id);
}

/** When the helper answered but could not do it, should the console try itself? Only when the helper lacked the means. */
export function shouldFallBack(answer) {
  return !answer || /not on the helper's allowlist|winget was not found/.test(answer.message || "");
}
