"""
Lapidary Helper: the Windows service that installs and updates for Lapidary Console.

Chrome installs once for the whole machine and keeps a small service running as
SYSTEM, so it can update without asking for administrator rights every time.
This is the same idea, kept deliberately narrow:

- It listens on a local named pipe (\\\\.\\pipe\\LapidaryHelper) that rejects remote
  clients and is open only to SYSTEM, Administrators and the signed-in user.
- It does three things and nothing else: install or upgrade a package from the
  allowlist written at build time from the console's own catalog (winget ids
  from the winget source, and PowerShell Gallery modules); update the console
  itself from this project's GitHub releases, after checking the SHA-256
  checksum published with the release and, when the build is signed, the
  Authenticode signature and publisher; and answer ping.
- It never runs a command line it was sent. A request names an allowlisted id;
  the command is built here.

Everything it does is written to helper.log next to the helper, in the install
folder under Program Files, which only administrators can change. Console
updates download into a new folder under the Windows temp folder that only
SYSTEM and Administrators can open, so a signed-in user cannot swap the
installer between the check and the run.

The functions above the service class are plain Python and are tested on any
platform (tests/test_helper.py). The service itself needs pywin32 on Windows.
"""
from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import urllib.request

SERVICE_NAME = "LapidaryHelper"
DISPLAY_NAME = "Lapidary Helper"
DESCRIPTION = "Installs and updates Lapidary Console and the tools it manages, so the console never needs administrator rights."
PIPE_NAME = r"\\.\pipe\LapidaryHelper"
RELEASES_URL = "https://api.github.com/repos/poyfather/lapidary/releases/latest"
# Only SYSTEM, built-in Administrators and interactive (signed-in) users may connect.
PIPE_SDDL = "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGW;;;IU)"
ASSET_RE = re.compile(r"^LapidaryConsole-Setup-(\d+\.\d+\.\d+)\.exe$")
OPS = ("ping", "install", "upgrade", "update_console")
MAX_REQUEST = 4096
# The private download folder: SYSTEM and Administrators only, not inherited.
PRIVATE_SDDL = "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"


# ─── Pure logic ────────────────────────────────────────────────────────────────

def load_allowlist(path: str) -> dict:
    """The allowlist written at build time next to the helper: {console_version, publisher_subject, packages: {id: {winget|psgallery}}}."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("packages"), dict):
        raise ValueError("allowlist has no packages")
    return data


def parse_request(raw: bytes, allowlist: dict) -> dict:
    """Validate one request line. Raises ValueError with a message the console can show."""
    if len(raw) > MAX_REQUEST:
        raise ValueError("request too long")
    try:
        req = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("request is not JSON")
    if not isinstance(req, dict):
        raise ValueError("request must be a JSON object")
    op = req.get("op")
    if op not in OPS:
        raise ValueError(f"unknown op; use one of {', '.join(OPS)}")
    if op in ("install", "upgrade"):
        pid = req.get("id")
        if not isinstance(pid, str) or pid not in allowlist["packages"]:
            raise ValueError(f"'{pid}' is not on the helper's allowlist")
        return {"op": op, "id": pid}
    return {"op": op}


def winget_command(winget: str, package: str, op: str) -> list[str]:
    """A machine-wide, silent winget install or upgrade of one exact id from the winget source."""
    verb = "upgrade" if op == "upgrade" else "install"
    return [winget, verb, "--id", package, "--exact", "--source", "winget", "--scope", "machine", "--silent",
            "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"]


def psgallery_command(pwsh: str, module: str, op: str) -> list[str]:
    """Install or update a module for all users from the PowerShell Gallery."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", module):
        raise ValueError("bad module name")
    verb = "Update-Module" if op == "upgrade" else "Install-Module"
    extra = "" if op == "upgrade" else " -Scope AllUsers -Force -AllowClobber"
    return [pwsh, "-NoProfile", "-NonInteractive", "-Command", f"{verb} -Name {module}{extra} -ErrorAction Stop"]


def command_for(entry: dict, op: str, winget: str | None, pwsh: str) -> list[str]:
    if "winget" in entry:
        if not winget:
            raise ValueError("winget was not found on this machine; install App Installer from the Microsoft Store")
        return winget_command(winget, entry["winget"], op)
    if "psgallery" in entry:
        return psgallery_command(pwsh, entry["psgallery"], op)
    raise ValueError("allowlist entry has no source")


def find_winget(program_files: str) -> str | None:
    """winget is a per-user app alias, invisible to SYSTEM; find the machine copy of App Installer instead (newest first)."""
    pattern = os.path.join(program_files, "WindowsApps", "Microsoft.DesktopAppInstaller_*_x64__8wekyb3d8bbwe", "winget.exe")
    found = sorted(glob.glob(pattern), key=_version_key_of_path, reverse=True)
    return found[0] if found else None


