// Lapidary Console, Electron main process.
// Privileged work lives here: detection, installs, config files, keys, sidecars, logs.
// The renderer only ever talks to it through the IPC surface in preload.js.

import { app, BrowserWindow, ipcMain, safeStorage, shell } from "electron";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { COMPONENTS, detectAll, installCommand, paths } from "./lib/components.js";
import { backendEnv, lapidaryMcpEntries, lapidaryMcpServersFile, mergeMcpServers, openWebUICompose } from "./lib/configs.js";
import { Sidecar, waitForHealth } from "./lib/sidecars.js";
import { capOutput, pwshInvocation } from "./lib/pwsh.js";
import { TOOLBOX, detectToolbox, toolboxInstallCommand, toolboxSourceLabel } from "./lib/toolbox.js";
import { AI_CHOICES, DEFAULT_LOCAL_MODEL, advancedPlan, plan, planAll, summarise } from "./lib/recipes.js";
import { PORTS, diagnose, readClientConfig, summarise as doctorSummary } from "./lib/doctor.js";
import { connect as netConnect } from "node:net";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const P = paths(process.env, process.platform);
const dataDir = P.consoleData;
const settingsFile = join(dataDir, "settings.bin");
const logLines = [];
const log = (line) => { logLines.push(`${new Date().toISOString().slice(11, 19)} ${String(line).trimEnd()}`); if (logLines.length > 2000) logLines.shift(); };

let win = null;
let backend = null;
let frontend = null;

// ---- settings (keys) with safeStorage: DPAPI on Windows, Keychain on macOS
function loadSettings() {
  try {
    if (!existsSync(settingsFile)) return {};
    const raw = readFileSync(settingsFile);
    const text = safeStorage.isEncryptionAvailable() ? safeStorage.decryptString(raw) : raw.toString("utf8");
    return JSON.parse(text);
  } catch (e) { log(`settings unreadable: ${e.message}`); return {}; }
}
function saveSettings(s) {
  mkdirSync(dataDir, { recursive: true });
  const text = JSON.stringify(s);
  writeFileSync(settingsFile, safeStorage.isEncryptionAvailable() ? safeStorage.encryptString(text) : Buffer.from(text, "utf8"));
}

// ---- resources: where CI put the backend exe and the standalone UI
function resources() {
  const base = app.isPackaged ? process.resourcesPath : join(here, "..", "build");
  return {
    backendExe: join(base, "backend", process.platform === "win32" ? "lapidary-backend.exe" : "lapidary-backend"),
    frontendServer: join(base, "frontend", "server.js"),
    mcpServersFile: join(dataDir, "mcp_servers.json"),
  };
}

async function startSidecars() {
  const r = resources();
  const settings = loadSettings();
  mkdirSync(dataDir, { recursive: true });
  if (!existsSync(r.mcpServersFile)) writeFileSync(r.mcpServersFile, lapidaryMcpServersFile({}));
  if (!settings.gemsApiKey) { settings.gemsApiKey = cryptoRandom(); saveSettings(settings); }
  backend = new Sidecar("backend", { program: r.backendExe, env: backendEnv(settings, { dataDir, mcpServersFile: r.mcpServersFile }), healthUrl: "http://127.0.0.1:8000/health", log });
  frontend = new Sidecar("ui", {
    program: process.execPath, args: [r.frontendServer],
    env: { ELECTRON_RUN_AS_NODE: "1", PORT: "3000", HOSTNAME: "127.0.0.1", BACKEND_URL: "http://127.0.0.1:8000", GEMS_API_KEY: settings.gemsApiKey },
    healthUrl: "http://127.0.0.1:3000", log,
  });
  if (existsSync(r.backendExe)) backend.start(); else log(`backend not found at ${r.backendExe} (dev mode: start it yourself)`);
  if (existsSync(r.frontendServer)) frontend.start(); else log(`ui not found at ${r.frontendServer} (dev mode: run next dev)`);
  await waitForHealth("http://127.0.0.1:8000/health", { timeoutMs: 30000 });
}

