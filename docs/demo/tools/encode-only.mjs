// Re-encodes frames already drawn by render.mjs, for example at 1280x720 for the repository,
// or after copying the poster frame over f00000.jpg so it becomes the thumbnail.
//   node encode-only.mjs <out.mp4> <framesDir> <nFrames> <fps> <w> <h> <bitrate> <audio|none>
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const [out, framesDir, nArg, fpsArg, wArg, hArg, brArg, audio] = process.argv.slice(2);
const chrome = spawn(process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", "--disable-gpu", "--remote-debugging-port=9335", `--user-data-dir=${mkdtempSync(join(tmpdir(), "enc-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets; for (let i = 0; i < 50; i++) { try { targets = await (await fetch("http://127.0.0.1:9335/json")).json(); if (targets.length) break; } catch {} await sleep(200); }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (js) => { const r = await send("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true }); if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400)); return r.result?.result?.value; };
await send("Page.navigate", { url: "http://localhost:8766/demo/tools/encode.html" }); await sleep(1200);
await ev(`window.JOB = encode(${+nArg}, ${+fpsArg}, ${+wArg}, ${+hArg}, ${JSON.stringify(framesDir)}, ${audio === "none" ? "null" : JSON.stringify(audio)}, ${+brArg}).then((n) => (window.LEN = n), (e) => (window.ERR = String((e && e.stack) || e))), true`);
let len;
for (let k = 0; k < 720; k++) {
  await sleep(5000);
  const st = await ev("JSON.stringify({p: window.PROG, len: window.LEN, err: window.ERR})");
  console.log(st); const o = JSON.parse(st);
  if (o.err) throw new Error(o.err);
  if (o.len) { len = o.len; break; }
}
const size = 512 * 1024, parts = [];
for (let i = 0; i * size < len; i++) parts.push(Buffer.from(await ev(`chunk(${i}, ${size})`), "base64"));
writeFileSync(out, Buffer.concat(parts)); console.log("wrote", out, len, "bytes");
ws.close(); chrome.kill();
