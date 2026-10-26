// Renders the README demo video. Serve docs/ first:  python3 -m http.server 8766 --directory docs
// then, in docs/demo/tools (after `npm install mp4-muxer@5` and `python music.py music.wav`):
//   node render.mjs out.mp4 [fps] [from] [to] [framesDir] [audio|none]
// Draws scene.html frame by frame (each frame a pure function of time), then encodes in the browser
// with WebCodecs (H.264 and AAC) and mp4-muxer. CHROME overrides the browser path.
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
const [out, fpsArg = "30", fromArg = "0", toArg = "64", framesDir = "frames", audio = "music.wav"] = process.argv.slice(2);
const fps = +fpsArg, from = +fromArg, to = +toArg, BASE = "http://localhost:8766/demo/tools";
const DIR = fileURLToPath(new URL(".", import.meta.url));
mkdirSync(join(DIR, framesDir), { recursive: true });
const chrome = spawn(process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1", "--remote-debugging-port=9334", `--user-data-dir=${mkdtempSync(join(tmpdir(), "rend-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets; for (let i = 0; i < 50; i++) { try { targets = await (await fetch("http://127.0.0.1:9334/json")).json(); if (targets.length) break; } catch {} await sleep(200); }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (js) => { const r = await send("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true }); if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400)); return r.result?.result?.value; };
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: `${BASE}/scene.html` }); await sleep(1500); await ev("window.ready.then(() => true)");
const n = Math.round((to - from) * fps);
const t0 = Date.now();
for (let i = 0; i < n; i++) {
  await ev(`render(${from + i / fps})`);
  const r = await send("Page.captureScreenshot", { format: "jpeg", quality: 94, clip: { x: 0, y: 0, width: 1920, height: 1080, scale: 1 } });
  writeFileSync(join(DIR, framesDir, `f${String(i).padStart(5, "0")}.jpg`), Buffer.from(r.result.data, "base64"));
  if (i % 150 === 0) console.log(`frame ${i}/${n} ${Math.round((Date.now() - t0) / 1000)}s`);
}
await send("Page.navigate", { url: `${BASE}/encode.html` }); await sleep(1200);
const len = await ev(`encode(${n}, ${fps}, 1920, 1080, ${JSON.stringify(framesDir)}, ${audio === "none" ? "null" : JSON.stringify(audio)})`);
const size = 512 * 1024, parts = [];
for (let i = 0; i * size < len; i++) parts.push(Buffer.from(await ev(`chunk(${i}, ${size})`), "base64"));
writeFileSync(out, Buffer.concat(parts));
console.log("wrote", out, len, "bytes in", Math.round((Date.now() - t0) / 1000), "s");
ws.close(); chrome.kill();
