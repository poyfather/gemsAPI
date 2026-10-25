import { test } from "node:test";
import assert from "node:assert/strict";
import { TOOLBOX, detectToolbox, toolboxInstallCommand, toolboxSourceLabel } from "../lib/toolbox.js";

test("every toolbox entry has a unique id, a publisher, a legitimate source and a homepage", () => {
  const ids = TOOLBOX.map((t) => t.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const t of TOOLBOX) {
    assert.ok(t.publisher && t.homepage.startsWith("https://"), t.id);
    assert.ok(t.source.winget || t.source.psgallery || t.source.command, t.id);
    if (t.source.winget) assert.match(t.source.winget, /^[A-Za-z0-9+.-]+\.[A-Za-z0-9+.-]+$/, t.id);
  }
});

test("install commands go through winget, the PowerShell Gallery or a documented command", () => {
  assert.deepEqual(toolboxInstallCommand("git").args.slice(0, 3), ["install", "--id", "Git.Git"]);
  const mod = toolboxInstallCommand("msgraph", { pwshPath: "C:\\pwsh.exe" });
  assert.equal(mod.program, "C:\\pwsh.exe");
  assert.match(mod.args.at(-1), /Install-Module -Name Microsoft\.Graph -Scope CurrentUser/);
  assert.deepEqual(toolboxInstallCommand("wsl"), { program: "wsl", args: ["--install", "--no-launch"] });
  assert.equal(toolboxInstallCommand("nope"), null);
  assert.equal(toolboxSourceLabel(TOOLBOX.find((t) => t.id === "7zip")), "winget 7zip.7zip");
});

test("detection reports installed for commands on PATH and unknown otherwise", async () => {
  const io = { which: async (cmd) => (cmd === "git" ? "C:\\git.exe" : null) };
  const s = await detectToolbox(io);
  assert.deepEqual(s.git, { installed: true, path: "C:\\git.exe" });
  assert.equal(s.nmap.installed, false);
  assert.equal(s.powertoys.installed, null);
});
