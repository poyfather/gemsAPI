// The only bridge between the console page and the main process.
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("lapidary", {
  components: () => ipcRenderer.invoke("console:components"),
  install: (id) => ipcRenderer.invoke("console:install", id),
  settings: { get: () => ipcRenderer.invoke("console:settings:get"), set: (patch) => ipcRenderer.invoke("console:settings:set", patch) },
  connect: {
    claude: () => ipcRenderer.invoke("console:connect:claude"),
    chatgpt: () => ipcRenderer.invoke("console:connect:chatgpt"),
    openwebui: () => ipcRenderer.invoke("console:connect:openwebui"),
  },
  restartLapidary: () => ipcRenderer.invoke("console:lapidary:restart"),
  logs: () => ipcRenderer.invoke("console:logs"),
  open: (url) => ipcRenderer.invoke("console:open", url),
  onReady: (cb) => ipcRenderer.on("console:ready", cb),
});