function cryptoRandom() {
  return require("node:crypto").randomBytes(32).toString("base64url");
}

// ---- side-effect adapters for detection
const io = {
  which: async (cmd) => new Promise((resolve) => {
    const p = spawn(process.platform === "win32" ? "where" : "which", [cmd], { windowsHide: true });
    let out = ""; p.stdout.on("data", (d) => (out += d)); p.on("close", (code) => resolve(code === 0 ? out.split(/\r?\n/)[0].trim() : null)); p.on("error", () => resolve(null));
  }),
  exists: async (path) => existsSync(path),
  version: async (cmd, args) => new Promise((resolve) => {
    const p = spawn(cmd, args, { windowsHide: true });
    let out = ""; p.stdout.on("data", (d) => (out += d)); p.on("close", () => resolve(out.trim().split(/\r?\n/)[0] || null)); p.on("error", () => resolve(null));
  }),
  fetchOk: async (url) => { try { const r = await fetch(url, { signal: AbortSignal.timeout(1500) }); return r.ok; } catch { return false; } },
  fetchJson: async (url) => { try { const r = await fetch(url, { signal: AbortSignal.timeout(1500) }); return r.ok ? await r.json() : null; } catch { return null; } },
};

function runCommand(program, args) {
  return new Promise((resolve) => {
    log(`$ ${program} ${args.join(" ")}`);
    const p = spawn(program, args, { windowsHide: true, shell: process.platform === "win32" });
    p.stdout.on("data", (d) => log(d)); p.stderr.on("data", (d) => log(d));
    p.on("close", (code) => resolve(code)); p.on("error", (e) => { log(e.message); resolve(-1); });
  });
}

// ---- IPC surface
ipcMain.handle("console:components", async () => ({ components: COMPONENTS.map(({ id, name, kind, blurb }) => ({ id, name, kind, blurb })), status: await detectAll(io) }));
ipcMain.handle("console:toolbox", async () => ({ tools: TOOLBOX.map((t) => ({ id: t.id, name: t.name, publisher: t.publisher, category: t.category, source: toolboxSourceLabel(t), homepage: t.homepage })), status: await detectToolbox(io) }));
ipcMain.handle("console:install", async (_e, id) => {
  const cmd = installCommand(id) || toolboxInstallCommand(id, { pwshPath: (await io.which("pwsh")) || "powershell.exe" });
  if (!cmd) return { ok: false, message: "this one has nothing to install; it is built in or detected only" };
  const code = await runCommand(cmd.program, cmd.args);
  return { ok: code === 0, message: code === 0 ? "installed" : `the installer stopped with code ${code}; open Logs to see why, then try again` };
});
ipcMain.handle("console:settings:get", async () => { const s = loadSettings(); return { modelPolicy: "auto", localModel: DEFAULT_LOCAL_MODEL, ...s, anthropicKey: s.anthropicKey ? "set" : "", openaiKey: s.openaiKey ? "set" : "", supabaseKey: s.supabaseKey ? "set" : "" }; });
ipcMain.handle("console:settings:set", async (_e, patch) => {
  const s = loadSettings();
  for (const [k, v] of Object.entries(patch)) if (typeof v === "string" && v !== "set") s[k] = v;
  saveSettings(s);
  return { ok: true, note: "saved; press Restart Lapidary on the Dashboard so the new settings are used" };
});
ipcMain.handle("console:connect:claude", async () => writeMcp(P.claudeConfig));
ipcMain.handle("console:connect:chatgpt", async () => writeMcp(P.chatgptConfig));
ipcMain.handle("console:connect:openwebui", async () => startOpenWebUI());
ipcMain.handle("console:lapidary:restart", async () => { backend?.stop(); frontend?.stop(); await startSidecars(); return { ok: true }; });
ipcMain.handle("console:logs", async () => logLines.slice(-400));
ipcMain.handle("console:pwsh", async (_e, script) => {
  const pwshPath = await io.which("pwsh");
  const inv = pwshInvocation(String(script || ""), { pwshPath });
  log(`pwsh> ${String(script).split("\n")[0]}`);
  return new Promise((resolve) => {
    let out = "", err = "";
    const p = spawn(inv.program, inv.args, { windowsHide: true });
    const timer = setTimeout(() => { p.kill(); err += "\n[stopped after 120 seconds]"; }, 120000);
    p.stdout.on("data", (d) => (out += d)); p.stderr.on("data", (d) => (err += d));
    p.on("close", (code) => { clearTimeout(timer); resolve({ code, output: capOutput(out), error: capOutput(err), note: inv.note }); });
    p.on("error", (e) => { clearTimeout(timer); resolve({ code: -1, output: "", error: e.message, note: inv.note }); });
  });
});
ipcMain.handle("console:open", async (_e, url) => { await shell.openExternal(url); return { ok: true }; });

