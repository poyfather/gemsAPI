// node fetch-out.mjs <port> <out.mp4>: if a run stops after encoding, read the finished file
// (window.OUT) out of the still-open encoder page in small pieces.
import { writeFileSync } from "node:fs";
const [port, out] = process.argv.slice(2);
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = targets.find((t) => t.type === "page" && t.url.includes("encode.html"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 1000; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const ev = (js) => new Promise((r) => { const i = ++id; pending.set(i, (m) => r(m.result?.result?.value)); ws.send(JSON.stringify({ id: i, method: "Runtime.evaluate", params: { expression: js, returnByValue: true } })); });
const len = await ev("window.OUT ? window.OUT.length : 0");
const size = 512 * 1024, parts = [];
for (let i = 0; i * size < len; i++) parts.push(Buffer.from(await ev(`chunk(${i}, ${size})`), "base64"));
const buf = Buffer.concat(parts); writeFileSync(out, buf);
console.log("wrote", out, buf.length, "of", len);
ws.close();
