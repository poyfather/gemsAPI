# Lapidary Console

The Windows 11 application that installs, connects and manages the AI tools on a machine, with Lapidary as the hub (ADR-009, roadmap items 36 to 42). An Electron shell: the main process does the privileged work, a single console page shows it, and the Lapidary web UI is embedded for gems, chat and runs.

## Design

Simple and retro, on purpose. One typeface (Cascadia Mono, which Windows ships, then Consolas), one amber for headings and the active item, one green for "running" lamps, one red for "missing", near-black panels with a single bright corner tick, faint scanlines and nothing that flickers or animates. Nine views, reachable by the number keys: Start, Dashboard, Doctor, Components, Connections, Settings, Logs, PowerShell, Lapidary. Every action prints what it did in a monospace box under the button, and everything the console runs is in Logs. The look is a terminal from a better decade; the rules are the ones a console for operators needs: dense, legible, keyboard-first, no surprises.

## Who it is for

Two people (ADR-012). Anyone on the Basic setup, a student, a parent, a marketing person, someone at home, who does not know much about AI, installs this, and gets something genuinely useful on day one: recipes, defaults, plain words, private and free by default with local models, cloud as a paid upgrade. A system administrator in IT who takes the Advanced setup: every choice walked through, every file the console writes shown first, and an Advanced toggle that reveals the details on every screen. So: plain words on the surface, nothing that needs a file edited, a path that works without a cloud key, outcomes offered as one-click recipes, every component explaining itself in a sentence, and anything that changes the machine asking first. The power-user surfaces stay one click away.

## Layout

```
main.js            Electron main: settings (safeStorage), sidecars, detection, installs, config writers, IPC
preload.js         the only bridge to the page (window.lapidary)
renderer/          console.html, console.css, console.js (no framework)
lib/components.js  what the console manages, platform paths, detection over an injected io
lib/doctor.js      the Doctor: facts about the machine in, findings in plain words with their fixes out
lib/recipes.js     the first run: the five AI choices, the eight recipes, and the planners that turn them into steps for this machine
lib/configs.js     pure config writers: Claude Desktop and ChatGPT MCP entries, Open WebUI compose, backend env
lib/sidecars.js    child processes and health polling
lib/pwsh.js        PowerShell 7 invocation and output capping
lib/toolbox.js     the optional tools catalog with publishers, sources and detection
lib/helper.js      the pipe client for Lapidary Helper, and the allowlist built from the catalog
helper/            Lapidary Helper, the Windows service that installs and updates (Python, pywin32)
installer.nsh      installer additions that register and remove the helper
scripts/           allowlist.mjs writes the helper's allowlist at build time
test/              node --test; the pure logic is covered on every platform
```

## Run in development (any platform)

Start the backend and the UI as usual, then:

```sh
cd desktop && npm install && npm start
```

Without a packaged backend the console says so in Logs and talks to whatever is running on ports 8000 and 3000.

## Build the Windows installer

The `desktop` workflow in CI builds the backend as a single file with PyInstaller, the UI as a Next.js standalone server, Lapidary Helper as a PyInstaller folder with its allowlist, then `electron-builder --win` into an NSIS installer (`LapidaryConsole-Setup-<version>.exe`) and its SHA-256 checksum. It then installs the result on the Windows runner, checks that the helper service runs as SYSTEM, answers a ping and refuses anything off its allowlist, and uninstalls it again. Every push to main keeps the installer as a workflow artifact; a `v*` tag also attaches it and the checksum to the GitHub release. The same steps run by hand on a Windows machine:

```powershell
pip install -r backend/requirements.txt pyinstaller typer pywin32
pyinstaller --onefile --name lapidary-backend --paths backend backend/run.py
# copy dist/lapidary-backend.exe to build/backend/
pyinstaller --onedir --name lapidary-helper --distpath build --hidden-import win32timezone desktop/helper/lapidary_helper.py
node desktop/scripts/allowlist.mjs build/lapidary-helper/allowlist.json
cd frontend; npm ci; npm run build
# copy .next/standalone to build/frontend/ (plus .next/static and public inside it)
cd ../desktop; npm ci; npm run dist:win
```

## Installs and updates without administrator prompts

The console installs the way Chrome does. The installer asks for administrator rights once, installs for every user on the PC under Program Files, and registers **Lapidary Helper**, a small Windows service that runs as SYSTEM. After that, installing a tool from Components, Toolbox or a first-run recipe, and updating the console itself, happen without another prompt.

The helper is deliberately narrow:

- It listens on a local named pipe that rejects remote clients and admits only SYSTEM, Administrators and signed-in users.
- It installs or upgrades only ids on its allowlist, which CI writes from the console's own catalog: winget packages from the winget source, machine-wide and silent, and PowerShell Gallery modules for all users. It never runs a command line it is sent.
- It updates the console only from this repository's latest GitHub release, only to a newer version, and only after the download matches the published SHA-256 checksum. A signed build also requires a valid Authenticode signature whose subject is exactly the publisher baked in at build time. Downloads go into a new folder only SYSTEM and Administrators can open.
- It logs everything to `helper.log` next to itself in the install folder.

