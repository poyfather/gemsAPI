import { test } from "node:test";
import assert from "node:assert/strict";
import { diagnose, readClientConfig, summarise } from "../lib/doctor.js";

const healthy = {
  status: { lapidary: { running: true }, ollama: { installed: true, running: true, models: ["qwen3:4b"] }, docker: { installed: true, version: "Docker version 28" }, openwebui: { running: true }, claude: { installed: true }, chatgpt: { installed: false }, pwsh: { installed: true, version: "7.5.2" } },
  settings: { modelPolicy: "mix", anthropicKey: "set", openaiKey: "" },
  keys: { anthropic: "ok" },
  ports: { 8000: "lapidary", 3000: "lapidary", 3080: "lapidary", 11434: "lapidary" },
  clients: { claude: { exists: true, connected: true } },
  composeExists: true,
  version: "0.3.0", latest: "0.3.0",
};
const byId = (findings) => Object.fromEntries(findings.map((f) => [f.id, f]));

test("a healthy machine has nothing to fix", () => {
  const f = diagnose(healthy);
  assert.equal(summarise(f), "everything looks fine");
  assert.ok(f.every((x) => x.state !== "fail" && x.state !== "warn"), JSON.stringify(f.filter((x) => x.state === "fail" || x.state === "warn")));
  const m = byId(f);
  assert.equal(m.lapidary.state, "ok"); assert.equal(m["ai-local"].state, "ok"); assert.equal(m["key-anthropic"].state, "ok");
  assert.equal(m["connect-claude"].state, "ok"); assert.equal(m["connect-chatgpt"].state, "skip"); assert.equal(m.version.state, "ok");
  assert.ok(f.every((x) => x.title && x.detail), "every finding explains itself");
});

test("lapidary down, or its port taken, offers a restart with a different explanation", () => {
  const down = byId(diagnose({ ...healthy, status: { ...healthy.status, lapidary: { running: false } }, ports: { ...healthy.ports, 8000: "free" } }));
  assert.equal(down.lapidary.state, "fail"); assert.equal(down.lapidary.fix.action, "restart"); assert.match(down.lapidary.detail, /Logs/);
  const taken = byId(diagnose({ ...healthy, status: { ...healthy.status, lapidary: { running: false } }, ports: { ...healthy.ports, 8000: "other" } }));
  assert.match(taken.lapidary.title, /Another program/); assert.match(taken.lapidary.detail, /port 8000/);
});

test("the AI choice is checked against what is actually there", () => {
  const base = { ...healthy, settings: { modelPolicy: "local" } };
  assert.equal(byId(diagnose({ ...base, status: { ...base.status, ollama: { installed: false } } }))["ai-local"].fix.action, "install:ollama");
  assert.equal(byId(diagnose({ ...base, status: { ...base.status, ollama: { installed: true, running: false } } }))["ai-local"].fix.action, "start:ollama");
  const noModel = byId(diagnose({ ...base, status: { ...base.status, ollama: { installed: true, running: true, models: [] } }, settings: { modelPolicy: "local", localModel: "llama3.2" } }));
  assert.equal(noModel["ai-local"].state, "fail"); assert.equal(noModel["ai-local"].fix.action, "pull:llama3.2");
  assert.equal(byId(diagnose(base))["ai-key"].state, "skip", "local only never needs a key");
  const online = byId(diagnose({ ...healthy, settings: { modelPolicy: "online" }, keys: {} }));
  assert.equal(online["ai-key"].state, "fail"); assert.equal(online["ai-key"].fix.action, "view:settings");
  assert.equal(online["ai-local"].state, "ok", "ollama running is reported, not demanded");
  const autoNothing = byId(diagnose({ ...healthy, settings: { modelPolicy: "auto" }, keys: {}, status: { ...healthy.status, ollama: { installed: false } } }));
  assert.equal(autoNothing["ai-key"].state, "fail"); assert.match(autoNothing["ai-key"].detail, /nothing to pick from/);
});

