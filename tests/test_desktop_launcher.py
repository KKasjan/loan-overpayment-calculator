"""Desktop lifecycle tests isolate OS/network boundaries and keep real state files."""

import json
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from urllib.error import URLError

import pytest

from scripts import launch_desktop as launcher


@pytest.mark.parametrize(
    "status,body,expected",
    [(200, b"ok\n", True), (503, b"ok", False), (200, b"not ready", False)],
)
def test_health_requires_success_status_and_streamlit_response(
    monkeypatch, status, body, expected
) -> None:
    response = MagicMock(status=status)
    response.read.return_value = body
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value = response
    monkeypatch.setattr(launcher, "HTTP", opener)
    assert launcher.healthy(12345) is expected
    assert str(12345) in opener.open.call_args.args[0]
    assert launcher.BASE_PATH in opener.open.call_args.args[0]


@pytest.mark.parametrize("error", [URLError("offline"), OSError("connection refused")])
def test_health_handles_unavailable_server(monkeypatch, error) -> None:
    opener = Mock()
    opener.open.side_effect = error
    monkeypatch.setattr(launcher, "HTTP", opener)
    assert not launcher.healthy(12345)


@pytest.mark.parametrize(
    "error,expected",
    [(None, True), (ProcessLookupError(), False), (PermissionError(), False)],
)
def test_pid_probe_does_not_send_a_termination_signal(
    monkeypatch, error, expected
) -> None:
    kill = Mock(side_effect=error)
    monkeypatch.setattr(launcher.os, "kill", kill)
    assert launcher.alive(12345) is expected
    kill.assert_called_once_with(12345, 0)


def test_wait_ready_returns_when_server_becomes_healthy(monkeypatch) -> None:
    monkeypatch.setattr(launcher.time, "monotonic", Mock(side_effect=[0, 0, 1]))
    monkeypatch.setattr(launcher, "healthy", Mock(side_effect=[False, True]))
    monkeypatch.setattr(launcher, "alive", lambda pid: True)
    sleep = Mock()
    monkeypatch.setattr(launcher.time, "sleep", sleep)
    assert launcher.wait_ready(123, 456)
    sleep.assert_called_once_with(0.2)


def test_wait_ready_stops_when_process_exits(monkeypatch) -> None:
    monkeypatch.setattr(launcher, "healthy", lambda port: False)
    monkeypatch.setattr(launcher, "alive", lambda pid: False)
    monkeypatch.setattr(
        launcher.time,
        "sleep",
        Mock(side_effect=AssertionError("must not wait on a dead process")),
    )
    assert not launcher.wait_ready(123, 456)


def test_wait_ready_times_out_without_real_sleep(monkeypatch) -> None:
    monkeypatch.setattr(launcher.time, "monotonic", Mock(side_effect=[0, 0, 31]))
    monkeypatch.setattr(launcher, "healthy", lambda port: False)
    monkeypatch.setattr(launcher, "alive", lambda pid: True)
    monkeypatch.setattr(launcher.time, "sleep", Mock())
    assert not launcher.wait_ready(123, 456)


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    directory = tmp_path / "runtime"
    directory.mkdir()
    monkeypatch.setattr(launcher, "RUNTIME", directory)
    probe = MagicMock()
    probe.getsockname.return_value = ("127.0.0.1", 23456)
    socket = MagicMock()
    socket.return_value.__enter__.return_value = probe
    monkeypatch.setattr(launcher.socket, "socket", socket)
    process = Mock(pid=9876)
    process.poll.return_value = 1
    spawn = Mock(return_value=process)
    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    monkeypatch.setattr(launcher, "alive", lambda pid: True)
    monkeypatch.setattr(launcher, "wait_ready", Mock(return_value=True))
    return SimpleNamespace(directory=directory, spawn=spawn, process=process)


def test_first_launch_records_state_and_second_click_reuses_server(runtime) -> None:
    first = launcher.launch()
    second = launcher.launch()
    assert first == second == f"http://127.0.0.1:23456/{launcher.BASE_PATH}/"
    assert json.loads((runtime.directory / "server.json").read_text()) == {
        "pid": 9876,
        "port": 23456,
    }
    runtime.spawn.assert_called_once()
    args = runtime.spawn.call_args
    assert "--server.address=127.0.0.1" in args.args[0]
    assert args.kwargs["start_new_session"] is True


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "{}",
        "[]",
        '{"pid": "invalid", "port": 1000}',
        '{"pid": -1, "port": 1000}',
        '{"pid": 123, "port": 0}',
    ],
)
def test_invalid_saved_state_is_replaced_after_successful_start(
    runtime, content
) -> None:
    path = runtime.directory / "server.json"
    path.write_text(content)
    assert launcher.launch().startswith("http://127.0.0.1:")
    assert json.loads(path.read_text())["pid"] == 9876
    runtime.spawn.assert_called_once()


