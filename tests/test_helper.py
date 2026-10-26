"""Lapidary Helper's request checks and command building (desktop/helper/lapidary_helper.py).

The service itself needs Windows and pywin32; everything it decides is plain
Python and is tested here on any platform.
"""
import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "desktop", "helper"))
import lapidary_helper as h  # noqa: E402

ALLOW = {
    "console_version": "0.4.0",
    "publisher_subject": "",
    "packages": {"git": {"winget": "Git.Git"}, "msgraph": {"psgallery": "Microsoft.Graph"}},
}


def test_load_allowlist(tmp_path):
    p = tmp_path / "allowlist.json"
    p.write_text(json.dumps(ALLOW))
    assert h.load_allowlist(str(p))["packages"]["git"] == {"winget": "Git.Git"}
    p.write_text(json.dumps({"packages": []}))
    with pytest.raises(ValueError):
        h.load_allowlist(str(p))


def test_parse_request_accepts_known_ops_and_ids():
    assert h.parse_request(b'{"op":"ping"}', ALLOW) == {"op": "ping"}
    assert h.parse_request(b'{"op":"install","id":"git"}', ALLOW) == {"op": "install", "id": "git"}
    assert h.parse_request(b'{"op":"upgrade","id":"msgraph","extra":1}', ALLOW) == {"op": "upgrade", "id": "msgraph"}
    assert h.parse_request(b'{"op":"update_console"}', ALLOW) == {"op": "update_console"}


@pytest.mark.parametrize("raw", [
    b"not json",
    b"[1,2]",
    b'{"op":"run","cmd":"calc.exe"}',
    b'{"op":"install","id":"evil"}',
    b'{"op":"install","id":["git"]}',
    b'{"op":"install"}',
    b"\xff\xfe",
    b'{"op":"ping","pad":"' + b"x" * 5000 + b'"}',
])
def test_parse_request_refuses(raw):
    with pytest.raises(ValueError):
        h.parse_request(raw, ALLOW)


def test_winget_command_is_exact_silent_machine_wide():
    cmd = h.winget_command("C:/wg/winget.exe", "Git.Git", "install")
    assert cmd[:4] == ["C:/wg/winget.exe", "install", "--id", "Git.Git"]
    for flag in ("--exact", "--silent", "--disable-interactivity"):
        assert flag in cmd
    assert cmd[cmd.index("--source") + 1] == "winget"
    assert cmd[cmd.index("--scope") + 1] == "machine"
    assert h.winget_command("w", "Git.Git", "upgrade")[1] == "upgrade"


def test_psgallery_command():
    cmd = h.psgallery_command("ps.exe", "Microsoft.Graph", "install")
    assert cmd[-1] == "Install-Module -Name Microsoft.Graph -Scope AllUsers -Force -AllowClobber -ErrorAction Stop"
    assert h.psgallery_command("ps.exe", "Microsoft.Graph", "upgrade")[-1] == "Update-Module -Name Microsoft.Graph -ErrorAction Stop"
    with pytest.raises(ValueError):
        h.psgallery_command("ps.exe", "x; Remove-Item C:\\", "install")


def test_command_for():
    assert h.command_for({"winget": "Git.Git"}, "install", "wg", "ps")[0] == "wg"
    assert h.command_for({"psgallery": "Az"}, "install", None, "ps")[0] == "ps"
    with pytest.raises(ValueError, match="winget was not found"):
        h.command_for({"winget": "Git.Git"}, "install", None, "ps")
    with pytest.raises(ValueError):
        h.command_for({}, "install", "wg", "ps")


def test_find_winget_picks_newest(tmp_path):
    apps = tmp_path / "WindowsApps"
    for v in ("1.9.25200.0", "1.10.320.0", "1.2.0.0"):
        d = apps / f"Microsoft.DesktopAppInstaller_{v}_x64__8wekyb3d8bbwe"
        d.mkdir(parents=True)
        (d / "winget.exe").write_text("")
    assert "1.10.320.0" in h.find_winget(str(tmp_path))
    assert h.find_winget(str(tmp_path / "nowhere")) is None


def test_versions():
    assert h.newer("0.5.0", "0.4.0")
    assert h.newer("0.10.0", "0.9.9")
    assert not h.newer("0.4.0", "0.4.0")
    assert not h.newer("0.3.9", "0.4.0")


def _asset(name, url=None):
    return {"name": name, "browser_download_url": url or f"https://github.com/poyfather/lapidary/releases/download/v0.5.0/{name}"}


def test_pick_release_asset():
    rel = {"assets": [_asset("LapidaryConsole-Setup-0.5.0.exe"), _asset("LapidaryConsole-Setup-0.5.0.exe.sha256"), _asset("notes.txt")]}
    url, sha, version = h.pick_release_asset(rel)
    assert url.endswith(".exe") and sha.endswith(".sha256") and version == "0.5.0"


@pytest.mark.parametrize("assets", [
    [_asset("LapidaryConsole-Setup-0.5.0.exe")],                                   # no checksum
    [_asset("LapidaryConsole-Setup-0.5.0.exe", "https://evil.example/x.exe"), _asset("LapidaryConsole-Setup-0.5.0.exe.sha256")],
    [_asset("Other-0.5.0.exe"), _asset("Other-0.5.0.exe.sha256")],
    [],
])
def test_pick_release_asset_refuses(assets):
    assert h.pick_release_asset({"assets": assets}) is None


