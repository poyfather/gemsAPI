// The guided first run (ADR-012, roadmap item 47): two questions in plain words,
// then recipes that turn an answer into an ordered list of steps the console
// can run. Everything here is data and pure functions so it is tested on any
// platform; main.js runs the steps and the page shows them.
//
// A step is { id, kind, text, detail?, done, optional? }:
//   kind    install | start | pull | key | policy | connect | open | note
//   text    what the person reads ("Install Ollama, the free AI that runs on this PC")
//   detail  what the console will actually run or write, shown on the Advanced path
//   done    already true on this machine, so the runner skips it

import { COMPONENTS, installCommand } from "./components.js";

/** A small, general model that fits most PCs. One constant so Advanced can change it in Settings. */
export const DEFAULT_LOCAL_MODEL = "qwen3:4b";
export const DEFAULT_LOCAL_MODEL_SIZE = "about 2.5 GB, downloaded once";

/** Question one: "Which AI should we use?" The id is the backend's GEMS_MODEL_POLICY value. */
export const AI_CHOICES = [
  { id: "mix", title: "A mix (recommended)", blurb: "Online for the hard thinking, the free one on this PC for everyday work. Needs a key for the online part; costs less than all online.", privacy: "everyday work stays here, hard questions go online", cost: "paid by use for the online part", recommended: true },
  { id: "local", title: "The free one on this PC", blurb: "Private: nothing leaves this computer. Works offline. Free. Slower than the cloud and not as clever, good enough for a lot.", privacy: "nothing leaves this PC", cost: "free" },
  { id: "online", title: "The online ones", blurb: "Claude and ChatGPT: the smartest and the fastest. Paid by use with your own key, and what you type is sent to their servers.", privacy: "what you type is sent to Anthropic or OpenAI", cost: "paid by use" },
  { id: "auto", title: "Decide for me", blurb: "Uses whatever is set up, picks per task, and always says which one it picked.", privacy: "depends on what is set up", cost: "free until you add a key" },
  { id: "manual", title: "I'll choose each time", blurb: "Every prompt and assistant keeps the AI you give it. For people who know what they want.", privacy: "your call each time", cost: "your call each time" },
];

/**
 * Question two: "What would you like?" Each recipe says what it needs in terms the
 * planner understands: components, a model on this PC, a cloud key, connections,
 * prompts and assistants that must exist, and what to open at the end.
 */