def _version_key_of_path(path: str) -> tuple:
    m = re.search(r"DesktopAppInstaller_([\d.]+)_", path)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def version_key(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def newer(remote: str, local: str) -> bool:
    return version_key(remote) > version_key(local)


def pick_release_asset(release: dict) -> tuple[str, str, str] | None:
    """(installer url, checksum url, version) from a GitHub release, or None when it has no installer and checksum."""
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in release.get("assets", [])}
    for name, url in assets.items():
        m = ASSET_RE.match(name)
        if m and assets.get(name + ".sha256", "").startswith("https://github.com/"):
            if url.startswith("https://github.com/"):
                return url, assets[name + ".sha256"], m.group(1)
    return None


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def checksum_matches(path: str, checksum_text: str) -> bool:
    """The .sha256 file is 'hex' or 'hex  filename'; compare case-insensitively."""
    expected = checksum_text.strip().split()[0].lower() if checksum_text.strip() else ""
    return bool(re.fullmatch(r"[0-9a-f]{64}", expected)) and sha256_of(path) == expected


def publisher_matches(expected: str, actual: str) -> bool:
    """The signer's full subject must equal the one baked in at build time (spacing aside); a look-alike name does not pass."""
    def norm(s: str) -> list[str]:
        return [part.strip() for part in s.split(",") if part.strip()]
    return bool(expected.strip()) and norm(expected) == norm(actual)


def system_temp() -> str:
    """SYSTEM's temp folder. Signed-in users may create items in it but cannot delete or rename what SYSTEM made."""
    root = os.environ.get("SystemRoot", r"C:\Windows")
    newer_one = os.path.join(root, "SystemTemp")
    return newer_one if os.path.isdir(newer_one) else os.path.join(root, "Temp")


def default_private_dir() -> str:
    return os.path.join(system_temp(), f"lapidary-update-{secrets.token_hex(16)}")


def here() -> str:
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))


# ─── The work ──────────────────────────────────────────────────────────────────

Emit = "callable[[dict], None]"


def _run(cmd: list[str], emit) -> int:
    logging.info("run: %s", " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for raw in p.stdout:
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            logging.info("  %s", line)
            emit({"line": line})
    return p.wait()


def _fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "LapidaryHelper", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - fixed https URLs only
        return r.read()


def _signature_ok(path: str, subject: str, pwsh: str) -> tuple[bool, str]:
    if not subject:
        return True, "unsigned build: checksum only"
    script = f"$s = Get-AuthenticodeSignature -LiteralPath '{path}'; \"$($s.Status)|$($s.SignerCertificate.Subject)\""
    out = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=60).stdout.strip()
    status, _, signer = out.partition("|")
    if status != "Valid" or not publisher_matches(subject, signer):
        return False, f"signature check failed ({status or 'no status'}; signer {signer or 'none'})"
    return True, f"signed by {signer}"


def _make_private_dir_plain() -> str:
    path = default_private_dir()
    os.makedirs(path)
    return path


def handle(req: dict, allowlist: dict, emit, make_private_dir=_make_private_dir_plain) -> dict:
    """Do one validated request; return the final message. make_private_dir returns a new folder only SYSTEM can write."""
    pwsh = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    if req["op"] == "ping":
        return {"done": True, "ok": True, "message": "Lapidary Helper is running", "version": allowlist.get("console_version", "")}
    if req["op"] in ("install", "upgrade"):
        cmd = command_for(allowlist["packages"][req["id"]], req["op"], find_winget(os.environ.get("ProgramFiles", r"C:\Program Files")), pwsh)
        code = _run(cmd, emit)
        return {"done": True, "ok": code == 0, "message": f"{req['id']}: {'done' if code == 0 else f'the installer stopped with code {code}'}"}
    # update_console
    release = json.loads(_fetch(RELEASES_URL))
    picked = pick_release_asset(release)
    if picked is None:
        return {"done": True, "ok": False, "message": "the latest release has no installer with a checksum"}
    url, sha_url, version = picked
    local = allowlist.get("console_version", "0.0.0")
    if not newer(version, local):
        return {"done": True, "ok": True, "message": f"Lapidary Console {local} is up to date"}
    folder = make_private_dir()
    _remember_update_dir(folder)
    target = os.path.join(folder, f"LapidaryConsole-Setup-{version}.exe")
    emit({"line": f"downloading {version}"})
    with open(target, "wb") as f:
        f.write(_fetch(url, timeout=600))
    if not checksum_matches(target, _fetch(sha_url).decode("utf-8", "replace")):
        shutil.rmtree(folder, ignore_errors=True)
        return {"done": True, "ok": False, "message": "the download did not match its published checksum; nothing was installed"}
    ok, why = _signature_ok(target, allowlist.get("publisher_subject", ""), pwsh)
    if not ok:
        shutil.rmtree(folder, ignore_errors=True)
        return {"done": True, "ok": False, "message": why + "; nothing was installed"}
    emit({"line": f"checksum matches; {why}; installing {version}"})
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([target, "/S"], creationflags=flags, close_fds=True)   # the installer restarts this service
    return {"done": True, "ok": True, "message": f"installing Lapidary Console {version}; it restarts when done"}


