from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
INSTALL_MARKER = VENV_DIR / ".tic-data-install"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_project() -> None:
    if not PYPROJECT.exists():
        raise RuntimeError(
            "pyproject.toml was not found. Keep Start_TIC_Data.py in the root "
            "of the extracted tic-data project folder."
        )


def ensure_venv() -> Path:
    python = venv_python()
    if not python.exists():
        print("First run: creating a private Python environment...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    return python


def install_if_needed(python: Path) -> None:
    fingerprint = str(PYPROJECT.stat().st_mtime_ns)
    current = INSTALL_MARKER.read_text(encoding="utf-8").strip() if INSTALL_MARKER.exists() else ""

    if current == fingerprint:
        return

    print("Installing/updating TIC Data dependencies...")
    subprocess.check_call(
        [str(python), "-m", "pip", "install", "-e", str(PROJECT_ROOT)],
        cwd=PROJECT_ROOT,
    )
    INSTALL_MARKER.write_text(fingerprint, encoding="utf-8")


def find_port(start: int = 8000, end: int = 8010) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free local port was found between {start} and {end}.")


def wait_for_server(port: int, process: subprocess.Popen, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("TIC Data stopped before the browser could connect.")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError("TIC Data did not start within 20 seconds.")


def main() -> int:
    try:
        ensure_project()
        python = ensure_venv()
        install_if_needed(python)
        port = find_port()
        url = f"http://127.0.0.1:{port}"

        print(f"Starting TIC Data at {url}")
        print("Leave this window open while using TIC Data.")
        print("Press Ctrl+C here when you are finished.")

        process = subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "tic_data.service:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=PROJECT_ROOT,
        )

        wait_for_server(port, process)
        webbrowser.open(url)

        try:
            return process.wait()
        except KeyboardInterrupt:
            print("\nStopping TIC Data...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return 0

    except Exception as exc:
        print(f"\nTIC Data could not start:\n{exc}")
        print("\nPress Enter to close this window.")
        try:
            input()
        except EOFError:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
