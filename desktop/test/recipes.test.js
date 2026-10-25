import { test } from "node:test";
import assert from "node:assert/strict";
import { AI_CHOICES, DEFAULT_LOCAL_MODEL, RECIPES, advancedPlan, plan, planAll, summarise } from "../lib/recipes.js";

const fresh = { winget: { installed: true }, pwsh: { installed: false }, node: { installed: false }, docker: { installed: false }, claude: { installed: false }, chatgpt: { installed: false }, ollama: { installed: false, running: false, models: [] }, openwebui: { installed: false, running: false }, rea: { installed: true }, lapidary: { installed: true, running: true } };
const ready = { ...fresh, pwsh: { installed: true }, docker: { installed: true }, ollama: { installed: true, running: true, models: [`${DEFAULT_LOCAL_MODEL}`] }, openwebui: { installed: true, running: true }, claude: { installed: true, configured: true }, chatgpt: { installed: true, configured: true } };

test("the five answers to which AI are the backend policies, each in plain words", () => {
  assert.deepEqual(AI_CHOICES.map((c) => c.id).sort(), ["auto", "local", "manual", "mix", "online"]);
  for (const c of AI_CHOICES) { assert.ok(c.title && c.blurb && c.privacy && c.cost, c.id); assert.ok(!/MCP|RLS|provider/i.test(c.blurb), `${c.id} blurb has jargon`); }
  assert.equal(AI_CHOICES.filter((c) => c.recommended).length, 1);
});

test("every recipe says what it is, what it needs and what you can do afterwards", () => {
  assert.equal(RECIPES.length, 8);
  for (const r of RECIPES) {
    assert.ok(r.title && r.blurb && r.needs && r.now?.length >= 2, r.id);
    assert.ok(r.open?.url && r.open?.label, `${r.id} has nothing to open`);
  }
});

test("a private chat on a fresh PC with the free AI: install, start, download, docker, policy, open webui, open", () => {
  const p = plan("private-chat", { status: fresh, settings: {}, choice: "local" });
  assert.deepEqual(p.steps.map((s) => s.id), ["install:ollama", "start:ollama", `pull:${DEFAULT_LOCAL_MODEL}`, "install:docker", "policy:local", "connect:openwebui", "open"]);
  assert.ok(p.steps.every((s) => !s.done));
  assert.equal(p.steps.find((s) => s.kind === "install").detail, "winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements");
  assert.equal(summarise(p), "6 steps");
  assert.ok(!p.steps.some((s) => s.kind === "key"), "local only never asks for a key");
});

test("online only asks for a key instead of Ollama, and a mix asks for both", () => {
  const online = plan("private-chat", { status: fresh, settings: {}, choice: "online" });
  assert.ok(!online.steps.some((s) => s.id.includes("ollama")));
  const key = online.steps.find((s) => s.kind === "key");
  assert.ok(key && !key.optional && !key.done);
  const withKey = plan("private-chat", { status: fresh, settings: { anthropicKey: "set" }, choice: "online" });
  assert.equal(withKey.steps.find((s) => s.kind === "key").done, true);
  const mix = plan("private-chat", { status: fresh, settings: {}, choice: "mix" });
  assert.ok(mix.steps.some((s) => s.id === "install:ollama") && mix.steps.some((s) => s.kind === "key" && !s.optional));
  const auto = plan("private-chat", { status: fresh, settings: {}, choice: "auto" });
  assert.equal(auto.steps.find((s) => s.kind === "key").optional, true);
});

test("on a machine that has everything, a recipe is ready now and every step but open is already here", () => {
  const p = plan("homework", { status: ready, settings: { modelPolicy: "mix", anthropicKey: "set", localModel: DEFAULT_LOCAL_MODEL }, choice: "mix" });
  assert.equal(summarise(p), "ready now");
  assert.deepEqual(p.steps.filter((s) => !s.done).map((s) => s.id), ["open"]);
  assert.ok(p.steps.some((s) => s.id === "gem:study_buddy" && s.done));
});

