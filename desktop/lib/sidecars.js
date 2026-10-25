// Start and stop the backend and the UI as child processes, and wait for health.

import { spawn } from "node:child_process";

export class Sidecar {
  constructor(name, { program, args = [], env = {}, cwd, healthUrl, log }) {
    Object.assign(this, { name, program, args, env, cwd, healthUrl, log: log || (() => {}) });
    this.child = null;
  }

  start() {
    if (this.child) return;
    this.child = spawn(this.program, this.args, { cwd: this.cwd, env: { ...process.env, ...this.env }, windowsHide: true });
    this.child.stdout.on("data", (d) => this.log(`[${this.name}] ${d}`));
    this.child.stderr.on("data", (d) => this.log(`[${this.name}] ${d}`));
    this.child.on("exit", (code) => { this.log(`[${this.name}] exited with ${code}`); this.child = null; });
  }

  stop() {
    if (!this.child) return;
    this.child.kill();
    this.child = null;
  }

  get running() {
    return this.child !== null;
  }
}

/** Poll a URL until it answers 2xx or the deadline passes. `fetchFn` is injectable for tests. */
export async function waitForHealth(url, { timeoutMs = 60000, intervalMs = 500, fetchFn = fetch, sleep = (ms) => new Promise((r) => setTimeout(r, ms)) } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetchFn(url);
      if (res.ok) return true;
    } catch {
      // not up yet
    }
    await sleep(intervalMs);
  }
  return false;
}