export const RECIPES = [
  {
    id: "private-chat", title: "A private chat on this PC",
    blurb: "Like ChatGPT, but it runs here. Free, nothing leaves the computer, works without internet.",
    needs: { components: ["docker", "openwebui"], model: true, connect: ["openwebui"] },
    open: { url: "http://localhost:3080", label: "Open the chat" },
    now: ["Ask it anything in the chat that opened. The first answer takes a moment while the model loads.", "Everything you type stays on this PC."],
  },
  {
    id: "homework", title: "Help with homework, writing and everyday questions",
    blurb: "The same private chat with ready-made helpers: a study buddy, a writing coach and a summariser.",
    needs: { components: ["docker", "openwebui"], model: true, connect: ["openwebui"], gems: ["study_buddy", "writing_coach", "summarizer"] },
    open: { url: "http://localhost:3080", label: "Open the chat" },
    now: ["In the chat, pick study_buddy, writing_coach or summarizer from the model list at the top.", "study_buddy explains and quizzes instead of doing the homework for you; writing_coach edits and explains the edits."],
  },
  {
    id: "my-documents", title: "Summarise or ask questions about my own documents, privately",
    blurb: "Drop in PDFs, notes or web pages and ask across them. Everything stays on this PC.",
    needs: { components: ["docker", "openwebui"], model: true, connect: ["openwebui"] },
    open: { url: "http://localhost:3080/workspace/knowledge", label: "Open my documents" },
    now: ["Add a collection, drop your files in, then start a chat and type # to pick the collection.", "Ask for a summary, a list of dates, or a question the documents answer; the answer quotes them."],
  },
  {
    id: "research", title: "A research assistant over my own sources",
    blurb: "Collect sources, ask across them, get answers that cite them, and summaries. On this PC, or with online help for the hard parts.",
    needs: { components: ["docker", "openwebui"], model: true, connect: ["openwebui"], gems: ["research_assistant"], keyOptional: true },
    open: { url: "http://localhost:3080/workspace/knowledge", label: "Open my sources" },
    now: ["Put your sources in a collection, then chat with research_assistant and pick the collection with #.", "It answers only from your sources, cites each one, and says when they do not cover the question.", "With a cloud key and the mix setting, the hard questions go to the online AI and the rest stays here."],
  },
  {
    id: "build-program", title: "Build me a program",
    blurb: "Describe what you want; an assistant plans it, writes it and tests it, asking before anything runs. The free model does the typing, an online one the planning when you have a key.",
    needs: { components: ["pwsh"], model: true, gems: ["program_builder"], keyOptional: true },
    open: { url: "http://127.0.0.1:3000/chat?gem=program_builder", label: "Open the builder" },
    now: ["Describe the program in plain words: what it does, where files should go.", "Every command it wants to run is shown first; nothing runs until you approve it.", "Review gates, tests and a visual check are coming (roadmap item 45)."],
  },
  {
    id: "my-prompts", title: "Let Claude and ChatGPT use my prompts",
    blurb: "Your prompts and assistants show up inside Claude Desktop and ChatGPT. Those apps are paid by use with your own account.",
    needs: { components: ["claude", "chatgpt"], connect: ["claude", "chatgpt"], anyClient: true },
    open: { url: "http://127.0.0.1:3000/gems", label: "Open my prompts" },
    now: ["Restart Claude Desktop or ChatGPT; a tools icon appears in the chat box with Lapidary and REA in it.", "Ask the app to list your gems, or to use one by name."],
  },
  {
    id: "powershell-helper", title: "An assistant that can run safe PowerShell for me",
    blurb: "Ask in plain words, it proposes the command, you approve, it runs. Nothing runs without your yes.",
    needs: { components: ["pwsh"], model: true, gems: ["windows_operator"] },
    open: { url: "http://127.0.0.1:3000/chat?gem=windows_operator", label: "Open the assistant" },
    now: ["Try: how much free disk space do I have, or which programs start with Windows.", "Each command appears with Approve and Deny before it runs, and Logs keeps everything it ran."],
  },
  {
    id: "understand-app", title: "Understand how an app works",
    blurb: "Point it at a program or file you own and it explains what is inside, with evidence. For the curious and for IT.",
    needs: { components: ["node", "rea"], model: true, gems: ["rea_analyst"] },
    open: { url: "http://127.0.0.1:3000/chat?gem=rea_analyst", label: "Open the analyst" },
    now: ["Give it the path to a program or file you own and what you want to know.", "It works from evidence it can show you, and says what it could not see."],
  },
];

const componentName = (id) => COMPONENTS.find((c) => c.id === id)?.name || id;

function hasKey(settings) {
  return Boolean(settings.anthropicKey || settings.openaiKey);
}

function describeInstall(id) {
  const cmd = installCommand(id);
  return cmd ? `${cmd.program} ${cmd.args.join(" ")}` : "";
}

/**
 * Turn a recipe plus the answer to question one into steps for this machine.
 * `status` is detectAll's result, `settings` the console settings (keys are "set" or ""),
 * `choice` an AI_CHOICES id. Steps already satisfied are marked done, not dropped,
 * so the page can show "already here".
 */