def test_stale_pid_starts_new_server(runtime, monkeypatch) -> None:
    (runtime.directory / "server.json").write_text('{"pid":123,"port":456}')
    monkeypatch.setattr(launcher, "alive", lambda pid: False)
    launcher.launch()
    runtime.spawn.assert_called_once()


def test_live_but_unresponsive_server_does_not_spawn_duplicate(
    runtime, monkeypatch
) -> None:
    (runtime.directory / "server.json").write_text('{"pid":123,"port":456}')
    monkeypatch.setattr(launcher, "wait_ready", Mock(return_value=False))
    with pytest.raises(RuntimeError, match="running but not responding"):
        launcher.launch()
    runtime.spawn.assert_not_called()


def test_failed_start_retries_then_reports_log(runtime, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "wait_ready", Mock(return_value=False))
    with pytest.raises(RuntimeError, match="Could not start") as caught:
        launcher.launch()
    assert "server.log" in str(caught.value)
    assert runtime.spawn.call_count == 3


def test_slow_live_start_does_not_create_another_process(runtime, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "wait_ready", Mock(return_value=False))
    runtime.process.poll.return_value = None
    with pytest.raises(RuntimeError, match="taking too long"):
        launcher.launch()
    runtime.spawn.assert_called_once()


def test_desktop_command_opens_default_browser(monkeypatch, capsys) -> None:
    monkeypatch.setattr(launcher, "launch", lambda: "http://127.0.0.1:1234/")
    run = Mock()
    monkeypatch.setattr(launcher.subprocess, "run", run)
    assert launcher.main([]) == 0
    run.assert_called_once_with(["/usr/bin/open", "http://127.0.0.1:1234/"], check=True)
    assert capsys.readouterr().out.strip() == "http://127.0.0.1:1234/"


def test_desktop_no_browser_mode_only_prints_url(monkeypatch, capsys) -> None:
    monkeypatch.setattr(launcher, "launch", lambda: "http://127.0.0.1:1234/")
    run = Mock()
    monkeypatch.setattr(launcher.subprocess, "run", run)
    assert launcher.main(["--no-browser"]) == 0
    run.assert_not_called()
    assert capsys.readouterr().out.strip() == "http://127.0.0.1:1234/"


@pytest.mark.parametrize(
    "error",
    [
        OSError("access denied"),
        RuntimeError("startup failed"),
        subprocess.SubprocessError("browser failed"),
    ],
)
def test_desktop_failure_returns_nonzero_exit_code(monkeypatch, capsys, error) -> None:
    monkeypatch.setattr(launcher, "launch", Mock(side_effect=error))
    assert launcher.main(["--no-browser"]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert str(error) in captured.err


def test_executable_entry_point_supports_help_without_starting_server(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr("sys.argv", [str(Path(launcher.__file__)), "--help"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(launcher.__file__, run_name="__main__")
    assert caught.value.code == 0
    assert "--no-browser" in capsys.readouterr().out


def test_server_exiting_during_readiness_check_can_be_restarted(
    runtime, monkeypatch
) -> None:
    (runtime.directory / "server.json").write_text('{"pid":123,"port":456}')
    monkeypatch.setattr(launcher, "alive", Mock(side_effect=[True, False]))
    monkeypatch.setattr(launcher, "wait_ready", Mock(side_effect=[False, True]))
    assert launcher.launch() == f"http://127.0.0.1:23456/{launcher.BASE_PATH}/"
    runtime.spawn.assert_called_once()


def test_simultaneous_launches_share_one_server(runtime) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ready = Barrier(2)

    def click() -> str:
        ready.wait(timeout=5)
        return launcher.launch()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(click), executor.submit(click)]
        urls = [future.result(timeout=5) for future in futures]
    assert urls[0] == urls[1]
    runtime.spawn.assert_called_once()