// ---- first run and recipes (ADR-012, roadmap 47)
function planContext(choice) {
  const settings = loadSettings();
  return { settings, choice: choice || settings.modelPolicy || "mix", localModel: settings.localModel || DEFAULT_LOCAL_MODEL };
}
ipcMain.handle("console:recipes", async (_e, choice) => {
  const ctx = { ...planContext(choice), status: await detectAll(io) };
  const plans = planAll(ctx).map((p) => ({ ...p, summary: summarise(p) }));
  return { choices: AI_CHOICES, plans, choice: ctx.choice, firstRunDone: Boolean(ctx.settings.firstRunDone), localModel: ctx.localModel };
});
ipcMain.handle("console:advanced:plan", async (_e, answers) => advancedPlan(answers, { status: await detectAll(io), settings: loadSettings(), paths: P }));
ipcMain.handle("console:recipe:run", async (_e, recipeId, choice, keys) => {
  if (keys && (keys.anthropicKey || keys.openaiKey)) { const s = loadSettings(); for (const k of ["anthropicKey", "openaiKey"]) if (keys[k]) s[k] = keys[k]; saveSettings(s); }
  const ctx = { ...planContext(choice), status: await detectAll(io) };
  const p = plan(recipeId, ctx);
  return runSteps(p.steps, { patch: { modelPolicy: ctx.choice, localModel: ctx.localModel } });
});
ipcMain.handle("console:advanced:run", async (_e, answers) => {
  const p = advancedPlan(answers, { status: await detectAll(io), settings: loadSettings(), paths: P });
  const policy = p.steps.find((s) => s.kind === "policy");
  return runSteps(p.steps, { patch: policy?.patch || {} });
});
ipcMain.handle("console:firstrun:done", async () => { const s = loadSettings(); s.firstRunDone = "yes"; saveSettings(s); return { ok: true }; });

// ---- the Doctor (roadmap 49): gather the facts, let lib/doctor.js judge them, run the fix it offers
async function portState(port, healthUrl) {
  if (healthUrl && await io.fetchOk(healthUrl)) return "lapidary";
  return new Promise((resolve) => {
    const sock = netConnect({ host: "127.0.0.1", port, timeout: 800 });
    sock.once("connect", () => { sock.destroy(); resolve("other"); });
    sock.once("error", () => resolve("free"));
    sock.once("timeout", () => { sock.destroy(); resolve("free"); });
  });
}
async function probeKey(provider, key) {
  if (!key) return null;
  const url = provider === "anthropic" ? "https://api.anthropic.com/v1/models" : "https://api.openai.com/v1/models";
  const headers = provider === "anthropic" ? { "x-api-key": key, "anthropic-version": "2023-06-01" } : { authorization: `Bearer ${key}` };
  try {
    const r = await fetch(url, { headers, signal: AbortSignal.timeout(6000) });
    if (r.ok) return "ok";
    if (r.status === 401 || r.status === 403) return "invalid";
    return "offline";
  } catch { return "offline"; }
}
async function latestRelease() {
  try {
    const r = await fetch("https://api.github.com/repos/poyfather/lapidary/releases/latest", { headers: { accept: "application/vnd.github+json" }, signal: AbortSignal.timeout(5000) });
    if (!r.ok) return null;
    const tag = (await r.json()).tag_name || "";
    return tag.replace(/^v/, "") || null;
  } catch { return null; }
}
const readText = (file) => { try { return readFileSync(file, "utf8"); } catch { return null; } };