When the helper is not running, the console installs as before and Windows asks for administrator rights where the installer needs them. The Doctor shows whether the helper runs, and "Update now" when a newer console is out.

## Code signing

An unsigned installer works, but Windows SmartScreen shows "Windows protected your PC" and the publisher reads "Unknown". Signing fixes the publisher name. SmartScreen still warns on a new publisher until downloads build reputation, typically a few weeks. CI signs automatically once the secrets below exist; until then it builds unsigned and says so.

**Azure Artifact Signing (recommended, about 9.99 US dollars a month).** Microsoft's signing service, formerly Trusted Signing. Individual developers in the United States and Canada qualify; organizations also in the EU and UK. No hardware token.

1. In the Azure portal, create an Artifact Signing account in a supported region, for example East US, whose endpoint is `https://eus.codesigning.azure.net`.
2. Assign yourself the Artifact Signing Identity Verifier role, then complete a Public identity validation, Individual or Organization. Microsoft checks a government ID; allow a few business days.
3. Create a Public Trust certificate profile from that validation.
4. Create an app registration in Microsoft Entra ID with a client secret, and give it the Artifact Signing Certificate Profile Signer role on the account.
5. In the GitHub repository settings, add secrets `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET`, and variables `AZURE_SIGNING_ENDPOINT`, `AZURE_SIGNING_ACCOUNT` and `AZURE_SIGNING_PROFILE`.
6. Add the variable `LAPIDARY_PUBLISHER_SUBJECT` with the certificate profile's full subject as the portal shows it, for example `CN=Jane Doe, O=Jane Doe, L=Austin, S=Texas, C=US`.

**A .pfx certificate instead.** Since 2023 certificate authorities issue code-signing keys only on hardware tokens or cloud HSMs, so a plain .pfx is uncommon now. If you have one, add it base64-encoded as the secret `WIN_CSC_LINK`, its password as `WIN_CSC_KEY_PASSWORD`, and set `LAPIDARY_PUBLISHER_SUBJECT`.

When signing is on, the console, the backend, the helper and the installer are all signed, CI checks the installer's signature, and the helper's allowlist pins the publisher. From then on, installed consoles accept only updates signed by that exact subject, so keep signing every release with the same identity.

## What each view does

- **Start**: the first run (roadmap item 47). **Basic** asks "Which AI should we use?" (the free one on this PC, the online ones, a mix, decide for me, I'll choose each time, each saying what is private and what costs money) and "What would you like?" (eight recipes), shows the steps for this machine, runs them with a lamp per step, and ends with "here is what you can do now". **Advanced** walks through components, AI and keys, SQLite or Supabase, connections, ports and folders, what assistants may do without asking, logging and updates, then lists every file and command before applying. The **Advanced** switch in the top bar reveals the details (commands, paths, hosted options) on every screen and is remembered. Recipes are also on the Dashboard.
- **Doctor**: the self-check (roadmap item 49). Lapidary and the web UI, the AI choice against what is there (Ollama running with a model, a key saved and accepted), the private chat and Docker, the connections to Claude Desktop and ChatGPT, PowerShell 7, and a newer release. Every finding says what it means; where one click fixes it, the button is next to it.
- **Dashboard**: the recipes, then a lamp per component (winget, PowerShell 7, Node, Docker Desktop, Claude Desktop, ChatGPT, Ollama, Open WebUI, REA, Lapidary) with state, plus restart and open buttons.
- **Components**: every piece with a sentence on what it is for and a line on what it costs or needs; install or update through winget (PowerShell 7, Claude, ChatGPT, Docker Desktop, Ollama, Node), Docker (Open WebUI) and npm (REA). Below it, the **Toolbox**: optional Windows management tools installed from the publisher's own package through winget or the PowerShell Gallery, never bundled or redistributed: Windows Terminal, PowerToys, Sysinternals Suite, Windows Admin Center, Git, Python, Visual Studio Code, 7-Zip, Notepad++, Everything, PuTTY, Wireshark, Nmap, Azure CLI, the Microsoft Graph PowerShell SDK, PSWindowsUpdate, and WSL. Tick several and install them in one go.
- **Connections**: one button each to register Lapidary and REA as MCP servers in Claude Desktop and ChatGPT, the address of Lapidary's MCP server over HTTP with copy buttons (the address, the key, a URL entry, an mcp-remote bridge entry) for apps that take a URL, and a button to write and start an Open WebUI compose file with Lapidary, OpenAI and Ollama as its providers (Lapidary's gems then appear as models in Open WebUI through the OpenAI-compatible API).
- **Settings**: which AI to use (the model policy), the local model, Anthropic and OpenAI keys, and with Advanced on, the local server URL, the Lapidary key and Supabase for the hosted mode; stored with safeStorage.
- **Logs**: everything the console and the sidecars print.
- **PowerShell**: run PowerShell 7 commands as yourself (Windows PowerShell 5 until 7 is installed; the Components view installs it through winget). The same engine is the agents' `run_powershell` tool, risky, so every agent call waits for approval.
- **Lapidary**: the web UI, embedded.

Not built yet: the installer's first run on a real Windows machine (42).
