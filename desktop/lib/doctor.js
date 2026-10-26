// The Doctor (ADR-012, roadmap item 49): looks at what the console can see about
// this machine and says, in plain words, what is wrong and what one click would
// fix it. Pure: main.js gathers the facts, this file turns them into findings.
//
// A finding is { id, title, state, detail, fix? }:
//   state  ok | warn | fail | skip
//   detail one or two sentences a newcomer can act on
//   fix    { action, label }, where action is a step the runner understands
//          (restart, install:<id>, start:ollama, pull:<model>, connect:<app>,
//          policy:<id>, open:<url>, view:<name>)

import { DEFAULT_LOCAL_MODEL } from "./recipes.js";

const PORTS = { lapidary: 8000, ui: 3000, openwebui: 3080, ollama: 11434 };

/**
 * facts:
 *   status        detectAll's result (components, with ollama.models)
 *   settings      console settings with keys as "set" or ""
 *   keys          { anthropic: "ok"|"invalid"|"offline"|null, openai: ... } from a live probe
 *   ports         { 8000: "lapidary"|"other"|"free", 3000, 3080, 11434 } from a connect probe
 *   clients       { claude: { exists, connected }, chatgpt: { exists, connected } } from reading the config files
 *   composeExists Open WebUI compose file written by the console
 *   version       the console's own version; latest: the newest release, or null when offline
 *   helper        on Windows: { running } for Lapidary Helper, the install and update service; elsewhere undefined
 */
