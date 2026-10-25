// Console page logic: tiny, no framework. Everything privileged goes through window.lapidary.
const $ = (s) => document.querySelector(s);
const views = ["dashboard", "components", "connections", "settings", "logs", "powershell", "lapidary"];
const LAMP = { on: "lamp on", warn: "lamp warn", off: "lamp off" };

function show(view) {
  for (const v of views) $(`#view-${v}`).classList.toggle("hidden", v !== view);
  for (const b of document.querySelectorAll("nav button")) b.classList.toggle("active", b.dataset.view === view);
  if (view === "lapidary" && $("#lapidary-frame").src === "about:blank") $("#lapidary-frame").src = "http://127.0.0.1:3000/gems";
  if (view === "logs") refreshLogs();
  if (view === "components") refreshToolbox();
  if (view === "settings") loadSettings();
}
document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
document.addEventListener("keydown", (e) => {
  if (e.target.id === "pwsh-in" && e.key === "Enter" && e.ctrlKey) { e.preventDefault(); runPwsh(); return; }
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  const i = Number(e.key) - 1;
  if (i >= 0 && i < views.length) show(views[i]);
  if (e.key.toLowerCase() === "r") refresh();
});

function lampFor(s) {
  if (!s || !s.installed) return LAMP.off;
  if ("running" in s && !s.running) return LAMP.warn;
  return LAMP.on;
}
function stateText(s) {
  if (!s || !s.installed) return "missing";
  if ("running" in s) return s.running ? "running" : "installed, not running";
  return s.configured === false ? "installed, no config yet" : "installed";
}

async function refresh() {
  $("#foot-msg").textContent = "detecting...";
  const { components, status } = await window.lapidary.components();
  const rows = components.map((c) => {
    const s = status[c.id] || {};
    return `<tr><td><span class="${lampFor(s)}"></span></td><td>${c.name}</td><td class="dim">${c.kind}</td><td>${stateText(s)}${s.note ? ` <span class="dim">(${s.note})</span>` : ""}</td><td></td></tr>`;
  });
  $("#status-table tbody").innerHTML = rows.join("");
  const inst = components.map((c) => {
    const s = status[c.id] || {};
    const btn = s.installed ? `<button data-install="${c.id}" class="small">update</button>` : `<button data-install="${c.id}" class="small">install</button>`;
    return `<tr><td><span class="${lampFor(s)}"></span></td><td>${c.name}</td><td class="dim">${s.version || ""}</td><td class="path">${s.path || ""}</td><td class="act">${c.id === "winget" || c.id === "lapidary" ? "" : btn}</td></tr>`;
  });
  $("#install-table tbody").innerHTML = inst.join("");
  document.querySelectorAll("[data-install]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true; $("#foot-msg").textContent = `installing ${b.dataset.install}...`;
    const r = await window.lapidary.install(b.dataset.install);
    $("#foot-msg").textContent = `${b.dataset.install}: ${r.message}`;
    b.disabled = false; refresh();
  }));
  $("#foot-msg").textContent = `ready, ${new Date().toLocaleTimeString()}`;
}

async function refreshToolbox() {
  const { tools, status } = await window.lapidary.toolbox();
  const rows = tools.map((t) => {
    const s = status[t.id] || {};
    const lamp = s.installed === null ? "lamp" : (s.installed ? LAMP.on : LAMP.off);
    const btn = s.installed ? `<span class="dim">installed</span>` : `<button data-toolbox="${t.id}" class="small">install</button>`;
    return `<tr><td><input type="checkbox" data-pick="${t.id}" ${s.installed ? "disabled" : ""}></td><td><span class="${lamp}"></span></td><td>${t.name}</td><td class="dim">${t.publisher}</td><td class="dim">${t.category}</td><td class="dim">${t.source}</td><td class="act">${btn}</td></tr>`;
  });
  $("#toolbox-table tbody").innerHTML = rows.join("");
  document.querySelectorAll("[data-toolbox]").forEach((b) => b.addEventListener("click", () => installTool(b.dataset.toolbox)));
}

async function installTool(id) {
  $("#toolbox-msg").textContent = `installing ${id}...`;
  const r = await window.lapidary.install(id);
  $("#toolbox-msg").textContent = `${id}: ${r.message}`;
  await refreshToolbox();
}

async function refreshLogs() {
  const lines = await window.lapidary.logs();
  const el = $("#logs"); el.textContent = lines.join("\n"); el.scrollTop = el.scrollHeight;
}

async function loadSettings() {
  const s = await window.lapidary.settings.get();
  for (const [k, v] of Object.entries(s)) { const f = document.querySelector(`[name="${k}"]`); if (f) f.placeholder = v === "set" ? "set (leave blank to keep)" : f.placeholder; if (f && k === "gemsApiKey") f.value = v || ""; if (f && k === "supabaseUrl") f.value = v || ""; }
}
$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const patch = Object.fromEntries(new FormData(e.target).entries());
  for (const k of Object.keys(patch)) if (!patch[k]) delete patch[k];
  const r = await window.lapidary.settings.set(patch);
  $("#settings-out").textContent = r.note || "saved";
  e.target.reset(); loadSettings();
});

async function runPwsh() {
  const script = $("#pwsh-in").value.trim();
  if (!script) return;
  const out = $("#pwsh-out");
  out.textContent += `PS> ${script}\n`;
  const r = await window.lapidary.pwsh(script);
  if (r.note) $("#pwsh-note").textContent = r.note;
  out.textContent += (r.output || "") + (r.error ? `\n${r.error}` : "") + `\n[exit ${r.code}]\n\n`;
  out.scrollTop = out.scrollHeight;
}

const actions = {
  "toolbox-install-checked": async () => { for (const c of document.querySelectorAll("[data-pick]:checked")) await installTool(c.dataset.pick); return ""; },
  "pwsh-run": async () => (await runPwsh(), ""),
  "pwsh-clear": async () => (($("#pwsh-out").textContent = ""), ""),
  "restart": async () => (await window.lapidary.restartLapidary(), "Lapidary restarted"),
  "open-ui": async () => (await window.lapidary.open("http://127.0.0.1:3000"), "opened Lapidary UI"),
  "open-webui": async () => (await window.lapidary.open("http://localhost:3080"), "opened Open WebUI"),
  "refresh": async () => (await refresh(), "refreshed"),
  "refresh-logs": async () => (await refreshLogs(), "logs refreshed"),
  "connect-claude": async () => (await window.lapidary.connect.claude()).message,
  "connect-chatgpt": async () => (await window.lapidary.connect.chatgpt()).message,
  "connect-openwebui": async () => (await window.lapidary.connect.openwebui()).message,
};
document.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
  const out = b.closest("#view-connections") ? $("#conn-out") : $("#action-out");
  b.disabled = true;
  try { const msg = await actions[b.dataset.act](); if (msg) out.textContent = msg; } catch (err) { out.textContent = `error: ${err.message}`; }
  b.disabled = false;
}));

setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString(); }, 1000);
window.lapidary.onReady(() => refresh());
refresh();
