import { test } from "node:test";
import assert from "node:assert/strict";
import { capOutput, pwshInvocation } from "../lib/pwsh.js";

test("pwsh is preferred, Windows PowerShell 5 is the fallback on Windows only", () => {
  const seven = pwshInvocation("Get-Date", { pwshPath: "C:\\pwsh.exe", platform: "win32" });
  assert.equal(seven.program, "C:\\pwsh.exe"); assert.equal(seven.note, null);
  assert.deepEqual(seven.args.slice(0, 4), ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]);
  assert.equal(seven.args.at(-1), "Get-Date");
  const five = pwshInvocation("Get-Date", { pwshPath: null, platform: "win32" });
  assert.equal(five.program, "powershell.exe"); assert.match(five.note, /PowerShell 5/);
  const mac = pwshInvocation("Get-Date", { pwshPath: null, platform: "darwin" });
  assert.equal(mac.program, "pwsh"); assert.equal(mac.note, null);
});

test("long output keeps its tail and says what was dropped", () => {
  assert.equal(capOutput("short"), "short");
  const capped = capOutput("x".repeat(100), 10);
  assert.match(capped, /^\[90 characters dropped\]\n/);
  assert.equal(capped.length, "[90 characters dropped]\n".length + 10);
});
