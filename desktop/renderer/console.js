// Console page logic: tiny, no framework. Everything privileged goes through window.lapidary.
const $ = (s) => document.querySelector(s);
const views = ["start", "dashboard", "doctor", "components", "connections", "settings", "logs", "powershell", "lapidary"];
const LAMP = { on: "lamp on", warn: "lamp warn", off: "lamp off" };

function show(view) {
  for (const v of views) $(`#view-${v}`).classList.toggle("hidden", v !== view);
  for (const b of document.querySelectorAll("nav button")) b.classList.toggle("active", b.dataset.view === view);
  if (view === "lapidary" && $("#lapidary-frame").src === "about:blank") $("#lapidary-frame").src = "http://127.0.0.1:3000/gems";
  if (view === "logs") refreshLogs();
  if (view === "components") refreshToolbox();
  if (view === "settings") loadSettings();
  if (view === "start" || view === "dashboard") loadRecipes();
  if (view === "doctor") runDoctor();
  if (view === "connections") window.lapidary.mcp.details().then((d) => { $("#mcp-url").textContent = d.url; });
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
    return `<tr><td><span class="${lampFor(s)}"></span></td><td>${c.name}<span class="blurb">${c.blurb || ""}${c.costs ? ` <span class="costs">${c.costs}.</span>` : ""}</span></td><td class="dim adv-only">${c.kind}</td><td>${stateText(s)}${s.note ? ` <span class="dim">(${s.note})</span>` : ""}</td><td></td></tr>`;
  });
  $("#status-table tbody").innerHTML = rows.join("");
  const inst = components.map((c) => {
    const s = status[c.id] || {};
    const btn = s.installed ? `<button data-install="${c.id}" class="small">update</button>` : `<button data-install="${c.id}" class="small">install</button>`;
    return `<tr><td><span class="${lampFor(s)}"></span></td><td>${c.name}<span class="blurb">${c.blurb || ""}${c.costs ? ` <span class="costs">${c.costs}.</span>` : ""}</span></td><td class="dim">${s.version || ""}</td><td class="path adv-only">${s.path || ""}</td><td class="act">${c.id === "winget" || c.id === "lapidary" ? "" : btn}</td></tr>`;
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
    return `<tr><td><input type="checkbox" data-pick="${t.id}" ${s.installed ? "disabled" : ""}></td><td><span class="${lamp}"></span></td><td>${t.name}<span class="blurb">${t.blurb || ""}${t.needs ? ` <span class="costs">${t.needs}.</span>` : ""}</span></td><td class="dim">${t.publisher}</td><td class="dim adv-only">${t.category}</td><td class="dim adv-only">${t.source}</td><td class="act">${btn}</td></tr>`;
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
  for (const [k, v] of Object.entries(s)) { const f = document.querySelector(`#settings-form [name="${k}"]`); if (f) f.placeholder = v === "set" ? "set (leave blank to keep)" : f.placeholder; if (f && ["gemsApiKey", "supabaseUrl", "localBaseUrl", "localModel", "modelPolicy"].includes(k) && v) f.value = v; }
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

// ---- the Doctor: every finding in plain words, with its fix button where one exists
const DOCTOR_LAMP = { ok: "lamp on", warn: "lamp warn", fail: "lamp off", skip: "lamp" };
async function runDoctor() {
  $("#doctor-msg").textContent = "checking...";
  const r = await window.lapidary.doctor.run();
  const rows = r.findings.map((f) => {
    const btn = f.fix ? `<button data-fix="${esc(f.fix.action)}" class="small">${esc(f.fix.label)}</button>` : "";
    return `<tr><td><span class="${DOCTOR_LAMP[f.state] || "lamp"}"></span></td><td>${esc(f.title)}</td><td class="means">${esc(f.detail)}</td><td class="act">${btn}</td></tr>`;
  });
  $("#doctor-table tbody").innerHTML = rows.join("");
  $("#doctor-msg").textContent = `${r.summary}, ${new Date(r.checkedAt).toLocaleTimeString()}`;
  document.querySelectorAll("[data-fix]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true; $("#doctor-out").textContent = `${b.textContent}...`;
    const res = await window.lapidary.doctor.fix(b.dataset.fix);
    if (res.view) { show(res.view); return; }
    $("#doctor-out").textContent = res.message || (res.ok ? "done" : "that did not work; see Logs");
    await runDoctor();
  }));
}

