"""Start one local calculator server and open it from a macOS desktop app."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

PROJECT = Path(__file__).resolve().parents[1]
RUNTIME = PROJECT / "local_data" / "desktop"
BASE_PATH = "kalkulator-" + hashlib.sha256(str(PROJECT).encode()).hexdigest()[:12]
HTTP = build_opener(ProxyHandler({}))


def healthy(port: int) -> bool:
    try:
        with HTTP.open(
            f"http://127.0.0.1:{port}/{BASE_PATH}/_stcore/health", timeout=1
        ) as response:
            return response.status == 200 and response.read(64).strip() == b"ok"
    except (URLError, OSError):
        return False


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def wait_ready(pid: int, port: int) -> bool:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if healthy(port):
            return True
        if not alive(pid):
            return False
        time.sleep(0.2)
    return False


def launch() -> str:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    # One click at a time, including concurrent Finder launches.
    with (RUNTIME / "launch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = RUNTIME / "server.json"
        try:
            state = json.loads(state_path.read_text())
            pid, port = int(state["pid"]), int(state["port"])
            if pid > 0 and 1 <= port <= 65535 and alive(pid):
                if wait_ready(pid, port):
                    return f"http://127.0.0.1:{port}/{BASE_PATH}/"
                raise RuntimeError(
                    "Serwer kalkulatora działa, ale nie odpowiada. "
                    f"Szczegóły: {RUNTIME / 'server.log'}"
                )
        except (OSError, ValueError, KeyError, TypeError):
            pass
        # A dedicated available port avoids conflicts with manually started apps.
        for _ in range(3):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            with (RUNTIME / "server.log").open("ab") as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "streamlit",
                        "run",
                        str(PROJECT / "app.py"),
                        "--server.address=127.0.0.1",
                        f"--server.port={port}",
                        f"--server.baseUrlPath={BASE_PATH}",
                        "--server.headless=true",
                        "--browser.gatherUsageStats=false",
                    ],
                    cwd=PROJECT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            state_path.write_text(json.dumps({"pid": process.pid, "port": port}))
            if wait_ready(process.pid, port):
                return f"http://127.0.0.1:{port}/{BASE_PATH}/"
            if process.poll() is None:
                raise RuntimeError(
                    f"Uruchomienie trwa zbyt długo. Szczegóły: {RUNTIME / 'server.log'}"
                )
        raise RuntimeError(
            f"Nie udało się uruchomić kalkulatora. Szczegóły: {RUNTIME / 'server.log'}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        url = launch()
        if not args.no_browser:
            subprocess.run(["/usr/bin/open", url], check=True)
        print(url)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
