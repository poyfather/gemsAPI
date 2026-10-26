// Stands in for the console's preload bridge (window.lapidary) so the console page can be
// opened in a browser for screenshots. Data comes from console-mock-data.mjs. Nothing is installed.
const M = window.MOCK; let choice = "mix"; let progressCb = null; const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function runSteps(steps) { for (const s of steps) { if (s.done || s.skipWhen) { progressCb({ step: s.id, state: "skipped", message: s.done ? "already here" : s.skipWhen }); continue; } progressCb({ step: s.id, state: "running" }); await sleep(600); progressCb({ step: s.id, state: "done", message: s.kind === "pull" ? "downloaded" : s.kind === "key" ? "key saved" : "done" }); } return { ok: true, results: [] }; }
window.lapidary = {
  components: async () => ({ components: M.components, status: M.status }),
  toolbox: async () => ({ tools: M.tools, status: { git: { installed: true, path: "C:\\git.exe" } } }), install: async () => ({ ok: true, message: "installed" }),
  settings: { get: async () => ({ modelPolicy: choice, localModel: "qwen3:4b", gemsApiKey: "abc" }), set: async () => ({ ok: true, note: "saved" }) },
  connect: { claude: async () => ({ message: "wrote config" }), chatgpt: async () => ({ message: "wrote config" }), openwebui: async () => ({ message: "started" }) },
  restartLapidary: async () => ({ ok: true }), logs: async () => ["12:00:00 preview"], pwsh: async () => ({ code: 0, output: "preview", error: "" }), open: async () => ({ ok: true }), onReady: () => {},
  doctor: { run: async () => window.DOCTOR, fix: async (a) => (a.startsWith("view:") ? { ok: true, view: a.slice(5) } : { ok: true, message: `${a}: done (preview)` }) },
  firstRun: {
    recipes: async (c) => { if (c) choice = c; return { choices: M.choices, plans: M.plans[choice], choice, firstRunDone: false, localModel: "qwen3:4b" }; },
    run: async (id) => runSteps(M.plans[choice].find((p) => p.recipe.id === id).steps),
    advancedPlan: async (a) => (a && a.choice ? M.adv : M.advEmpty), advancedRun: async () => runSteps(M.adv.steps), done: async () => ({ ok: true }),
    onProgress: (cb) => { progressCb = cb; },
  },
};
