import { test } from "node:test";
import assert from "node:assert/strict";
import { COMPONENTS, detectAll, installCommand, paths } from "../lib/components.js";

const winEnv = { USERPROFILE: "C:\\Users\\troy", APPDATA: "C:\\Users\\troy\\AppData\\Roaming", LOCALAPPDATA: "C:\\Users\\troy\\AppData\\Local" };

test("windows paths follow APPDATA and LOCALAPPDATA", () => {
  const p = paths(winEnv, "win32");
  assert.ok(p.claudeConfig.endsWith("Claude/claude_desktop_config.json") || p.claudeConfig.endsWith("Claude\\claude_desktop_config.json"));
  assert.ok(p.consoleData.includes("Roaming") && p.consoleData.endsWith("Lapidary"));
  assert.ok(p.chatgptApp.includes("Programs"));
});

test("mac paths use Application Support", () => {
  const p = paths({ HOME: "/Users/troy" }, "darwin");
  assert.equal(p.claudeConfig, "/Users/troy/Library/Application Support/Claude/claude_desktop_config.json");
  assert.equal(p.claudeApp, "/Applications/Claude.app");
});

test("detection reports installed, running and missing from the injected io", async () => {
  const io = {
    which: async (cmd) => ({ winget: "C:\\winget.exe", node: "C:\\node.exe", pwsh: "C:\\Program Files\\PowerShell\\7\\pwsh.exe" }[cmd] || null),
    exists: async (path) => path.includes("AnthropicClaude") || path.includes("claude_desktop_config"),
    version: async (cmd) => ({ winget: "v1.9", node: "v24.14.1", pwsh: "7.5.2" }[cmd] || null),
    fetchOk: async (url) => url.includes("11434"),
  };
  const s = await detectAll(io, winEnv, "win32");
  assert.deepEqual({ installed: s.winget.installed, version: s.winget.version }, { installed: true, version: "v1.9" });
  assert.equal(s.node.version, "v24.14.1");
  assert.equal(s.pwsh.installed, true); assert.equal(s.pwsh.version, "7.5.2");
  assert.equal(s.docker.installed, false);
  assert.equal(s.claude.installed, true); assert.equal(s.claude.configured, true);
  assert.equal(s.chatgpt.installed, false);
  assert.equal(s.ollama.installed, false); assert.equal(s.ollama.running, true);
  assert.equal(s.openwebui.running, false);
  assert.equal(s.lapidary.running, false);
  assert.equal(Object.keys(s).length, COMPONENTS.length);
});

test("every component says what it costs or needs", () => {
  for (const c of COMPONENTS) assert.ok(c.costs && /free|built in/.test(c.costs), `${c.id} has no cost line`);
});

test("every component has a plain-language blurb", () => {
  for (const c of COMPONENTS) assert.ok(c.blurb && c.blurb.length > 20, c.id);
});

test("install commands are winget, docker or npm, and nothing for winget itself", () => {
  assert.deepEqual(installCommand("claude").program, "winget");
  assert.ok(installCommand("claude").args.includes("Anthropic.Claude"));
  assert.deepEqual(installCommand("openwebui"), { program: "docker", args: ["pull", "ghcr.io/open-webui/open-webui:main"] });
  assert.deepEqual(installCommand("rea"), { program: "npm", args: ["install", "-g", "rea-agents"] });
  assert.ok(installCommand("pwsh").args.includes("Microsoft.PowerShell"));
  assert.equal(installCommand("winget"), null);
  assert.equal(installCommand("nope"), null);
});