test("a pulled model counts with or without its tag", () => {
  const status = { ...fresh, ollama: { installed: true, running: true, models: ["qwen3:4b"] } };
  assert.equal(plan("powershell-helper", { status, choice: "local", localModel: "qwen3" }).steps.find((s) => s.kind === "pull").done, true);
  assert.equal(plan("powershell-helper", { status, choice: "local", localModel: "qwen3:4b" }).steps.find((s) => s.kind === "pull").done, true);
  assert.equal(plan("powershell-helper", { status, choice: "local", localModel: "llama3.2" }).steps.find((s) => s.kind === "pull").done, false);
});

test("let Claude and ChatGPT use my prompts: the apps are optional, connecting skips the ones not installed", () => {
  const status = { ...fresh, claude: { installed: true, configured: false } };
  const p = plan("my-prompts", { status, settings: {}, choice: "mix" });
  const claude = p.steps.find((s) => s.id === "connect:claude");
  const chatgpt = p.steps.find((s) => s.id === "connect:chatgpt");
  assert.equal(claude.skipWhen, undefined);
  assert.match(chatgpt.skipWhen, /not installed/);
  assert.ok(p.steps.find((s) => s.id === "install:chatgpt").optional);
  assert.ok(!p.steps.some((s) => s.kind === "policy" || s.kind === "pull"), "no model needed to share prompts");
  assert.equal(summarise(p), "1 step");
});

test("the policy step is done only when the saved settings match", () => {
  const p = (settings) => plan("powershell-helper", { status: ready, settings, choice: "local", localModel: DEFAULT_LOCAL_MODEL }).steps.find((s) => s.kind === "policy").done;
  assert.equal(p({ modelPolicy: "local", localModel: DEFAULT_LOCAL_MODEL }), true);
  assert.equal(p({ modelPolicy: "mix", localModel: DEFAULT_LOCAL_MODEL }), false);
  assert.equal(p({ modelPolicy: "local", localModel: "other" }), false);
});

test("planAll covers every recipe and an unknown recipe is refused", () => {
  assert.equal(planAll({ status: fresh }).length, RECIPES.length);
  assert.throws(() => plan("nope", {}), /unknown recipe/);
});

test("the advanced plan lists every file and command before anything runs", () => {
  const paths = { consoleData: "C:\\Users\\t\\AppData\\Roaming\\Lapidary", claudeConfig: "C:\\Users\\t\\AppData\\Roaming\\Claude\\claude_desktop_config.json", chatgptConfig: "C:\\x\\mcp_config.json" };
  const p = advancedPlan({ components: ["ollama", "docker", "claude"], choice: "mix", keys: { anthropicKey: "sk-ant-1" }, storage: "sqlite", connect: ["claude", "openwebui"], localModel: "qwen3:4b" }, { status: fresh, settings: {}, paths });
  assert.deepEqual(p.steps.map((s) => s.id), ["install:ollama", "install:docker", "install:claude", "start:ollama", "pull:qwen3:4b", "policy:mix", "connect:claude", "connect:openwebui", "open"]);
  assert.ok(p.writes.some((w) => w.includes("settings.bin") && w.includes("lapidary.db")));
  assert.ok(p.writes.some((w) => w.includes("claude_desktop_config.json")));
  assert.ok(p.writes.some((w) => w.includes("open-webui.compose.yml")));
  assert.ok(p.commands.includes("ollama pull qwen3:4b"));
  assert.ok(p.commands.some((c) => c.startsWith("winget install --id Docker.DockerDesktop")));
  const policy = p.steps.find((s) => s.kind === "policy");
  assert.deepEqual(policy.patch, { modelPolicy: "mix", localModel: "qwen3:4b", anthropicKey: "sk-ant-1" });
  assert.equal(p.ports.openwebui, 3080);
  const hosted = advancedPlan({ choice: "online", storage: "supabase", supabaseUrl: "https://x.supabase.co", supabaseKey: "s" }, { paths });
  assert.ok(hosted.writes[0].includes("no database file"));
  assert.equal(hosted.steps.find((s) => s.kind === "policy").patch.supabaseKey, "s");
  assert.ok(!hosted.steps.some((s) => s.kind === "pull"), "online only downloads nothing");
});
