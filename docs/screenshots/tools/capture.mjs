// Drives headless Chrome over the DevTools protocol to take the README screenshots.
//   node docs/screenshots/tools/capture.mjs plan.json
// plan.json: [{url, out, width, height, load, clipHeight, fullPage,
//              steps: [{js, wait, until, timeout, log}]}]
// Each step runs `js` in the page, waits `wait` ms, then polls `until` (a JS expression)
// until it is true. Dialogs (the "this is N model calls" confirms) are accepted.
// CHROME overrides the browser path (default: Google Chrome on macOS).
import { spawn } from "node:child_process";
import { writeFileSync, readFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const chrome = spawn(process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--remote-debugging-port=9333", `--user-data-dir=${mkdtempSync(join(tmpdir(), "cdp-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch("http://127.0.0.1:9333/json")).json(); if (targets.length) break; } catch {} await sleep(200); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data);
  if (m.method === "Page.javascriptDialogOpening") { ws.send(JSON.stringify({ id: ++id, method: "Page.handleJavaScriptDialog", params: { accept: true } })); console.log("   dialog accepted:", m.params.message.slice(0, 80)); }
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (js) => { const r = await Promise.race([send("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true }), sleep(15000).then(() => ({}))]); return r.result?.result?.value; };
const HIDE = `(() => { const s = document.createElement('style'); s.textContent = 'nextjs-portal, [data-nextjs-toast], #__next-build-watcher { display: none !important; }'; document.head.appendChild(s); document.querySelectorAll('nextjs-portal').forEach(n => n.remove()); return true; })()`;
await send("Page.enable"); await send("Runtime.enable");
for (const shot of plan) {
  await send("Emulation.setDeviceMetricsOverride", { width: shot.width || 1400, height: shot.height || 900, deviceScaleFactor: shot.scale || 1, mobile: false });
  await send("Page.navigate", { url: shot.url });
  await sleep(shot.load || 3500);
  for (const st of shot.steps || []) {
    const v = await evaluate(st.js); if (st.log) console.log("  ", st.log, JSON.stringify(v)); await sleep(st.wait || 800);
    if (st.until) { const t0 = Date.now(); while (Date.now() - t0 < (st.timeout || 600000)) { if (await evaluate(st.until)) break; await sleep(2000); } console.log("   done after", Math.round((Date.now() - t0) / 1000), "s"); await sleep(1000); }
  }
  await evaluate(HIDE); await sleep(300);
  let clip;
  if (shot.fullPage || shot.clipHeight) {
    const h = await evaluate("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)");
    const height = Math.min(h, shot.clipHeight || h);
    await send("Emulation.setDeviceMetricsOverride", { width: shot.width || 1400, height, deviceScaleFactor: shot.scale || 1, mobile: false });
    await sleep(500);
    clip = { x: 0, y: shot.clipTop || 0, width: shot.width || 1400, height: height - (shot.clipTop || 0), scale: 1 };
  }
  const r = await send("Page.captureScreenshot", { format: "png", ...(clip ? { clip } : {}) });
  writeFileSync(shot.out, Buffer.from(r.result.data, "base64"));
  console.log("wrote", shot.out);
}
ws.close(); chrome.kill();
