const { app, BrowserWindow, Tray, Menu, dialog, ipcMain, nativeImage } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const PORT = 8765;
const URL = `http://127.0.0.1:${PORT}`;
const PROJECT_ROOT = path.resolve(__dirname, "..");

let mainWindow = null;
let tray = null;
let pyProc = null;
let quitting = false;

function waitForBackend(retries = 40) {
  return new Promise((resolve, reject) => {
    const tryOnce = (n) => {
      const req = http.get(URL + "/api/status", (res) => {
        res.resume();
        resolve();
      });
      req.on("error", () => {
        if (n <= 0) reject(new Error("backend not reachable"));
        else setTimeout(() => tryOnce(n - 1), 250);
      });
      req.setTimeout(500, () => req.destroy());
    };
    tryOnce(retries);
  });
}

function resolveBackend() {
  // Packaged layout: electron-builder copies the PyInstaller folder to
  // resources/backend/codegraph-backend(.exe).
  const resources = process.resourcesPath || "";
  const exeName = process.platform === "win32"
    ? "codegraph-backend.exe" : "codegraph-backend";
  const packaged = path.join(resources, "backend", "codegraph-backend", exeName);
  try {
    if (require("fs").existsSync(packaged)) {
      return { cmd: packaged, args: [], cwd: path.dirname(packaged) };
    }
  } catch {}
  // Dev fallback: use the system Python.
  const py = process.platform === "win32" ? "python" : "python3";
  return { cmd: py, args: ["run.py"], cwd: PROJECT_ROOT };
}

function startBackend() {
  const { cmd, args, cwd } = resolveBackend();
  pyProc = spawn(cmd, args, {
    cwd,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
    env: { ...process.env, CODEGRAPH_NO_BROWSER: "1" },
  });
  pyProc.stdout.on("data", (d) => process.stdout.write(`[py] ${d}`));
  pyProc.stderr.on("data", (d) => process.stderr.write(`[py] ${d}`));
  pyProc.on("exit", (code) => {
    pyProc = null;
    if (!quitting) {
      dialog.showErrorBox("CodeGraph backend crashed", `Python process exited with code ${code}.`);
    }
  });
}

function stopBackend() {
  if (pyProc) {
    try {
      if (process.platform === "win32") {
        spawn("taskkill", ["/pid", pyProc.pid, "/f", "/t"]);
      } else {
        pyProc.kill("SIGTERM");
      }
    } catch {}
    pyProc = null;
  }
}

function createWindow() {
  const iconFile = process.platform === "win32" ? "icon.ico" : "icon.png";
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    backgroundColor: "#0f1117",
    title: "CodeGraph",
    icon: path.join(__dirname, iconFile),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  mainWindow.loadURL(URL);
  mainWindow.webContents.on("preload-error", (_e, preloadPath, error) => {
    console.error("[preload-error]", preloadPath, error);
    dialog.showErrorBox("Preload failed", `${preloadPath}\n\n${error?.stack || error}`);
  });
  mainWindow.on("close", (e) => {
    if (!quitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  const trayIcon = path.join(__dirname, "icon_tray.png");
  let img;
  try { img = nativeImage.createFromPath(trayIcon); } catch { img = nativeImage.createEmpty(); }
  if (img.isEmpty()) {
    try { img = nativeImage.createFromPath(path.join(__dirname, "icon.png")); }
    catch { img = nativeImage.createEmpty(); }
  }
  tray = new Tray(img);
  tray.setToolTip("CodeGraph — live code context");
  const menu = Menu.buildFromTemplate([
    { label: "Show CodeGraph", click: () => { mainWindow?.show(); } },
    { label: "Open in browser", click: () => require("electron").shell.openExternal(URL) },
    { type: "separator" },
    { label: "Quit", click: () => { quitting = true; app.quit(); } },
  ]);
  tray.setContextMenu(menu);
  tray.on("click", () => { mainWindow?.show(); });
}

ipcMain.handle("set-autostart", async (_e, enabled) => {
  try {
    app.setLoginItemSettings({ openAtLogin: !!enabled, openAsHidden: true });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
});

ipcMain.handle("pick-folder", async () => {
  const res = await dialog.showOpenDialog(mainWindow, {
    title: "Pick a project folder to watch",
    properties: ["openDirectory"],
  });
  if (res.canceled || !res.filePaths.length) return null;
  return res.filePaths[0];
});

app.commandLine.appendSwitch("disable-http-cache");

app.whenReady().then(async () => {
  startBackend();
  try { await waitForBackend(); } catch (e) {
    dialog.showErrorBox("Failed to start CodeGraph",
      "The Python backend didn't start. Make sure Python is installed and "
      + "you've run `pip install -r requirements.txt`.");
    app.quit();
    return;
  }
  try {
    const session = require("electron").session.defaultSession;
    await session.clearCache();
  } catch {}
  createWindow();
  createTray();
});

app.on("window-all-closed", (e) => {
  // keep running in tray on non-macOS too
});

app.on("before-quit", () => {
  quitting = true;
  stopBackend();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
  else mainWindow?.show();
});
