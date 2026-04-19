const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  pickFolder: () => ipcRenderer.invoke("pick-folder"),
  setAutostart: (enabled) => ipcRenderer.invoke("set-autostart", enabled),
});
