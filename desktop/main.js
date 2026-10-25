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
ipcMain.handle("console:components", async () => ({ components: COMPONENTS.map(({ id, name, kind }) => ({ id, name, kind })), status: await detectAll(io) }));
ipcMain.handle("console:toolbox", async () => ({ tools: TOOLBOX.map((t) => ({ id: t.id, name: t.name, publisher: t.publisher, category: t.category, source: toolboxSourceLabel(t), homepage: t.homepage })), status: await detectToolbox(io) }));
ipcMain.handle("console:install", async (_e, id) => {
  const cmd = installCommand(id) || toolboxInstallCommand(id, { pwshPath: (await io.which("pwsh")) || "powershell.exe" });
  if (!cmd) return { ok: false, message: "nothing to install for this component" };
  const code = await runCommand(cmd.program, cmd.args);
  return { ok: code === 0, message: code === 0 ? "installed" : `exit code ${code}` };
});
ipcMain.handle("console:settings:get", async () => { const s = loadSettings(); return { ...s, anthropicKey: s.anthropicKey ? "set" : "", openaiKey: s.openaiKey ? "set" : "", supabaseKey: s.supabaseKey ? "set" : "" }; });
ipcMain.handle("console:settings:set", async (_e, patch) => {
  const s = loadSettings();
  for (const [k, v] of Object.entries(patch)) if (typeof v === "string" && v !== "set") s[k] = v;
  saveSettings(s);
  return { ok: true, note: "restart Lapidary from the dashboard for the backend to pick up new keys" };
});
ipcMain.handle("console:connect:claude", async () => writeMcp(P.claudeConfig));
ipcMain.handle("console:connect:chatgpt", async () => writeMcp(P.chatgptConfig));
ipcMain.handle("console:connect:openwebui", async () => {
  const s = loadSettings();
  const file = join(dataDir, "open-webui.compose.yml");
  mkdirSync(dataDir, { recursive: true });
  writeFileSync(file, openWebUICompose({ lapidaryKey: s.gemsApiKey || "", openaiKey: s.openaiKey || "" }));
  const code = await runCommand("docker", ["compose", "-f", file, "up", "-d"]);
  return { ok: code === 0, message: code === 0 ? "Open WebUI is starting on http://localhost:3080" : `docker compose exited with ${code}; the file is at ${file}` };
});
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

function writeMcp(file) {
  const r = resources();
  const entries = lapidaryMcpEntries({ backendDir: dirname(r.backendExe), pythonExe: r.backendExe });
  entries.lapidary = { command: r.backendExe, args: ["--mcp"] };
  mkdirSync(dirname(file), { recursive: true });
  const existing = existsSync(file) ? readFileSync(file, "utf8") : "";
  try {
    writeFileSync(file, mergeMcpServers(existing, entries));
    return { ok: true, message: `wrote ${file}; restart the client to pick it up` };
  } catch (e) { return { ok: false, message: e.message }; }
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