const actions = {
  "toolbox-install-checked": async () => { for (const c of document.querySelectorAll("[data-pick]:checked")) await installTool(c.dataset.pick); return ""; },
  "pwsh-run": async () => (await runPwsh(), ""),
  "pwsh-clear": async () => (($("#pwsh-out").textContent = ""), ""),
  "restart": async () => (await window.lapidary.restartLapidary(), "Lapidary restarted"),
  "open-ui": async () => (await window.lapidary.open("http://127.0.0.1:3000"), "opened Lapidary UI"),
  "open-webui": async () => (await window.lapidary.open("http://localhost:3080"), "opened Open WebUI"),
  "refresh": async () => (await refresh(), "refreshed"),
  "doctor-run": async () => (await runDoctor(), ""),
  "refresh-logs": async () => (await refreshLogs(), "logs refreshed"),
  "connect-claude": async () => (await window.lapidary.connect.claude()).message,
  "mcp-copy-url": async () => (await window.lapidary.mcp.copy("url")).message,
  "mcp-copy-key": async () => (await window.lapidary.mcp.copy("key")).message,
  "mcp-copy-entry": async () => (await window.lapidary.mcp.copy("entry")).message,
  "mcp-copy-bridge": async () => (await window.lapidary.mcp.copy("bridge")).message,
  "connect-chatgpt": async () => (await window.lapidary.connect.chatgpt()).message,
  "connect-openwebui": async () => (await window.lapidary.connect.openwebui()).message,
};
document.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
  const out = b.closest("#view-connections") ? $("#conn-out") : b.closest("#view-doctor") ? $("#doctor-out") : $("#action-out");
  b.disabled = true;
  try { const msg = await actions[b.dataset.act](); if (msg) out.textContent = msg; } catch (err) { out.textContent = `error: ${err.message}`; }
  b.disabled = false;
}));

// ---- Advanced toggle: one switch that reveals the details on every screen
const advToggle = $("#adv-toggle");
advToggle.checked = localStorage.getItem("advanced") === "yes";
document.body.classList.toggle("adv", advToggle.checked);
advToggle.addEventListener("change", () => { localStorage.setItem("advanced", advToggle.checked ? "yes" : "no"); document.body.classList.toggle("adv", advToggle.checked); });

// ---- first run: Basic (two questions) and Advanced (every choice), then recipes
const first = { choice: null, recipe: null, plans: [], choices: [], stepEls: {} };
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function showStartPanel(id) {
  for (const p of ["start-paths", "start-basic", "start-plan", "start-advanced"]) $(`#${p}`).classList.toggle("hidden", p !== id);
}
document.querySelectorAll("[data-path]").forEach((b) => b.addEventListener("click", () => {
  const path = b.dataset.path;
  if (path === "basic") showStartPanel("start-basic");
  else if (path === "advanced") { showStartPanel("start-advanced"); loadAdvanced(); }
  else showStartPanel("start-paths");
}));
document.querySelectorAll("[data-view-go]").forEach((b) => b.addEventListener("click", () => show(b.dataset.viewGo)));