test("a refused key is a failure that points at Settings; an unreachable service is skipped", () => {
  const bad = byId(diagnose({ ...healthy, settings: { modelPolicy: "mix", anthropicKey: "set", openaiKey: "set" }, keys: { anthropic: "invalid", openai: "offline" } }));
  assert.equal(bad["key-anthropic"].state, "fail"); assert.equal(bad["key-anthropic"].fix.action, "view:settings");
  assert.equal(bad["key-openai"].state, "skip");
  assert.equal(summarise(Object.values(bad)), "1 thing to fix");
});

test("the private chat: docker missing, docker not running, port taken, or simply stopped", () => {
  const stopped = { ...healthy, status: { ...healthy.status, openwebui: { running: false } }, ports: { ...healthy.ports, 3080: "free" } };
  assert.equal(byId(diagnose(stopped)).openwebui.fix.action, "connect:openwebui");
  assert.equal(byId(diagnose({ ...stopped, status: { ...stopped.status, docker: { installed: false } } })).openwebui.fix.action, "install:docker");
  assert.equal(byId(diagnose({ ...stopped, status: { ...stopped.status, docker: { installed: true, version: null } } })).openwebui.fix.action, "open:docker");
  assert.match(byId(diagnose({ ...stopped, ports: { ...stopped.ports, 3080: "other" } })).openwebui.title, /Another program/);
  assert.equal(byId(diagnose({ ...stopped, composeExists: false })).openwebui.state, "skip");
});

test("connections: not connected offers connect, a damaged config is explained, a missing app is skipped", () => {
  const f = byId(diagnose({ ...healthy, status: { ...healthy.status, chatgpt: { installed: true } }, clients: { claude: { exists: true, connected: false }, chatgpt: { exists: true, connected: false, broken: true } } }));
  assert.equal(f["connect-claude"].state, "warn"); assert.equal(f["connect-claude"].fix.action, "connect:claude");
  assert.equal(f["connect-chatgpt"].state, "fail"); assert.match(f["connect-chatgpt"].detail, /JSON/);
  assert.deepEqual(readClientConfig(null), { exists: false, connected: false, broken: false });
  assert.deepEqual(readClientConfig('{"mcpServers":{"lapidary":{}}}'), { exists: true, connected: true, broken: false });
  assert.deepEqual(readClientConfig("{oops"), { exists: true, connected: false, broken: true });
});

test("versions: newer available, up to date, or offline", () => {
  assert.equal(byId(diagnose({ ...healthy, latest: "0.4.0" })).version.state, "warn");
  assert.match(byId(diagnose({ ...healthy, latest: "0.4.0" })).version.fix.action, /releases/);
  assert.equal(byId(diagnose({ ...healthy, latest: null })).version.state, "skip");
  const pwsh = byId(diagnose({ ...healthy, status: { ...healthy.status, pwsh: { installed: false } } }));
  assert.equal(pwsh.pwsh.fix.action, "install:pwsh");
  assert.equal(summarise(Object.values(pwsh)), "1 suggestion");
});

test("the helper: running, stopped, or not on this platform; updates go through it when it runs", () => {
  assert.equal(byId(diagnose({ ...healthy, helper: { running: true } })).helper.state, "ok");
  assert.equal(byId(diagnose({ ...healthy, helper: { running: false } })).helper.state, "warn");
  assert.equal(byId(diagnose({ ...healthy, helper: { running: false } })).helper.fix.action, "helper:start");
  assert.equal(byId(diagnose(healthy)).helper, undefined);
  assert.equal(byId(diagnose({ ...healthy, latest: "0.4.0", helper: { running: true } })).version.fix.action, "update:console");
  assert.match(byId(diagnose({ ...healthy, latest: "0.4.0", helper: { running: false } })).version.fix.action, /releases/);
});