export function diagnose(facts) {
  const { status = {}, settings = {}, keys = {}, ports = {}, clients = {}, composeExists = false, version = "", latest = null, helper } = facts;
  const st = (id) => status[id] || {};
  const policy = settings.modelPolicy || "auto";
  const localModel = settings.localModel || DEFAULT_LOCAL_MODEL;
  const hasKey = settings.anthropicKey === "set" || settings.openaiKey === "set";
  const out = [];
  const add = (f) => out.push(f);

  // 1. Lapidary itself
  if (st("lapidary").running) add({ id: "lapidary", title: "Lapidary is running", state: "ok", detail: `Answering on port ${PORTS.lapidary}.` });
  else if (ports[PORTS.lapidary] === "other") add({ id: "lapidary", title: "Another program is using Lapidary's port", state: "fail", detail: `Something else answers on port ${PORTS.lapidary}, so Lapidary cannot start. Close that program, then restart Lapidary.`, fix: { action: "restart", label: "Restart Lapidary" } });
  else add({ id: "lapidary", title: "Lapidary is not running", state: "fail", detail: "Your prompts and assistants are unavailable until it starts. Logs shows why it stopped.", fix: { action: "restart", label: "Restart Lapidary" } });

  if (ports[PORTS.ui] === "lapidary") add({ id: "ui", title: "The Lapidary web UI is running", state: "ok", detail: `Answering on port ${PORTS.ui}.` });
  else if (ports[PORTS.ui] === "other") add({ id: "ui", title: "Another program is using the web UI's port", state: "fail", detail: `Something else answers on port ${PORTS.ui}. Close it, then restart Lapidary.`, fix: { action: "restart", label: "Restart Lapidary" } });
  else add({ id: "ui", title: "The Lapidary web UI is not running", state: "fail", detail: "The Lapidary view and the chat will be empty until it starts.", fix: { action: "restart", label: "Restart Lapidary" } });

  // 2. Which AI, and whether that choice can work right now
  const ollama = st("ollama");
  const models = ollama.models || [];
  const localReady = Boolean(ollama.running && models.length > 0);
  const needsLocal = policy === "local" || policy === "mix";
  const needsKey = policy === "online" || policy === "mix";
  if (needsLocal && !ollama.installed) add({ id: "ai-local", title: "Your AI choice needs Ollama, which is not installed", state: "fail", detail: "The free AI on this PC runs through Ollama. Install it, or pick another answer to \"Which AI should we use?\" in Settings.", fix: { action: "install:ollama", label: "Install Ollama" } });
  else if (needsLocal && !ollama.running) add({ id: "ai-local", title: "Ollama is installed but not running", state: "fail", detail: "Nothing on this PC can answer until it starts.", fix: { action: "start:ollama", label: "Start Ollama" } });
  else if (needsLocal && models.length === 0) add({ id: "ai-local", title: "Ollama has no model yet", state: "fail", detail: `It is running but has nothing to answer with. Download ${localModel} (a few GB, once).`, fix: { action: `pull:${localModel}`, label: "Download a model" } });
  else if (needsLocal) add({ id: "ai-local", title: "The free AI on this PC is ready", state: "ok", detail: `Ollama is running with ${models.length} model${models.length === 1 ? "" : "s"}: ${models.slice(0, 4).join(", ")}${models.length > 4 ? ", ..." : ""}.` });
  else if (ollama.installed && !ollama.running) add({ id: "ai-local", title: "Ollama is installed but not running", state: "warn", detail: "Your AI choice does not need it right now, so this is fine. Start it if you want the free one available.", fix: { action: "start:ollama", label: "Start Ollama" } });
  else if (localReady) add({ id: "ai-local", title: "The free AI on this PC is available", state: "ok", detail: `Ollama is running with ${models.length} model${models.length === 1 ? "" : "s"}.` });
  else add({ id: "ai-local", title: "No AI on this PC", state: "skip", detail: "Your AI choice does not need one. Install Ollama from Components if you want a free, private option." });

  if (needsKey && !hasKey) add({ id: "ai-key", title: "Your AI choice needs a cloud key, and none is saved", state: "fail", detail: "The online AIs (Claude, ChatGPT) need a key from your own account, paid by use. Add one in Settings, or choose the free one on this PC.", fix: { action: "view:settings", label: "Open Settings" } });
  else if (!hasKey) add({ id: "ai-key", title: "No cloud key saved", state: policy === "auto" && !localReady ? "fail" : "skip", detail: policy === "auto" && !localReady ? "\"Decide for me\" has nothing to pick from: no key and no model on this PC. Add a key in Settings or install Ollama and download a model." : "Everything runs on this PC. Add a key in Settings if you want the online AIs.", fix: policy === "auto" && !localReady ? { action: "view:settings", label: "Open Settings" } : undefined });
  for (const [provider, name] of [["anthropic", "Anthropic (Claude)"], ["openai", "OpenAI (ChatGPT)"]]) {
    const saved = settings[`${provider}Key`] === "set";
    if (!saved) continue;
    const probe = keys[provider];
    if (probe === "ok") add({ id: `key-${provider}`, title: `The ${name} key works`, state: "ok", detail: "The service accepted it." });
    else if (probe === "invalid") add({ id: `key-${provider}`, title: `The ${name} key was refused`, state: "fail", detail: "The service does not accept it. It may be mistyped, revoked or out of credit. Paste a fresh one in Settings.", fix: { action: "view:settings", label: "Open Settings" } });
    else add({ id: `key-${provider}`, title: `The ${name} key could not be checked`, state: "skip", detail: "The service did not answer; this PC may be offline. Try again later." });
  }
  if (policy === "manual" && !hasKey && !localReady) add({ id: "ai-manual", title: "\"I'll choose each time\" has nothing to choose from", state: "warn", detail: "No key and no model on this PC. Prompts set to Claude or ChatGPT will fail until a key is added." });

  // 3. The private chat (Open WebUI) and Docker
  const docker = st("docker");
  const webui = st("openwebui");
  if (webui.running) add({ id: "openwebui", title: "The private chat (Open WebUI) is running", state: "ok", detail: `Open it at http://localhost:${PORTS.openwebui}.`, fix: { action: `open:http://localhost:${PORTS.openwebui}`, label: "Open it" } });
  else if (composeExists && !docker.installed) add({ id: "openwebui", title: "The private chat needs Docker Desktop, which is missing", state: "fail", detail: "Open WebUI runs inside Docker. Install Docker Desktop, start it, then start the chat from Connections.", fix: { action: "install:docker", label: "Install Docker Desktop" } });
  else if (composeExists && docker.installed && !docker.version) add({ id: "openwebui", title: "Docker Desktop is installed but not running", state: "fail", detail: "Open Docker Desktop and wait until it says running, then start the chat from Connections.", fix: { action: "open:docker", label: "Open Docker Desktop" } });
  else if (composeExists && ports[PORTS.openwebui] === "other") add({ id: "openwebui", title: "Another program is using the private chat's port", state: "fail", detail: `Something else answers on port ${PORTS.openwebui}. Close it, then start the chat again.`, fix: { action: "connect:openwebui", label: "Start the chat" } });
  else if (composeExists) add({ id: "openwebui", title: "The private chat is set up but not running", state: "warn", detail: "Start it from here; the first start takes a minute.", fix: { action: "connect:openwebui", label: "Start the chat" } });
  else add({ id: "openwebui", title: "No private chat yet", state: "skip", detail: "Pick \"A private chat on this PC\" on Start to set one up." });

  // 4. Connections to the apps
  for (const [id, name] of [["claude", "Claude Desktop"], ["chatgpt", "ChatGPT"]]) {
    const app = st(id);
    const c = clients[id] || {};
    if (!app.installed) { add({ id: `connect-${id}`, title: `${name} is not installed`, state: "skip", detail: `Install it from Components if you want your prompts inside ${name}.` }); continue; }
    if (c.connected) add({ id: `connect-${id}`, title: `${name} is connected`, state: "ok", detail: "Lapidary and REA are in its config. Restart the app if it does not show them yet." });
    else if (c.broken) add({ id: `connect-${id}`, title: `${name}'s config file is damaged`, state: "fail", detail: `${name} will not read it. Open the file with Advanced on in Connections and fix the JSON, or let Connect rewrite it after you move the file aside.` });
    else add({ id: `connect-${id}`, title: `${name} is installed but not connected`, state: "warn", detail: `One click adds your prompts and assistants to ${name}.`, fix: { action: `connect:${id}`, label: `Connect ${name}` } });
  }

  // 5. Tools the assistants rely on
  const pwsh = st("pwsh");
  if (pwsh.installed) add({ id: "pwsh", title: "PowerShell 7 is installed", state: "ok", detail: `Version ${pwsh.version || "unknown"}.` });
  else add({ id: "pwsh", title: "PowerShell 7 is missing", state: "warn", detail: "Windows PowerShell 5 is used instead; some modern commands will not work.", fix: { action: "install:pwsh", label: "Install PowerShell 7" } });

  // 6. Versions, and the helper that installs and updates without administrator prompts
  const canUpdate = helper?.running;
  if (latest && version && latest !== version) add({ id: "version", title: `A newer Lapidary Console is available (${latest}, you have ${version})`, state: "warn", detail: canUpdate ? "Update now installs it in the background; the console closes and reopens, and your settings are kept." : "Download the new installer from the releases page; your settings are kept.", fix: canUpdate ? { action: "update:console", label: "Update now" } : { action: "open:https://github.com/poyfather/lapidary/releases/latest", label: "Open releases" } });
  else if (latest) add({ id: "version", title: `Lapidary Console is up to date (${version})`, state: "ok", detail: "Components update from their publishers through the Components view." });
  else add({ id: "version", title: "Could not check for a newer console", state: "skip", detail: "This PC may be offline. Components still update from the Components view." });

  if (helper?.running) add({ id: "helper", title: "Lapidary Helper is running", state: "ok", detail: "Installs and updates happen without asking for administrator rights." });
  else if (helper) add({ id: "helper", title: "Lapidary Helper is not running", state: "warn", detail: "Installs will ask for administrator rights each time. Restart the PC; if it stays off, reinstall Lapidary Console.", fix: { action: "open:https://github.com/poyfather/lapidary/releases/latest", label: "Get the installer" } });

  return out;
}

/** One line for the dashboard: what the doctor found. */
export function summarise(findings) {
  const fails = findings.filter((f) => f.state === "fail").length;
  const warns = findings.filter((f) => f.state === "warn").length;
  if (fails === 0 && warns === 0) return "everything looks fine";
  const parts = [];
  if (fails) parts.push(`${fails} thing${fails === 1 ? "" : "s"} to fix`);
  if (warns) parts.push(`${warns} suggestion${warns === 1 ? "" : "s"}`);
  return parts.join(", ");
}

/** Read a Claude Desktop or ChatGPT config: does it exist, is it valid, does it name lapidary? */
export function readClientConfig(text) {
  if (text === null || text === undefined) return { exists: false, connected: false, broken: false };
  try {
    const doc = JSON.parse(text);
    return { exists: true, connected: Boolean(doc && doc.mcpServers && doc.mcpServers.lapidary), broken: false };
  } catch {
    return { exists: true, connected: false, broken: true };
  }
}

export { PORTS };