def _remember_update_dir(folder: str) -> None:
    with open(os.path.join(here(), "last-update-dir.txt"), "w", encoding="utf-8") as f:
        f.write(folder)


def _clean_last_update_dir() -> None:
    """Remove the previous update's download. Only a folder this service made (named in its own protected folder) is touched."""
    marker = os.path.join(here(), "last-update-dir.txt")
    try:
        with open(marker, encoding="utf-8") as f:
            folder = f.read().strip()
    except OSError:
        return
    if os.path.basename(folder).startswith("lapidary-update-") and os.path.dirname(folder) == system_temp():
        shutil.rmtree(folder, ignore_errors=True)
    try:
        os.remove(marker)
    except OSError:
        pass


# ─── The service (Windows, pywin32) ────────────────────────────────────────────

try:
    import pywintypes
    import servicemanager
    import win32event
    import win32file
    import win32pipe
    import win32security
    import win32service
    import win32serviceutil

    def make_private_dir_secured() -> str:
        """A new folder whose access list admits only SYSTEM and Administrators; fails if the name already exists."""
        path = default_private_dir()
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.SECURITY_DESCRIPTOR = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(PRIVATE_SDDL, win32security.SDDL_REVISION_1)
        win32file.CreateDirectory(path, sa)
        return path

    class HelperService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = DISPLAY_NAME
        _svc_description_ = DESCRIPTION
        if getattr(sys, "frozen", False):
            _exe_name_ = sys.executable
            _exe_args_ = ""

        def __init__(self, args) -> None:
            super().__init__(args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.running = True

        def SvcStop(self) -> None:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.running = False
            win32event.SetEvent(self.stop_event)
            try:   # unblock ConnectNamedPipe with a throwaway client
                win32file.CloseHandle(win32file.CreateFile(PIPE_NAME, win32file.GENERIC_READ | win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None))
            except pywintypes.error:
                pass

        def SvcDoRun(self) -> None:
            logging.basicConfig(filename=os.path.join(here(), "helper.log"), level=logging.INFO, format="%(asctime)s %(message)s")
            logging.info("starting from %s", here())
            try:
                self._run_service()
            except Exception:
                logging.exception("the helper stopped on an error")
                raise

        def _run_service(self) -> None:
            _clean_last_update_dir()
            servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ""))
            allowlist = load_allowlist(os.path.join(here(), "allowlist.json"))
            sa = win32security.SECURITY_ATTRIBUTES()
            sa.SECURITY_DESCRIPTOR = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(PIPE_SDDL, win32security.SDDL_REVISION_1)
            reject_remote = 0x00000008   # PIPE_REJECT_REMOTE_CLIENTS
            while self.running:
                pipe = win32pipe.CreateNamedPipe(
                    PIPE_NAME, win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT | reject_remote,
                    1, 65536, 65536, 0, sa)
                try:
                    win32pipe.ConnectNamedPipe(pipe, None)
                    if self.running:
                        self._serve(pipe, allowlist)
                except pywintypes.error as exc:
                    logging.info("pipe error: %s", exc)
                finally:
                    try:
                        win32file.FlushFileBuffers(pipe)
                        win32pipe.DisconnectNamedPipe(pipe)
                    except pywintypes.error:
                        pass
                    win32file.CloseHandle(pipe)

        def _serve(self, pipe, allowlist: dict) -> None:
            buf = b""
            while b"\n" not in buf and len(buf) <= MAX_REQUEST:
                _, chunk = win32file.ReadFile(pipe, 4096)
                if not chunk:
                    break
                buf += chunk

            def emit(obj: dict) -> None:
                win32file.WriteFile(pipe, (json.dumps(obj) + "\n").encode("utf-8"))

            try:
                req = parse_request(buf.split(b"\n", 1)[0], allowlist)
                logging.info("request: %s", req)
                emit(handle(req, allowlist, emit, make_private_dir_secured))
            except ValueError as exc:
                logging.info("refused: %s", exc)
                emit({"done": True, "ok": False, "message": str(exc)})
            except Exception as exc:   # noqa: BLE001 - report, never crash the service
                logging.exception("failed")
                emit({"done": True, "ok": False, "message": f"{type(exc).__name__}: {exc}"[:300]})

except ImportError:   # not on Windows, or pywin32 missing: the pure logic above still imports for tests
    HelperService = None


if __name__ == "__main__":
    if HelperService is None:
        sys.exit("Lapidary Helper runs on Windows with pywin32.")
    if len(sys.argv) == 1:   # started by the Service Control Manager
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(HelperService)
        servicemanager.StartServiceCtrlDispatcher()
    else:   # install, remove, start, stop, update; see win32serviceutil
        win32serviceutil.HandleCommandLine(HelperService)
