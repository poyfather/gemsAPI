import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:net";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { buildAllowlist, helperHandles, helperPing, helperRequest, shouldFallBack } from "../lib/helper.js";
import { COMPONENTS } from "../lib/components.js";
import { TOOLBOX } from "../lib/toolbox.js";

test("allowlist holds only winget and PowerShell Gallery entries from the catalog", () => {
  const list = buildAllowlist({ version: "0.4.0", publisher: "CN=Lapidary" });
  assert.equal(list.console_version, "0.4.0");
  assert.equal(list.publisher_subject, "CN=Lapidary");
  assert.deepEqual(list.packages.git, { winget: "Git.Git" });
  assert.deepEqual(list.packages.pwsh, { winget: "Microsoft.PowerShell" });
  assert.deepEqual(list.packages.msgraph, { psgallery: "Microsoft.Graph" });
  assert.equal(list.packages.wsl, undefined, "raw commands never reach the helper");
  assert.equal(list.packages.openwebui, undefined, "docker and pip installs stay in the console");
  for (const [id, entry] of Object.entries(list.packages)) {
    assert.ok(COMPONENTS.some((c) => c.id === id) || TOOLBOX.some((t) => t.id === id), id);
    assert.equal(Object.keys(entry).length, 1);
  }
});

function fakeHelper(reply) {
  const dir = mkdtempSync(join(tmpdir(), "lapidary-pipe-"));
  const path = join(dir, "helper.sock");
  const got = [];
  const server = createServer((sock) => {
    let buf = "";
    sock.on("data", (d) => {
      buf += d;
      if (buf.includes("\n")) { got.push(JSON.parse(buf.split("\n")[0])); reply(sock); }
    });
  });
  return new Promise((resolve) => server.listen(path, () => resolve({ path, got, close: () => server.close() })));
}

test("helperRequest sends one line and streams progress until done", async () => {
  const h = await fakeHelper((sock) => {
    sock.write('{"line":"Downloading"}\n{"li');
    setTimeout(() => sock.write('ne":"Installing"}\nnot json\n{"done":true,"ok":true,"message":"git: done"}\n'), 10);
  });
  const lines = [];
  const out = await helperRequest({ op: "install", id: "git" }, { path: h.path, onLine: (l) => lines.push(l) });
  h.close();
  assert.deepEqual(h.got, [{ op: "install", id: "git" }]);
  assert.deepEqual(lines, ["Downloading", "Installing"]);
  assert.deepEqual(out, { done: true, ok: true, message: "git: done" });
});

test("helperRequest reports a helper that hangs up early", async () => {
  const h = await fakeHelper((sock) => sock.end('{"line":"half"}\n'));
  const out = await helperRequest({ op: "ping" }, { path: h.path });
  h.close();
  assert.equal(out.ok, false);
});

test("no helper means null, so the console falls back", async () => {
  assert.equal(await helperRequest({ op: "ping" }, { path: join(tmpdir(), "no-such-helper.sock") }), null);
  assert.equal(await helperPing({ path: join(tmpdir(), "no-such-helper.sock") }), null);
});

test("helperPing returns the answer when the helper is up", async () => {
  const h = await fakeHelper((sock) => sock.write('{"done":true,"ok":true,"message":"Lapidary Helper is running","version":"0.4.0"}\n'));
  const out = await helperPing({ path: h.path });
  h.close();
  assert.equal(out.version, "0.4.0");
});

test("the console hands the helper only what it can install, and falls back when it lacks the means", () => {
  assert.ok(helperHandles("git"));
  assert.ok(helperHandles("ollama"));
  assert.ok(!helperHandles("openwebui"));
  assert.ok(!helperHandles("wsl"));
  assert.ok(!helperHandles("__proto__"));
  assert.ok(shouldFallBack(null));
  assert.ok(shouldFallBack({ ok: false, message: "winget was not found on this machine; install App Installer" }));
  assert.ok(!shouldFallBack({ ok: false, message: "git: the installer stopped with code 1603" }));
  assert.ok(!shouldFallBack({ ok: true, message: "git: done" }));
});