async function loadRecipes() {
  const r = await window.lapidary.firstRun.recipes(first.choice);
  first.choice = r.choice; first.plans = r.plans; first.choices = r.choices;
  $("#ai-choices").innerHTML = r.choices.map((c) => `<button class="choice ${c.id === r.choice ? "picked" : ""}" data-choice="${c.id}"><b>${esc(c.title)}</b><span>${esc(c.blurb)}</span><span class="tag">${esc(c.privacy)} / ${esc(c.cost)}</span></button>`).join("");
  document.querySelectorAll("[data-choice]").forEach((b) => b.addEventListener("click", async () => { first.choice = b.dataset.choice; await loadRecipes(); }));
  const card = (p) => `<button class="choice" data-recipe="${p.recipe.id}"><b>${esc(p.recipe.title)}</b><span>${esc(p.recipe.blurb)}</span><span class="tag">${esc(p.summary)}</span></button>`;
  $("#recipe-choices").innerHTML = r.plans.map(card).join("");
  $("#dash-recipes").innerHTML = r.plans.map(card).join("");
  document.querySelectorAll("[data-recipe]").forEach((b) => b.addEventListener("click", () => showPlan(b.dataset.recipe)));
}

function stepItem(s) {
  const li = document.createElement("li");
  li.className = s.done ? "done" : (s.skipWhen ? "skipped" : "");
  li.innerHTML = `<span class="lamp ${s.done ? "on" : ""}"></span><div><div class="text">${esc(s.text)}${s.optional ? " <span class=\"dim\">(optional)</span>" : ""}</div><div class="detail">${esc(s.detail)}</div><div class="msg">${s.done ? "already here" : esc(s.skipWhen || "")}</div></div>`;
  return li;
}
function renderSteps(list, steps) {
  list.innerHTML = ""; first.stepEls = {};
  for (const s of steps) { const li = stepItem(s); first.stepEls[s.id] = li; list.appendChild(li); }
}
window.lapidary.firstRun.onProgress((ev) => {
  const li = first.stepEls[ev.step]; if (!li) return;
  li.className = ev.state;
  const lamp = li.querySelector(".lamp"); lamp.className = `lamp ${ev.state === "done" || ev.state === "skipped" ? "on" : ev.state === "failed" ? "off" : ""}`;
  li.querySelector(".msg").textContent = ev.message || (ev.state === "running" ? "working..." : "");
});

function showPlan(recipeId) {
  const p = first.plans.find((x) => x.recipe.id === recipeId); if (!p) return;
  first.recipe = recipeId;
  show("start"); showStartPanel("start-plan");
  $("#plan-title").textContent = p.recipe.title.toUpperCase();
  renderSteps($("#plan-steps"), p.steps);
  $("#plan-key").classList.toggle("hidden", !p.steps.some((s) => s.kind === "key" && !s.done));
  $("#plan-out").classList.add("hidden"); $("#plan-now").classList.add("hidden"); $("#plan-go").disabled = false;
}
$("#plan-back").addEventListener("click", () => showStartPanel("start-basic"));
$("#plan-another").addEventListener("click", async () => { await loadRecipes(); showStartPanel("start-basic"); });
$("#plan-go").addEventListener("click", async () => {
  const p = first.plans.find((x) => x.recipe.id === first.recipe); if (!p) return;
  $("#plan-go").disabled = true;
  const keys = { anthropicKey: $("#plan-anthropic").value.trim(), openaiKey: $("#plan-openai").value.trim() };
  $("#plan-anthropic").value = ""; $("#plan-openai").value = ""; $("#plan-key").classList.add("hidden");
  const out = $("#plan-out"); out.classList.remove("hidden"); out.textContent = "working, this can take a few minutes (downloads and installers)...";
  const r = await window.lapidary.firstRun.run(first.recipe, first.choice, keys);
  if (r.ok) {
    out.textContent = "done";
    $("#plan-now-list").innerHTML = p.now.map((t) => `<li>${esc(t)}</li>`).join("");
    $("#plan-now").classList.remove("hidden");
  } else {
    out.textContent = `stopped at "${r.failed}": ${r.message}\nFix that and press Do it again; finished steps are skipped.`;
    $("#plan-go").disabled = false;
  }
  refresh();
});

