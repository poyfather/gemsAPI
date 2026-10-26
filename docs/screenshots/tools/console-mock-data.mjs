// Writes mock-data.js and doctor-data.js for a browser preview of the console page, from the
// console's own catalog, recipes and Doctor, with the state of a typical Windows PC.
//   node docs/screenshots/tools/console-mock-data.mjs <preview-dir>
import { fileURLToPath } from "node:url";
const L = fileURLToPath(new URL("../../../desktop/lib", import.meta.url));
const { COMPONENTS } = await import(`${L}/components.js`);
const { TOOLBOX } = await import(`${L}/toolbox.js`);
const R = await import(`${L}/recipes.js`);
const { diagnose, summarise } = await import(`${L}/doctor.js`);
import { writeFileSync } from "node:fs";
const out = process.argv[2];
const status = {
  winget: { installed: true, version: "v1.12.350" }, pwsh: { installed: true, version: "7.5.4", path: "C:\\Program Files\\PowerShell\\7\\pwsh.exe" },
  node: { installed: true, version: "v24.11.0" }, docker: { installed: false }, claude: { installed: true }, chatgpt: { installed: true },
  ollama: { installed: true, running: true, version: "0.40.11", models: ["qwen3:4b"] }, openwebui: { installed: false, running: false },
  rea: { installed: true }, lapidary: { installed: true, running: true },
};
const settings = { modelPolicy: "mix", localModel: "qwen3:4b", anthropicKey: "set", openaiKey: "" };
const plans = {};
for (const c of R.AI_CHOICES) plans[c.id] = R.planAll({ status, settings, choice: c.id, localModel: "qwen3:4b", paths: {} }).map((p) => ({ ...p, summary: R.summarise(p) }));
const comps = COMPONENTS.map(({ id, name, kind, blurb, costs }) => ({ id, name, kind, blurb, costs }));
const tools = TOOLBOX.map((t) => ({ id: t.id, name: t.name, publisher: t.publisher, category: t.category, source: t.source.winget ? `winget ${t.source.winget}` : t.source.psgallery ? `PowerShell Gallery ${t.source.psgallery}` : "command", homepage: t.homepage, blurb: t.blurb, needs: t.needs }));
const adv = R.advancedPlan({ choice: "mix", components: ["pwsh", "ollama", "claude"], storage: "sqlite" }, { status, settings, paths: {} });
const advEmpty = R.advancedPlan({}, { status, settings, paths: {} });
writeFileSync(`${out}/mock-data.js`, "window.MOCK = " + JSON.stringify({ choices: R.AI_CHOICES, plans, components: comps, status, tools, adv, advEmpty }) + ";\n");
const findings = diagnose({ status, settings, keys: { anthropic: "ok", openai: null },
  ports: { 8000: "lapidary", 3000: "lapidary", 3080: "free", 11434: "lapidary" },
  clients: { claude: { exists: true, connected: true }, chatgpt: { exists: true, connected: false } },
  composeExists: false, version: "0.4.0", latest: "0.4.0", helper: { running: true } });
writeFileSync(`${out}/doctor-data.js`, "window.DOCTOR = " + JSON.stringify({ findings, summary: summarise(findings), checkedAt: new Date().toISOString() }) + ";\n");
console.log("plans:", Object.fromEntries(Object.entries(plans).map(([k, v]) => [k, v.length])), "findings:", findings.length, summarise(findings));