export function plan(recipeId, { status = {}, settings = {}, choice = "mix", localModel = DEFAULT_LOCAL_MODEL } = {}) {
  const recipe = RECIPES.find((r) => r.id === recipeId);
  if (!recipe) throw new Error(`unknown recipe ${recipeId}`);
  const steps = [];
  const st = (id) => status[id] || {};
  const n = recipe.needs;

  // A model: on this PC (Ollama plus a download) unless the person chose online only.
  const localWanted = n.model && choice !== "online";
  const cloudWanted = n.model && (choice === "online" || choice === "mix");
  if (localWanted) {
    steps.push({ id: "install:ollama", kind: "install", text: "Install Ollama, the free AI that runs on this PC", detail: describeInstall("ollama"), done: Boolean(st("ollama").installed) });
    steps.push({ id: "start:ollama", kind: "start", text: "Start Ollama", detail: "ollama serve, then wait for http://127.0.0.1:11434", done: Boolean(st("ollama").running) });
    const models = st("ollama").models || [];
    steps.push({ id: `pull:${localModel}`, kind: "pull", text: `Download a small model, ${localModel} (${DEFAULT_LOCAL_MODEL_SIZE})`, detail: `ollama pull ${localModel}`, done: models.some((m) => m === localModel || m.startsWith(`${localModel}:`) || localModel.startsWith(`${m}:`)) });
  }
  if (cloudWanted) {
    steps.push({ id: "key", kind: "key", text: "Add your Anthropic or OpenAI key (paid by use, from your own account)", detail: "stored with the operating system's credential encryption, never shown again", done: hasKey(settings) });
  } else if (n.keyOptional || (n.model && (choice === "auto" || choice === "manual"))) {
    steps.push({ id: "key", kind: "key", text: "Optional: add a cloud key so the hard parts can go online", detail: "stored encrypted; without it everything runs on this PC", done: hasKey(settings), optional: true });
  }

  for (const id of n.components || []) {
    if (id === "openwebui") continue;  // started by its connect step
    if (id === "pwsh" && st("pwsh").installed === false) {
      steps.push({ id: "install:pwsh", kind: "install", text: "Install PowerShell 7 (Windows PowerShell 5 works until then)", detail: describeInstall("pwsh"), done: false, optional: true });
      continue;
    }
    if (id === "rea") continue;  // bundled with the console
    if (n.anyClient && ["claude", "chatgpt"].includes(id)) {
      steps.push({ id: `install:${id}`, kind: "install", text: `Install ${componentName(id)}`, detail: describeInstall(id), done: Boolean(st(id).installed), optional: true });
      continue;
    }
    steps.push({ id: `install:${id}`, kind: "install", text: `Install ${componentName(id)}`, detail: describeInstall(id), done: Boolean(st(id).installed) });
  }

  if (n.model) {
    steps.push({ id: `policy:${choice}`, kind: "policy", text: `Set the AI to "${AI_CHOICES.find((c) => c.id === choice)?.title || choice}"`, detail: `GEMS_MODEL_POLICY=${choice}, GEMS_LOCAL_DEFAULT_MODEL=${localModel}, then restart Lapidary`, done: settings.modelPolicy === choice && (!localWanted || settings.localModel === localModel) });
  }

  for (const target of n.connect || []) {
    if (target === "openwebui") {
      steps.push({ id: "connect:openwebui", kind: "connect", text: "Start the private chat (Open WebUI) and point it at Lapidary and Ollama", detail: "writes open-webui.compose.yml in the Lapidary data folder and runs docker compose up -d", done: Boolean(st("openwebui").running) });
    } else {
      // Sharing prompts needs at least one app; one that is not installed is skipped, one that is gets connected.
      const absent = Boolean(n.anyClient) && !st(target).installed;
      steps.push({ id: `connect:${target}`, kind: "connect", text: `Connect ${componentName(target)} to your prompts`, detail: `adds lapidary and rea to the app's MCP config file`, done: Boolean(st(target).configured), optional: absent, skipWhen: absent ? `${componentName(target)} is not installed` : undefined });
    }
  }

  for (const g of n.gems || []) {
    steps.push({ id: `gem:${g}`, kind: "note", text: `The ${g.replace(/_/g, " ")} assistant comes with Lapidary`, detail: `seed gem ${g}`, done: true });
  }

  if (recipe.open) steps.push({ id: "open", kind: "open", text: recipe.open.label, detail: recipe.open.url, done: false });
  return { recipe, choice, steps, now: recipe.now };
}

/** Plans for every recipe on this machine, for the page to show "ready" or "n steps". */
export function planAll(ctx) {
  return RECIPES.map((r) => plan(r.id, ctx));
}

/** One line per plan: how much is left to do. */
export function summarise(p) {
  const todo = p.steps.filter((s) => !s.done && !s.optional && s.kind !== "open" && !s.skipWhen);
  if (todo.length === 0) return "ready now";
  return `${todo.length} step${todo.length === 1 ? "" : "s"}`;
}

