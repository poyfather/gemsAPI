import { test } from "node:test";
import assert from "node:assert/strict";
import { waitForHealth } from "../lib/sidecars.js";

test("waitForHealth returns true once the endpoint answers and false at the deadline", async () => {
  let calls = 0;
  const fetchFn = async () => { calls += 1; if (calls < 3) throw new Error("refused"); return { ok: true }; };
  const sleep = async () => {};
  assert.equal(await waitForHealth("http://x/health", { timeoutMs: 1000, fetchFn, sleep }), true);
  assert.equal(calls, 3);
  const never = async () => ({ ok: false });
  assert.equal(await waitForHealth("http://x/health", { timeoutMs: 1, intervalMs: 1, fetchFn: never }), false);
});