async function loadAdvanced() {
  const { components, status } = await window.lapidary.components();
  $("#adv-components").innerHTML = components.filter((c) => !["winget", "lapidary", "rea"].includes(c.id)).map((c) => {
    const s = status[c.id] || {};
    return `<label class="row"><input type="checkbox" name="components" value="${c.id}" ${s.installed ? "checked disabled" : ""}> ${esc(c.name)} <span class="dim">${s.installed ? "installed" : esc(c.blurb || "")}</span></label>`;
  }).join("");
  const r = await window.lapidary.firstRun.recipes(first.choice);
  $("#adv-ai").innerHTML = r.choices.map((c) => `<label class="row"><input type="radio" name="choice" value="${c.id}" ${c.id === r.choice ? "checked" : ""}> ${esc(c.title)} <span class="dim">${esc(c.blurb)}</span></label>`).join("");
  const plan = await window.lapidary.firstRun.advancedPlan({});
  $("#adv-ports").textContent = `Lapidary API  127.0.0.1:${plan.ports.lapidary}\nLapidary UI   127.0.0.1:${plan.ports.ui}\nOpen WebUI    localhost:${plan.ports.openwebui}\nOllama        127.0.0.1:${plan.ports.ollama}\nData folder   ${plan.dataDir}\nPorts are fixed in this version; the data folder follows the Windows AppData rules.`;
  $("#adv-summary").classList.add("hidden");
}
function advancedAnswers() {
  const f = $("#adv-form");
  const fd = new FormData(f);
  const all = (name) => Array.from(f.querySelectorAll(`[name="${name}"]:checked`)).map((i) => i.value);
  return {
    components: all("components").filter((id) => !f.querySelector(`[name="components"][value="${id}"]`).disabled),
    choice: fd.get("choice") || "auto",
    keys: { anthropicKey: fd.get("anthropicKey") || "", openaiKey: fd.get("openaiKey") || "" },
    localBaseUrl: fd.get("localBaseUrl") || "", localModel: fd.get("localModel") || "",
    storage: fd.get("storage") || "sqlite", supabaseUrl: fd.get("supabaseUrl") || "", supabaseKey: fd.get("supabaseKey") || "",
    connect: all("connect"),
  };
}
$("#adv-review").addEventListener("click", async () => {
  const plan = await window.lapidary.firstRun.advancedPlan(advancedAnswers());
  $("#adv-writes").innerHTML = plan.writes.map((w) => `<li>${esc(w)}</li>`).join("") || "<li>nothing</li>";
  $("#adv-commands").innerHTML = plan.commands.map((c) => `<li class="mono">${esc(c)}</li>`).join("") || "<li>nothing</li>";
  renderSteps($("#adv-steps"), plan.steps);
  $("#adv-summary").classList.remove("hidden"); $("#adv-out").classList.add("hidden"); $("#adv-go").disabled = false;
  $("#adv-summary").scrollIntoView({ behavior: "smooth" });
});
$("#adv-edit").addEventListener("click", () => $("#adv-summary").classList.add("hidden"));
$("#adv-go").addEventListener("click", async () => {
  $("#adv-go").disabled = true;
  const answers = advancedAnswers();
  for (const i of $("#adv-form").querySelectorAll("input[type=password]")) i.value = "";
  const out = $("#adv-out"); out.classList.remove("hidden"); out.textContent = "applying...";
  const r = await window.lapidary.firstRun.advancedRun(answers);
  out.textContent = r.ok ? "done; the dashboard shows the result" : `stopped at "${r.failed}": ${r.message}`;
  if (!r.ok) $("#adv-go").disabled = false;
  refresh();
});

setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString(); }, 1000);
window.lapidary.onReady(() => refresh());
refresh();
window.lapidary.firstRun.recipes(null).then((r) => { if (r.firstRunDone) show("dashboard"); else show("start"); });