ipcMain.handle("console:doctor", async () => {
  const s = loadSettings();
  const [status, ports, anthropic, openai, latest] = await Promise.all([
    detectAll(io),
    (async () => ({
      [PORTS.lapidary]: await portState(PORTS.lapidary, "http://127.0.0.1:8000/health"),
      [PORTS.ui]: await portState(PORTS.ui, "http://127.0.0.1:3000"),
      [PORTS.openwebui]: await portState(PORTS.openwebui, "http://127.0.0.1:3080/health"),
      [PORTS.ollama]: await portState(PORTS.ollama, "http://127.0.0.1:11434/api/tags"),
    }))(),
    probeKey("anthropic", s.anthropicKey),
    probeKey("openai", s.openaiKey),
    latestRelease(),
  ]);
  const findings = diagnose({
    status,
    settings: { ...s, anthropicKey: s.anthropicKey ? "set" : "", openaiKey: s.openaiKey ? "set" : "" },
    keys: { anthropic, openai },
    ports,
    clients: { claude: readClientConfig(readText(P.claudeConfig)), chatgpt: readClientConfig(readText(P.chatgptConfig)) },
    composeExists: existsSync(join(dataDir, "open-webui.compose.yml")),
    version: app.getVersion(),
    latest,
  });
  log(`[doctor] ${doctorSummary(findings)}`);
  return { findings, summary: doctorSummary(findings), checkedAt: new Date().toISOString() };
});
ipcMain.handle("console:doctor:fix", async (_e, action) => {
  const [kind, arg] = [action.slice(0, action.indexOf(":") === -1 ? action.length : action.indexOf(":")), action.slice(action.indexOf(":") + 1)];
  if (kind === "restart") { backend?.stop(); frontend?.stop(); await startSidecars(); return { ok: true, message: "Lapidary restarted" }; }
  if (kind === "open" && arg === "docker") {
    const code = process.platform === "win32" ? await runCommand("cmd", ["/c", "start", "", "Docker Desktop"]) : await runCommand("open", ["-a", "Docker"]);
    return { ok: code === 0, message: code === 0 ? "Docker Desktop is opening; wait for it to say running, then check again" : "could not open Docker Desktop; start it from the Start menu" };
  }
  if (kind === "open") { await shell.openExternal(arg); return { ok: true, message: "opened" }; }
  if (kind === "view") return { ok: true, message: "", view: arg };
  if (["install", "start", "pull", "connect", "policy"].includes(kind)) {
    const r = await runStep({ id: action, kind, detail: "" }, kind === "policy" ? { modelPolicy: arg } : {});
    return r;
  }
  return { ok: false, message: `no fix called ${action}` };
});

const progress = (ev) => { win?.webContents.send("console:progress", ev); if (ev.message) log(`[recipe] ${ev.step}: ${ev.message}`); };

/** Run a plan's steps in order, reporting each one. Stops at the first required failure. */
async function runSteps(steps, { patch }) {
  const results = [];
  for (const step of steps) {
    if (step.done || step.skipWhen) { progress({ step: step.id, state: "skipped", message: step.done ? "already here" : step.skipWhen }); continue; }
    progress({ step: step.id, state: "running" });
    let r;
    try { r = await runStep(step, patch); } catch (e) { r = { ok: false, message: e.message }; }
    results.push({ id: step.id, ...r });
    progress({ step: step.id, state: r.ok ? "done" : "failed", message: r.message });
    if (!r.ok && !step.optional) return { ok: false, failed: step.id, message: r.message, results };
  }
  const s = loadSettings(); s.firstRunDone = "yes"; saveSettings(s);
  return { ok: true, results };
}

