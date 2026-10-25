// The only bridge between the console page and the main process.
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("lapidary", {
  components: () => ipcRenderer.invoke("console:components"),
  install: (id) => ipcRenderer.invoke("console:install", id),
  toolbox: () => ipcRenderer.invoke("console:toolbox"),
  settings: { get: () => ipcRenderer.invoke("console:settings:get"), set: (patch) => ipcRenderer.invoke("console:settings:set", patch) },
  connect: {
    claude: () => ipcRenderer.invoke("console:connect:claude"),
    chatgpt: () => ipcRenderer.invoke("console:connect:chatgpt"),
    openwebui: () => ipcRenderer.invoke("console:connect:openwebui"),
  },
  restartLapidary: () => ipcRenderer.invoke("console:lapidary:restart"),
  logs: () => ipcRenderer.invoke("console:logs"),
  pwsh: (script) => ipcRenderer.invoke("console:pwsh", script),
  open: (url) => ipcRenderer.invoke("console:open", url),
  onReady: (cb) => ipcRenderer.on("console:ready", cb),
  doctor: { run: () => ipcRenderer.invoke("console:doctor"), fix: (action) => ipcRenderer.invoke("console:doctor:fix", action) },
  firstRun: {
    recipes: (choice) => ipcRenderer.invoke("console:recipes", choice),
    run: (recipeId, choice, keys) => ipcRenderer.invoke("console:recipe:run", recipeId, choice, keys),
    advancedPlan: (answers) => ipcRenderer.invoke("console:advanced:plan", answers),
    advancedRun: (answers) => ipcRenderer.invoke("console:advanced:run", answers),
    done: () => ipcRenderer.invoke("console:firstrun:done"),
    onProgress: (cb) => ipcRenderer.on("console:progress", (_e, ev) => cb(ev)),
  },
});
