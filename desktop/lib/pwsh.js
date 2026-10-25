// PowerShell 7 helpers: pure functions so they are tested on every platform.

/** The program and arguments to run a script with PowerShell 7, or Windows PowerShell 5 as a fallback. */
export function pwshInvocation(script, { pwshPath = null, platform = process.platform } = {}) {
  const program = pwshPath || (platform === "win32" ? "powershell.exe" : "pwsh");
  const legacy = !pwshPath && platform === "win32";
  return {
    program,
    args: ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
    note: legacy ? "PowerShell 7 (pwsh) not found; using Windows PowerShell 5" : null,
  };
}

/** Keep the tail of long output and say how much was dropped. */
export function capOutput(text, max = 20000) {
  if (text.length <= max) return text;
  return `[${text.length - max} characters dropped]\n` + text.slice(-max);
}
