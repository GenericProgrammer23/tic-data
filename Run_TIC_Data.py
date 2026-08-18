from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import venv
import webbrowser
import zipfile
from pathlib import Path

# Current development branch. After the first release this can point to main.
DOWNLOAD_URL = (
    "https://codeload.github.com/GenericProgrammer23/tic-data/"
    "zip/refs/heads/agent/initial-tic-data-mvp"
)

if os.name == "nt":
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    APP_HOME = base / "TICData"
else:
    APP_HOME = Path.home() / ".tic-data"

CODE_DIR = APP_HOME / "app"
VENV_DIR = APP_HOME / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def download_latest_source() -> None:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    print("Checking/downloading TIC Data...")

    try:
        with tempfile.TemporaryDirectory(prefix="tic-data-download-") as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "tic-data.zip"

            request = urllib.request.Request(
                DOWNLOAD_URL,
                headers={"User-Agent": "TIC-Data-Launcher/1.0"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                archive.write_bytes(response.read())

            extract_dir = tmp_path / "extracted"
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(extract_dir)

            roots = [p for p in extract_dir.iterdir() if p.is_dir()]
            if len(roots) != 1:
                raise RuntimeError("Unexpected project ZIP layout.")

            new_code = roots[0]
            if CODE_DIR.exists():
                shutil.rmtree(CODE_DIR)
            shutil.copytree(new_code, CODE_DIR)

    except Exception as exc:
        if CODE_DIR.exists() and (CODE_DIR / "pyproject.toml").exists():
            print(f"Could not download an update ({exc}).")
            print("Starting the most recently downloaded TIC Data instead.")
            return
        raise RuntimeError(f"Could not download TIC Data: {exc}") from exc


def ensure_venv() -> Path:
    python = venv_python()
    if not python.exists():
        print("First run: creating a private Python environment...")
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    return python


def install_project(python: Path) -> None:
    print("Preparing TIC Data...")
    subprocess.check_call(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-e",
            str(CODE_DIR),
        ],
        cwd=CODE_DIR,
    )


def find_port(start: int = 8000, end: int = 8010) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free local port was found between {start} and {end}.")


def wait_for_server(port: int, process: subprocess.Popen, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("TIC Data stopped before the browser could connect.")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.25)
    raise RuntimeError("TIC Data did not start within 30 seconds.")


def main() -> int:
    process = None
    try:
        print("=" * 55)
        print("TIC Data")
        print("=" * 55)

        download_latest_source()
        python = ensure_venv()
        install_project(python)

        port = find_port()
        url = f"http://127.0.0.1:{port}"

        print()
        print(f"Starting TIC Data: {url}")
        print("Your browser will open automatically.")
        print("Leave this window/program running while using TIC Data.")
        print("Press Ctrl+C when finished.")
        print()

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
            cwd=CODE_DIR,
        )

        wait_for_server(port, process)
        webbrowser.open(url)

        try:
            return process.wait()
        except KeyboardInterrupt:
            return 0

    except Exception as exc:
        print()
        print("TIC Data could not start.")
        print(exc)
        print()
        print("If you are running this in VS Code, copy this error back into ChatGPT.")
        try:
            input("Press Enter to close...")
        except EOFError:
            pass
        return 1

    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
