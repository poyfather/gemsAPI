// Detection of the AI tools on this machine: pure functions over an injected
// environment so they can be tested on any platform. Nothing here installs.
//
// A component is { id, name, kind, detect(), install, health }:
//   detect  -> { installed, version?, path?, note? }
//   install -> what the console runs to install it (winget id, docker image, npm package)
//   health  -> an http endpoint to poll when the component runs a service

import { join } from "node:path";

export const COMPONENTS = [
  { id: "winget",   name: "winget (Windows Package Manager)", kind: "tooling",  install: null, blurb: "Built into Windows. The console uses it to install the other pieces from their publishers." },
  { id: "pwsh",     name: "PowerShell 7",                     kind: "tooling",  install: { winget: "Microsoft.PowerShell" }, blurb: "The modern command line for Windows. The console and your assistants use it to look at and fix things on this PC, always asking first." },
  { id: "node",     name: "Node.js",                          kind: "tooling",  install: { winget: "OpenJS.NodeJS.LTS" }, blurb: "Needed by some of the tools below. Nothing you use directly." },
  { id: "docker",   name: "Docker Desktop",                   kind: "tooling",  install: { winget: "Docker.DockerDesktop" }, blurb: "Runs Open WebUI in a box of its own. Only needed if you want the private chat." },
  { id: "claude",   name: "Claude Desktop",                   kind: "client",   install: { winget: "Anthropic.Claude" }, blurb: "Anthropic's assistant app. Connect it and it can use your prompts and assistants from here." },
  { id: "chatgpt",  name: "ChatGPT",                          kind: "client",   install: { winget: "OpenAI.ChatGPT" }, blurb: "OpenAI's assistant app. Connect it the same way." },
  { id: "ollama",   name: "Ollama (local models)",            kind: "service",  install: { winget: "Ollama.Ollama" }, health: "http://127.0.0.1:11434/api/tags", blurb: "AI models that run on this PC. Free, private, no account, works offline. Slower than the cloud, good enough for a lot." },
  { id: "openwebui", name: "Open WebUI",                      kind: "service",  install: { docker: "ghcr.io/open-webui/open-webui:main", pip: "open-webui" }, health: "http://127.0.0.1:3080/health", blurb: "A chat website that runs on this PC, like ChatGPT but yours. Talks to local models, the cloud, and your prompts here." },
  { id: "rea",      name: "REA (Reverse Engineer Anything)", kind: "mcp", install: { npm: "rea-agents" }, blurb: "Lets an assistant look inside an app or file you own to understand how it works. Comes with the console." },
  { id: "lapidary", name: "Lapidary (your prompts and assistants)", kind: "hub",      install: null, health: "http://127.0.0.1:8000/health", blurb: "The heart of this: your prompts, your assistants, and the place every other app connects to." },
];

/** Default file locations per platform. `env` is process.env-like; `platform` is process.platform-like. */
export function paths(env, platform) {
  const home = env.USERPROFILE || env.HOME || "";
  if (platform === "win32") {
    const appData = env.APPDATA || join(home, "AppData", "Roaming");
    const local = env.LOCALAPPDATA || join(home, "AppData", "Local");
    return {
      claudeConfig: join(appData, "Claude", "claude_desktop_config.json"),
      chatgptConfig: join(appData, "OpenAI", "ChatGPT", "mcp_config.json"),
      claudeApp: join(local, "AnthropicClaude"),
      chatgptApp: join(local, "Programs", "ChatGPT"),
      ollamaApp: join(local, "Programs", "Ollama"),
      consoleData: join(appData, "Lapidary"),
    };
  }
  const support = join(home, "Library", "Application Support");
  return {
    claudeConfig: join(support, "Claude", "claude_desktop_config.json"),
    chatgptConfig: join(support, "com.openai.chat", "mcp_config.json"),
    claudeApp: "/Applications/Claude.app",
    chatgptApp: "/Applications/ChatGPT.app",
    ollamaApp: "/Applications/Ollama.app",
    consoleData: join(support, "Lapidary"),
  };
}

/**
 * Detect every component. `io` supplies the side effects:
 *   io.which(cmd) -> path or null;  io.exists(path) -> bool;  io.version(cmd, args) -> string or null
 *   io.fetchOk(url) -> bool;  io.fetchJson(url) -> parsed body or null (optional, lists Ollama's models)
 */
export async function detectAll(io, env = process.env, platform = process.platform) {
  const p = paths(env, platform);
  const results = {};
  for (const c of COMPONENTS) {
    results[c.id] = await detectOne(c, io, p);
  }
  return results;
}

async function detectOne(c, io, p) {
  switch (c.id) {
    case "winget": {
      const path = await io.which("winget");
      return { installed: !!path, path, version: path ? await io.version("winget", ["--version"]) : null };
    }
    case "pwsh": {
      const path = await io.which("pwsh");
      return { installed: !!path, path, version: path ? await io.version("pwsh", ["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]) : null,
               note: path ? null : "Windows PowerShell 5 will be used until PowerShell 7 is installed" };
    }
    case "node": {
      const path = await io.which("node");
      return { installed: !!path, path, version: path ? await io.version("node", ["--version"]) : null };
    }
    case "docker": {
      const path = await io.which("docker");
      const version = path ? await io.version("docker", ["--version"]) : null;
      return { installed: !!path, path, version, note: version ? null : "docker on PATH but the engine did not answer" };
    }
    case "claude":
      return { installed: await io.exists(p.claudeApp), path: p.claudeApp, configured: await io.exists(p.claudeConfig) };
    case "chatgpt":
      return { installed: await io.exists(p.chatgptApp), path: p.chatgptApp, configured: await io.exists(p.chatgptConfig) };
    case "ollama": {
      const path = (await io.which("ollama")) || ((await io.exists(p.ollamaApp)) ? p.ollamaApp : null);
      const running = await io.fetchOk(c.health);
      const models = running && io.fetchJson ? ((await io.fetchJson(c.health))?.models || []).map((m) => m.name) : [];
      return { installed: !!path, path, running, models };
    }
    case "openwebui":
      return { installed: await io.fetchOk(c.health), running: await io.fetchOk(c.health), note: "detected by its health endpoint" };
    case "rea": {
      const bundled = await io.exists(join(p.consoleData, "node_modules", "rea-agents")) || true; // bundled with the console
      return { installed: bundled, note: "bundled with Lapidary Console" };
    }
    case "lapidary":
      return { installed: true, running: await io.fetchOk(c.health) };
    default:
      return { installed: false };
  }
}

/** The winget, docker or npm command for a component, or null when there is nothing to run. */
export function installCommand(id) {
  const c = COMPONENTS.find((x) => x.id === id);
  if (!c || !c.install) return null;
  if (c.install.winget) return { program: "winget", args: ["install", "--id", c.install.winget, "-e", "--accept-source-agreements", "--accept-package-agreements"] };
  if (c.install.docker) return { program: "docker", args: ["pull", c.install.docker] };
  if (c.install.npm) return { program: "npm", args: ["install", "-g", c.install.npm] };
  return null;
}