def test_checksum_matches(tmp_path):
    f = tmp_path / "setup.exe"
    f.write_bytes(b"installer bytes")
    digest = hashlib.sha256(b"installer bytes").hexdigest()
    assert h.checksum_matches(str(f), digest)
    assert h.checksum_matches(str(f), digest.upper() + "  LapidaryConsole-Setup-0.5.0.exe\n")
    assert not h.checksum_matches(str(f), "0" * 64)
    assert not h.checksum_matches(str(f), "")
    assert not h.checksum_matches(str(f), "not a digest")


def test_publisher_matches_exactly():
    subject = "CN=Lapidary, O=Lapidary, L=Austin, S=Texas, C=US"
    assert h.publisher_matches(subject, "CN=Lapidary,  O=Lapidary, L=Austin, S=Texas, C=US")
    assert not h.publisher_matches(subject, "CN=Lapidary Evil, O=Lapidary, L=Austin, S=Texas, C=US")
    assert not h.publisher_matches("CN=Lapidary", "CN=Lapidary, O=Other")
    assert not h.publisher_matches("", "CN=Anyone")


def test_handle_ping_and_install(monkeypatch):
    assert h.handle({"op": "ping"}, ALLOW, lambda m: None)["ok"]
    ran = []
    monkeypatch.setattr(h, "find_winget", lambda pf: "winget.exe")
    monkeypatch.setattr(h, "_run", lambda cmd, emit: ran.append(cmd) or 0)
    out = h.handle({"op": "install", "id": "git"}, ALLOW, lambda m: None)
    assert out["ok"] and ran[0][:4] == ["winget.exe", "install", "--id", "Git.Git"]
    monkeypatch.setattr(h, "_run", lambda cmd, emit: 1603)
    assert not h.handle({"op": "upgrade", "id": "git"}, ALLOW, lambda m: None)["ok"]


def _release(version="0.5.0"):
    name = f"LapidaryConsole-Setup-{version}.exe"
    return {"assets": [_asset(name), _asset(name + ".sha256")]}


def _fake_fetch(payload, checksum):
    def fetch(url, timeout=60):
        if url == h.RELEASES_URL:
            return json.dumps(_release()).encode()
        if url.endswith(".sha256"):
            return checksum.encode()
        return payload
    return fetch


def _private(tmp_path):
    def make():
        d = tmp_path / "lapidary-update-x"
        d.mkdir()
        return str(d)
    return make


def test_update_console_up_to_date(monkeypatch, tmp_path):
    monkeypatch.setattr(h, "_fetch", _fake_fetch(b"", ""))
    out = h.handle({"op": "update_console"}, {**ALLOW, "console_version": "0.5.0"}, lambda m: None, _private(tmp_path))
    assert out["ok"] and "up to date" in out["message"]


def test_update_console_refuses_bad_checksum(monkeypatch, tmp_path):
    monkeypatch.setattr(h, "_fetch", _fake_fetch(b"tampered", "0" * 64))
    monkeypatch.setattr(h, "here", lambda: str(tmp_path))
    started = []
    monkeypatch.setattr(h.subprocess, "Popen", lambda *a, **k: started.append(a))
    out = h.handle({"op": "update_console"}, ALLOW, lambda m: None, _private(tmp_path))
    assert not out["ok"] and "checksum" in out["message"]
    assert not started and not (tmp_path / "lapidary-update-x").exists()


def test_update_console_refuses_wrong_publisher(monkeypatch, tmp_path):
    payload = b"real installer"
    monkeypatch.setattr(h, "_fetch", _fake_fetch(payload, hashlib.sha256(payload).hexdigest()))
    monkeypatch.setattr(h, "here", lambda: str(tmp_path))
    monkeypatch.setattr(h, "_signature_ok", lambda path, subject, pwsh: (False, "signature check failed"))
    started = []
    monkeypatch.setattr(h.subprocess, "Popen", lambda *a, **k: started.append(a))
    out = h.handle({"op": "update_console"}, {**ALLOW, "publisher_subject": "CN=Lapidary"}, lambda m: None, _private(tmp_path))
    assert not out["ok"] and not started


def test_update_console_runs_verified_installer(monkeypatch, tmp_path):
    payload = b"real installer"
    monkeypatch.setattr(h, "_fetch", _fake_fetch(payload, hashlib.sha256(payload).hexdigest()))
    monkeypatch.setattr(h, "here", lambda: str(tmp_path))
    started = []
    monkeypatch.setattr(h.subprocess, "Popen", lambda args, **k: started.append(args))
    out = h.handle({"op": "update_console"}, ALLOW, lambda m: None, _private(tmp_path))
    assert out["ok"], out
    assert started[0][1] == "/S" and started[0][0].endswith("LapidaryConsole-Setup-0.5.0.exe")
    assert (tmp_path / "last-update-dir.txt").read_text() == str(tmp_path / "lapidary-update-x")
