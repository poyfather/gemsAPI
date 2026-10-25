import { test } from "node:test";
import assert from "node:assert/strict";
import { backendEnv, lapidaryMcpEntries, lapidaryMcpServersFile, mergeMcpServers, openWebUICompose } from "../lib/configs.js";

test("merging MCP entries keeps what the user already had", () => {
  const existing = JSON.stringify({ mcpServers: { filesystem: { command: "npx", args: ["fs"] } }, theme: "dark" });
  const out = JSON.parse(mergeMcpServers(existing, lapidaryMcpEntries({ backendDir: "C:\\L\\backend", pythonExe: "C:\\L\\backend\\lapidary-backend.exe" })));
  assert.deepEqual(Object.keys(out.mcpServers).sort(), ["filesystem", "lapidary", "rea"]);
  assert.equal(out.theme, "dark");
  assert.deepEqual(out.mcpServers.rea, { command: "npx", args: ["-y", "rea-agents@6.4.0", "mcp"] });
});

test("merging into an empty or missing file works, and invalid JSON is refused", () => {
  assert.ok(JSON.parse(mergeMcpServers("", { a: { command: "x" } })).mcpServers.a);
  assert.ok(JSON.parse(mergeMcpServers("   ", { a: { command: "x" } })).mcpServers.a);
  assert.throws(() => mergeMcpServers("{not json", { a: {} }), /not valid JSON/);
});

test("the Open WebUI compose file points at Lapidary through host.docker.internal and adds OpenAI when a key exists", () => {
  const yml = openWebUICompose({ lapidaryKey: "lap-key", openaiKey: "sk-x", port: 3080 });
  assert.match(yml, /OPENAI_API_BASE_URLS: "http:\/\/host\.docker\.internal:8000\/v1;https:\/\/api\.openai\.com\/v1"/);
  assert.match(yml, /OPENAI_API_KEYS: "lap-key;sk-x"/);
  assert.match(yml, /"3080:8080"/);
  assert.match(yml, /OLLAMA_BASE_URL: "http:\/\/host\.docker\.internal:11434"/);
  const only = openWebUICompose({ lapidaryKey: "lap-key" });
  assert.match(only, /OPENAI_API_KEYS: "lap-key"\n/);
});

test("the backend environment reflects the settings, sqlite by default, supabase when configured", () => {
  const base = backendEnv({ gemsApiKey: "k", anthropicKey: "a" }, { dataDir: "D:\\data", mcpServersFile: "D:\\data\\mcp.json" });
  assert.equal(base.GEMS_STORAGE, "sqlite");
  assert.equal(base.GEMS_MODEL_POLICY, "auto");
  assert.equal(backendEnv({ gemsApiKey: "k", modelPolicy: "local", localBaseUrl: "http://127.0.0.1:1234/v1" }, { dataDir: "d", mcpServersFile: "m" }).LOCAL_OPENAI_BASE_URL, "http://127.0.0.1:1234/v1");
  assert.equal(base.GEMS_SQLITE_PATH, "D:\\data/lapidary.db");
  assert.equal(base.ANTHROPIC_API_KEY, "a");
  assert.equal(base.OPENAI_API_KEY, undefined);
  const hosted = backendEnv({ gemsApiKey: "k", supabaseUrl: "https://x.supabase.co", supabaseKey: "s" }, { dataDir: "d", mcpServersFile: "m" });
  assert.equal(hosted.GEMS_STORAGE, "supabase");
  assert.equal(hosted.SUPABASE_SERVICE_ROLE_KEY, "s");
  assert.deepEqual(JSON.parse(lapidaryMcpServersFile({})).mcpServers.rea.risky, false);
});
