// Optional Windows management tools the console can install from legitimate
// sources only: the winget community repository (manifests verified against
// the publisher's own download) and the PowerShell Gallery for Microsoft
// modules. Nothing here is bundled or redistributed; the console runs the
// publisher's installer through winget or Install-Module.

export const TOOLBOX = [
  { id: "windows-terminal", name: "Windows Terminal", publisher: "Microsoft", category: "shell", source: { winget: "Microsoft.WindowsTerminal" }, detect: { cmd: "wt" }, homepage: "https://github.com/microsoft/terminal" },
  { id: "powertoys", name: "PowerToys", publisher: "Microsoft", category: "productivity", source: { winget: "Microsoft.PowerToys" }, homepage: "https://github.com/microsoft/PowerToys" },
  { id: "sysinternals", name: "Sysinternals Suite", publisher: "Microsoft", category: "diagnostics", source: { winget: "Microsoft.Sysinternals" }, detect: { cmd: "procexp" }, homepage: "https://learn.microsoft.com/sysinternals/" },
  { id: "windows-admin-center", name: "Windows Admin Center", publisher: "Microsoft", category: "management", source: { winget: "Microsoft.WindowsAdminCenter" }, homepage: "https://learn.microsoft.com/windows-server/manage/windows-admin-center/overview" },
  { id: "git", name: "Git", publisher: "Git", category: "developer", source: { winget: "Git.Git" }, detect: { cmd: "git" }, homepage: "https://git-scm.com" },
  { id: "python", name: "Python 3.12", publisher: "Python Software Foundation", category: "developer", source: { winget: "Python.Python.3.12" }, detect: { cmd: "python" }, homepage: "https://www.python.org" },
  { id: "vscode", name: "Visual Studio Code", publisher: "Microsoft", category: "developer", source: { winget: "Microsoft.VisualStudioCode" }, detect: { cmd: "code" }, homepage: "https://code.visualstudio.com" },
  { id: "7zip", name: "7-Zip", publisher: "Igor Pavlov", category: "utility", source: { winget: "7zip.7zip" }, detect: { cmd: "7z" }, homepage: "https://www.7-zip.org" },
  { id: "notepadpp", name: "Notepad++", publisher: "Notepad++", category: "utility", source: { winget: "Notepad++.Notepad++" }, homepage: "https://notepad-plus-plus.org" },
  { id: "everything", name: "Everything (file search)", publisher: "voidtools", category: "utility", source: { winget: "voidtools.Everything" }, homepage: "https://www.voidtools.com" },
  { id: "putty", name: "PuTTY", publisher: "Simon Tatham", category: "network", source: { winget: "PuTTY.PuTTY" }, detect: { cmd: "putty" }, homepage: "https://www.chiark.greenend.org.uk/~sgtatham/putty/" },
  { id: "wireshark", name: "Wireshark", publisher: "Wireshark Foundation", category: "network", source: { winget: "WiresharkFoundation.Wireshark" }, homepage: "https://www.wireshark.org" },
  { id: "nmap", name: "Nmap", publisher: "Nmap Project", category: "network", source: { winget: "Insecure.Nmap" }, detect: { cmd: "nmap" }, homepage: "https://nmap.org" },
  { id: "azure-cli", name: "Azure CLI", publisher: "Microsoft", category: "cloud", source: { winget: "Microsoft.AzureCLI" }, detect: { cmd: "az" }, homepage: "https://learn.microsoft.com/cli/azure/" },
  { id: "msgraph", name: "Microsoft Graph PowerShell SDK", publisher: "Microsoft", category: "management", source: { psgallery: "Microsoft.Graph" }, homepage: "https://learn.microsoft.com/powershell/microsoftgraph/" },
  { id: "pswindowsupdate", name: "PSWindowsUpdate module", publisher: "Michal Gajda (PowerShell Gallery)", category: "management", source: { psgallery: "PSWindowsUpdate" }, homepage: "https://www.powershellgallery.com/packages/PSWindowsUpdate" },
  { id: "wsl", name: "Windows Subsystem for Linux", publisher: "Microsoft", category: "developer", source: { command: ["wsl", "--install", "--no-launch"] }, detect: { cmd: "wsl" }, homepage: "https://learn.microsoft.com/windows/wsl/" },
];

/** The command that installs a toolbox entry; psgallery modules go through pwsh. */
export function toolboxInstallCommand(id, { pwshPath = "pwsh" } = {}) {
  const t = TOOLBOX.find((x) => x.id === id);
  if (!t) return null;
  if (t.source.winget) return { program: "winget", args: ["install", "--id", t.source.winget, "-e", "--accept-source-agreements", "--accept-package-agreements"] };
  if (t.source.psgallery) return { program: pwshPath, args: ["-NoProfile", "-NonInteractive", "-Command", `Install-Module -Name ${t.source.psgallery} -Scope CurrentUser -Force -AllowClobber`] };
  if (t.source.command) return { program: t.source.command[0], args: t.source.command.slice(1) };
  return null;
}

/** Where the entry comes from, as one line for the UI. */
export function toolboxSourceLabel(t) {
  if (t.source.winget) return `winget ${t.source.winget}`;
  if (t.source.psgallery) return `PowerShell Gallery ${t.source.psgallery}`;
  if (t.source.command) return t.source.command.join(" ");
  return "";
}

/** Detect what is already there: a command on PATH, or unknown when the entry has no cheap check. */
export async function detectToolbox(io) {
  const out = {};
  for (const t of TOOLBOX) {
    if (t.detect?.cmd) {
      const path = await io.which(t.detect.cmd);
      out[t.id] = { installed: !!path, path };
    } else {
      out[t.id] = { installed: null };
    }
  }
  return out;
}
