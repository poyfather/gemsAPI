// Optional Windows management tools the console can install from legitimate
// sources only: the winget community repository (manifests verified against
// the publisher's own download) and the PowerShell Gallery for Microsoft
// modules. Nothing here is bundled or redistributed; the console runs the
// publisher's installer through winget or Install-Module.

export const TOOLBOX = [
  { id: "windows-terminal", name: "Windows Terminal", publisher: "Microsoft", category: "shell", source: { winget: "Microsoft.WindowsTerminal" }, detect: { cmd: "wt" }, homepage: "https://github.com/microsoft/terminal", blurb: "A better window for command lines, with tabs and themes. Nicer than the plain console for PowerShell.", needs: "free, from Microsoft" },
  { id: "powertoys", name: "PowerToys", publisher: "Microsoft", category: "productivity", source: { winget: "Microsoft.PowerToys" }, homepage: "https://github.com/microsoft/PowerToys", blurb: "Small Windows helpers: a quick launcher, window layouts, colour picker, bulk rename, and more.", needs: "free, from Microsoft" },
  { id: "sysinternals", name: "Sysinternals Suite", publisher: "Microsoft", category: "diagnostics", source: { winget: "Microsoft.Sysinternals" }, detect: { cmd: "procexp" }, homepage: "https://learn.microsoft.com/sysinternals/", blurb: "Deep diagnostic tools for Windows: what a process is doing, who holds a file, what starts at boot.", needs: "free, from Microsoft; for IT and the curious" },
  { id: "windows-admin-center", name: "Windows Admin Center", publisher: "Microsoft", category: "management", source: { winget: "Microsoft.WindowsAdminCenter" }, homepage: "https://learn.microsoft.com/windows-server/manage/windows-admin-center/overview", blurb: "A web page for managing Windows servers and PCs: updates, services, storage, remote sessions.", needs: "free, from Microsoft; aimed at IT" },
  { id: "git", name: "Git", publisher: "Git", category: "developer", source: { winget: "Git.Git" }, detect: { cmd: "git" }, homepage: "https://git-scm.com", blurb: "Keeps versions of files and code so you can go back. Needed by many developer tools.", needs: "free, open source" },
  { id: "python", name: "Python 3.12", publisher: "Python Software Foundation", category: "developer", source: { winget: "Python.Python.3.12" }, detect: { cmd: "python" }, homepage: "https://www.python.org", blurb: "A programming language many tools and scripts are written in. The builder assistant can use it.", needs: "free, open source" },
  { id: "vscode", name: "Visual Studio Code", publisher: "Microsoft", category: "developer", source: { winget: "Microsoft.VisualStudioCode" }, detect: { cmd: "code" }, homepage: "https://code.visualstudio.com", blurb: "A code and text editor. Good for looking at what the builder assistant wrote.", needs: "free, from Microsoft" },
  { id: "7zip", name: "7-Zip", publisher: "Igor Pavlov", category: "utility", source: { winget: "7zip.7zip" }, detect: { cmd: "7z" }, homepage: "https://www.7-zip.org", blurb: "Opens and makes zip and other archive files.", needs: "free, open source" },
  { id: "notepadpp", name: "Notepad++", publisher: "Notepad++", category: "utility", source: { winget: "Notepad++.Notepad++" }, homepage: "https://notepad-plus-plus.org", blurb: "A fast text editor for notes, logs and config files.", needs: "free, open source" },
  { id: "everything", name: "Everything (file search)", publisher: "voidtools", category: "utility", source: { winget: "voidtools.Everything" }, homepage: "https://www.voidtools.com", blurb: "Finds any file on this PC by name, instantly.", needs: "free" },
  { id: "putty", name: "PuTTY", publisher: "Simon Tatham", category: "network", source: { winget: "PuTTY.PuTTY" }, detect: { cmd: "putty" }, homepage: "https://www.chiark.greenend.org.uk/~sgtatham/putty/", blurb: "Connects to other machines over SSH and serial.", needs: "free, open source; for IT" },
  { id: "wireshark", name: "Wireshark", publisher: "Wireshark Foundation", category: "network", source: { winget: "WiresharkFoundation.Wireshark" }, homepage: "https://www.wireshark.org", blurb: "Shows what is travelling over the network, packet by packet.", needs: "free, open source; for IT and learning" },
  { id: "nmap", name: "Nmap", publisher: "Nmap Project", category: "network", source: { winget: "Insecure.Nmap" }, detect: { cmd: "nmap" }, homepage: "https://nmap.org", blurb: "Finds which machines and services are on a network. Use only on networks you are allowed to scan.", needs: "free, open source; for IT" },
  { id: "azure-cli", name: "Azure CLI", publisher: "Microsoft", category: "cloud", source: { winget: "Microsoft.AzureCLI" }, detect: { cmd: "az" }, homepage: "https://learn.microsoft.com/cli/azure/", blurb: "Manages Microsoft Azure from the command line.", needs: "free; needs an Azure account to be useful" },
  { id: "msgraph", name: "Microsoft Graph PowerShell SDK", publisher: "Microsoft", category: "management", source: { psgallery: "Microsoft.Graph" }, homepage: "https://learn.microsoft.com/powershell/microsoftgraph/", blurb: "PowerShell commands for Microsoft 365: users, mail, Teams, devices.", needs: "free; needs a Microsoft 365 account" },
  { id: "pswindowsupdate", name: "PSWindowsUpdate module", publisher: "Michal Gajda (PowerShell Gallery)", category: "management", source: { psgallery: "PSWindowsUpdate" }, homepage: "https://www.powershellgallery.com/packages/PSWindowsUpdate", blurb: "PowerShell commands to check and install Windows updates.", needs: "free, community module" },
  { id: "wsl", name: "Windows Subsystem for Linux", publisher: "Microsoft", category: "developer", source: { command: ["wsl", "--install", "--no-launch"] }, detect: { cmd: "wsl" }, homepage: "https://learn.microsoft.com/windows/wsl/", blurb: "Runs Linux inside Windows, for tools that only exist there.", needs: "free, from Microsoft; needs a restart after install" },
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
