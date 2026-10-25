"""The run_powershell tool with the process faked; it is risky, so the loop gates it."""
import asyncio

import app.agents.builtin as builtin
from app import settings
from app.agents.tools import call_tool, get_tool


def test_tool_is_registered_and_risky() -> None:
    t = get_tool("run_powershell")
    assert t.risky and t.parameters["required"] == ["script"]
    assert "PowerShell" in t.description and "read-only" in t.description


def test_runs_pwsh_with_safe_flags_and_returns_output_and_exit_code(monkeypatch) -> None:
    seen = {}

    async def fake_run(program, args, timeout):
        seen.update(program=program, args=args, timeout=timeout)
        return 0, "OsName : Microsoft Windows 11 Pro\n", ""

    monkeypatch.setattr(builtin, "_powershell_program", lambda: "/usr/local/bin/pwsh")
    monkeypatch.setattr(builtin, "_run_process", fake_run)
    out = asyncio.run(call_tool(get_tool("run_powershell"), {"script": "Get-ComputerInfo | Select OsName"}))
    assert out == "OsName : Microsoft Windows 11 Pro\n[exit 0]"
    assert seen["program"] == "/usr/local/bin/pwsh"
    assert seen["args"][:4] == ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]
    assert seen["args"][-1] == "Get-ComputerInfo | Select OsName"
    assert seen["timeout"] == settings.POWERSHELL_TIMEOUT_SECONDS


def test_stderr_timeouts_and_caps_are_reported(monkeypatch) -> None:
    monkeypatch.setattr(builtin, "_powershell_program", lambda: "pwsh")
    monkeypatch.setattr(settings, "POWERSHELL_MAX_OUTPUT_CHARS", 40)

    async def failing(program, args, timeout):
        return 1, "x" * 100, "Access denied"

    monkeypatch.setattr(builtin, "_run_process", failing)
    out = asyncio.run(call_tool(get_tool("run_powershell"), {"script": "Stop-Service x"}))
    assert out.startswith("[60 characters dropped]\n") and "[stderr]\nAccess denied" in out and out.endswith("[exit 1]")

    async def timing_out(program, args, timeout):
        return -1, "", "stopped after 120 seconds"

    monkeypatch.setattr(builtin, "_run_process", timing_out)
    assert "stopped after 120 seconds" in asyncio.run(call_tool(get_tool("run_powershell"), {"script": "sleep 999"}))


def test_missing_powershell_is_explained_not_raised(monkeypatch) -> None:
    monkeypatch.setattr(builtin, "_powershell_program", lambda: None)
    out = asyncio.run(call_tool(get_tool("run_powershell"), {"script": "Get-Date"}))
    assert "not installed" in out


def test_the_loop_pauses_before_running_powershell(fake_library, fake_runs, monkeypatch) -> None:
    from app.agents import runner
    from app.services.llm_service import ToolCall
    from conftest import make_gem
    from test_runner import fake_turns

    fake_library["ops"] = make_gem("ops", "Operate.", kind="agent", tools=["run_powershell"])
    fn, _ = fake_turns([("", [ToolCall(id="1", name="run_powershell", input={"script": "Restart-Computer"})]), ("done", [])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = asyncio.run(runner.run_agent("ops", "reboot"))
    assert result.run.status == "waiting_approval"
    assert result.events[-1].data["name"] == "run_powershell"
