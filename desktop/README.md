# Lapidary Console

The Windows 11 application that installs, connects and manages the AI tools on a machine, with Lapidary as the hub (ADR-009, roadmap items 36 to 42). An Electron shell: the main process does the privileged work, a single console page shows it, and the Lapidary web UI is embedded for gems, chat and runs.

## Design

Simple and retro, on purpose. One typeface (Cascadia Mono, which Windows ships, then Consolas), one amber for headings and the active item, one green for "running" lamps, one red for "missing", near-black panels with a single bright corner tick, faint scanlines and nothing that flickers or animates. Seven views, reachable by the number keys: Dashboard, Components, Connections, Settings, Logs, PowerShell, Lapidary. Every action prints what it did in a monospace box under the button, and everything the console runs is in Logs. The look is a terminal from a better decade; the rules are the ones a console for operators needs: dense, legible, keyboard-first, no surprises.

## Who it is for

Someone who does not know much about AI, installs this, and gets something genuinely useful on day one (ADR-012). So: plain words on the surface, nothing that needs a file edited, a path that works without a cloud key, outcomes offered as one-click recipes, every component explaining itself in a sentence, and anything that changes the machine asking first. The power-user surfaces stay one click away.

## Layout

```
main.js            Electron main: settings (safeStorage), sidecars, detection, installs, config writers, IPC
preload.js         the only bridge to the page (window.lapidary)
renderer/          console.html, console.css, console.js (no framework)
lib/components.js  what the console manages, platform paths, detection over an injected io
lib/configs.js     pure config writers: Claude Desktop and ChatGPT MCP entries, Open WebUI compose, backend env
lib/sidecars.js    child processes and health polling
lib/pwsh.js        PowerShell 7 invocation and output capping
lib/toolbox.js     the optional tools catalog with publishers, sources and detection
test/              node --test; the pure logic is covered on every platform
```

## Run in development (any platform)

Start the backend and the UI as usual, then:

```sh
cd desktop && npm install && npm start
```

Without a packaged backend the console says so in Logs and talks to whatever is running on ports 8000 and 3000.

## Build the Windows installer

The `desktop` workflow in CI builds the backend as a single file with PyInstaller, the UI as a Next.js standalone server, then `electron-builder --win` into an NSIS installer (`LapidaryConsole-Setup-<version>.exe`). The same steps run by hand on a Windows machine:

```powershell
pip install -r backend/requirements.txt pyinstaller
pyinstaller --onefile --name lapidary-backend --paths backend backend/run.py
# copy dist/lapidary-backend.exe to build/backend/
cd frontend; npm ci; npm run build
# copy .next/standalone to build/frontend/ (plus .next/static and public inside it)
cd ../desktop; npm ci; npm run dist:win
```

## What each view does

- **Dashboard**: a lamp per component (winget, PowerShell 7, Node, Docker Desktop, Claude Desktop, ChatGPT, Ollama, Open WebUI, REA, Lapidary) with state, plus restart and open buttons.
- **Components**: install or update through winget (PowerShell 7, Claude, ChatGPT, Docker Desktop, Ollama, Node), Docker (Open WebUI) and npm (REA). Below it, the **Toolbox**: optional Windows management tools installed from the publisher's own package through winget or the PowerShell Gallery, never bundled or redistributed: Windows Terminal, PowerToys, Sysinternals Suite, Windows Admin Center, Git, Python, Visual Studio Code, 7-Zip, Notepad++, Everything, PuTTY, Wireshark, Nmap, Azure CLI, the Microsoft Graph PowerShell SDK, PSWindowsUpdate, and WSL. Tick several and install them in one go.
- **Connections**: one button each to register Lapidary and REA as MCP servers in Claude Desktop and ChatGPT, and to write and start an Open WebUI compose file with Lapidary, OpenAI and Ollama as its providers (Lapidary's gems then appear as models in Open WebUI through the OpenAI-compatible API).
- **Settings**: Anthropic and OpenAI keys, the Lapidary key, optional Supabase for the hosted mode; stored with safeStorage.
- **Logs**: everything the console and the sidecars print.
- **PowerShell**: run PowerShell 7 commands as yourself (Windows PowerShell 5 until 7 is installed; the Components view installs it through winget). The same engine is the agents' `run_powershell` tool, risky, so every agent call waits for approval.
- **Lapidary**: the web UI, embedded.

Not built yet: the SQLite storage the desktop env assumes (item 38), the HTTP transport for Lapidary's MCP server (41), the installer's first-run screen (42).