/**
 * The Advanced path: a system administrator's answers become steps plus the list
 * of every file the console will write and every command it will run, shown before
 * anything happens. `answers` is { components: [ids], choice, keys: {anthropicKey, openaiKey},
 * localBaseUrl, localModel, storage: "sqlite"|"supabase", supabaseUrl, supabaseKey, connect: [ids] }.
 * `paths` comes from components.paths().
 */
export function advancedPlan(answers, { status = {}, settings = {}, paths = {} } = {}) {
  const st = (id) => status[id] || {};
  const steps = [];
  const writes = [];
  const commands = [];
  const dataDir = paths.consoleData || "the Lapidary data folder";
  const choice = answers.choice || "auto";
  const localModel = answers.localModel || DEFAULT_LOCAL_MODEL;

  for (const id of answers.components || []) {
    const cmd = installCommand(id);
    if (!cmd) continue;
    const done = Boolean(st(id).installed);
    steps.push({ id: `install:${id}`, kind: "install", text: `Install ${componentName(id)}`, detail: describeInstall(id), done });
    if (!done) commands.push(describeInstall(id));
  }
  const wantsLocal = (answers.components || []).includes("ollama") || ["local", "mix"].includes(choice);
  if (wantsLocal) {
    steps.push({ id: "start:ollama", kind: "start", text: "Start Ollama", detail: "ollama serve", done: Boolean(st("ollama").running) });
    const models = st("ollama").models || [];
    const pulled = models.some((m) => m === localModel || m.startsWith(`${localModel}:`));
    steps.push({ id: `pull:${localModel}`, kind: "pull", text: `Download the local model ${localModel}`, detail: `ollama pull ${localModel}`, done: pulled });
    if (!pulled) commands.push(`ollama pull ${localModel}`);
  }

  const patch = { modelPolicy: choice, localModel };
  if (answers.localBaseUrl) patch.localBaseUrl = answers.localBaseUrl;
  for (const k of ["anthropicKey", "openaiKey"]) if (answers.keys?.[k]) patch[k] = answers.keys[k];
  if (answers.storage === "supabase" && answers.supabaseUrl && answers.supabaseKey) { patch.supabaseUrl = answers.supabaseUrl; patch.supabaseKey = answers.supabaseKey; }
  steps.push({ id: `policy:${choice}`, kind: "policy", patch, text: `Save the settings: AI "${AI_CHOICES.find((c) => c.id === choice)?.title || choice}", ${answers.storage === "supabase" ? "Supabase" : "SQLite on this PC"}${patch.anthropicKey || patch.openaiKey ? ", cloud keys" : ""}`, detail: `settings.bin (encrypted) in ${dataDir}; GEMS_MODEL_POLICY=${choice}`, done: false });
  writes.push(`${dataDir}: settings.bin (encrypted settings and keys), mcp_servers.json, ${answers.storage === "supabase" ? "no database file (Supabase is used)" : "lapidary.db (SQLite)"}`);

  for (const target of answers.connect || []) {
    if (target === "claude") { steps.push({ id: "connect:claude", kind: "connect", text: "Register Lapidary and REA in Claude Desktop", detail: paths.claudeConfig || "claude_desktop_config.json", done: Boolean(st("claude").configured) }); writes.push(`${paths.claudeConfig || "claude_desktop_config.json"}: mcpServers.lapidary and mcpServers.rea (other entries kept)`); }
    if (target === "chatgpt") { steps.push({ id: "connect:chatgpt", kind: "connect", text: "Register Lapidary and REA in ChatGPT", detail: paths.chatgptConfig || "mcp_config.json", done: Boolean(st("chatgpt").configured) }); writes.push(`${paths.chatgptConfig || "mcp_config.json"}: mcpServers.lapidary and mcpServers.rea (other entries kept)`); }
    if (target === "openwebui") { steps.push({ id: "connect:openwebui", kind: "connect", text: "Write the Open WebUI compose file and start it on port 3080", detail: "docker compose -f open-webui.compose.yml up -d", done: Boolean(st("openwebui").running) }); writes.push(`${dataDir}/open-webui.compose.yml`); commands.push("docker compose -f open-webui.compose.yml up -d"); }
  }
  steps.push({ id: "open", kind: "open", text: "Open the dashboard", detail: "", done: false });
  return { steps, writes, commands, ports: { lapidary: 8000, ui: 3000, openwebui: 3080, ollama: 11434 }, dataDir };
}