async function runStep(step, patch) {
  const arg = step.id.slice(step.id.indexOf(":") + 1);   // model names carry a colon (qwen3:4b)
  switch (step.kind) {
    case "install": {
      const cmd = installCommand(arg);
      if (!cmd) return { ok: false, message: `nothing to install for ${arg}` };
      const code = await runCommand(cmd.program, cmd.args);
      return { ok: code === 0, message: code === 0 ? "installed" : `the installer exited with ${code}; see Logs` };
    }
    case "start": {
      const ollama = (await io.which("ollama")) || "ollama";
      try { const child = spawn(ollama, ["serve"], { detached: true, stdio: "ignore", windowsHide: true }); child.unref(); } catch (e) { return { ok: false, message: e.message }; }
      const up = await waitForHealth("http://127.0.0.1:11434/api/tags", { timeoutMs: 20000 });
      return { ok: up, message: up ? "running" : "Ollama did not answer on port 11434; open the Ollama app and try again" };
    }
    case "pull": {
      const code = await runCommand((await io.which("ollama")) || "ollama", ["pull", arg]);
      return { ok: code === 0, message: code === 0 ? "downloaded" : `the download stopped with ${code}; check the internet connection and Logs` };
    }
    case "key": {
      const s = loadSettings();
      return s.anthropicKey || s.openaiKey ? { ok: true, message: "key saved" } : { ok: false, message: "no key yet; add one in the box above or in Settings" };
    }
    case "policy": {
      const s = loadSettings();
      Object.assign(s, patch);
      saveSettings(s);
      backend?.stop(); frontend?.stop(); await startSidecars();
      return { ok: true, message: "saved and Lapidary restarted" };
    }
    case "connect": {
      if (arg === "openwebui") return startOpenWebUI();
      return writeMcp(arg === "claude" ? P.claudeConfig : P.chatgptConfig);
    }
    case "open": {
      await shell.openExternal(step.detail);
      return { ok: true, message: "opened" };
    }
    case "note":
      return { ok: true, message: "" };
    default:
      return { ok: false, message: `unknown step ${step.kind}` };
  }
}

async function startOpenWebUI() {
  const s = loadSettings();
  const file = join(dataDir, "open-webui.compose.yml");
  mkdirSync(dataDir, { recursive: true });
  writeFileSync(file, openWebUICompose({ lapidaryKey: s.gemsApiKey || "", openaiKey: s.openaiKey || "" }));
  const code = await runCommand("docker", ["compose", "-f", file, "up", "-d"]);
  if (code !== 0) return { ok: false, message: `Docker did not start the chat (code ${code}). Open Docker Desktop, wait for it to say running, and try again. The file is at ${file}` };
  const up = await waitForHealth("http://127.0.0.1:3080/health", { timeoutMs: 90000 });
  return { ok: true, message: up ? "Open WebUI is running on http://localhost:3080" : "Open WebUI is starting on http://localhost:3080 (first start takes a minute)" };
}

function writeMcp(file) {
  const r = resources();
  const entries = lapidaryMcpEntries({ backendDir: dirname(r.backendExe), pythonExe: r.backendExe });
  entries.lapidary = { command: r.backendExe, args: ["--mcp"] };
  mkdirSync(dirname(file), { recursive: true });
  const existing = existsSync(file) ? readFileSync(file, "utf8") : "";
  try {
    writeFileSync(file, mergeMcpServers(existing, entries));
    return { ok: true, message: `connected; restart the app to see Lapidary in it (${file})` };
  } catch (e) { return { ok: false, message: `could not write the app's config file (${e.message}); check it is valid JSON or that the folder is writable` }; }
}

// ---- window
function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 820, minWidth: 960, minHeight: 600,
    backgroundColor: "#0b0e11", title: "Lapidary Console", autoHideMenuBar: true,
    webPreferences: { preload: join(here, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.loadFile(join(here, "renderer", "console.html"));
}

app.whenReady().then(async () => {
  createWindow();
  await startSidecars();
  win?.webContents.send("console:ready");
});
app.on("window-all-closed", () => { backend?.stop(); frontend?.stop(); app.quit(); });
