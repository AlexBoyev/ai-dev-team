from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"
ENV_FILE     = Path(__file__).parent / ".env"
APP_URL      = "http://localhost:3000"
HEALTH_URL   = "http://localhost:3000/api/state"  # ← through Nginx now

DOCKER_DESKTOP_PATHS = [
    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Docker\Docker Desktop.exe"),
]


def _run(cmd: list[str], capture: bool = False, shell: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, shell=shell)


def _check_docker_running() -> bool:
    return _run(["docker", "info"], capture=True).returncode == 0


def _start_docker_desktop() -> None:
    print("Docker is not running. Attempting to start Docker Desktop...")

    if sys.platform == "win32":
        docker_exe = next((p for p in DOCKER_DESKTOP_PATHS if Path(p).exists()), None)
        if docker_exe:
            print(f"Found Docker Desktop at: {docker_exe}")
            subprocess.Popen([docker_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen("start Docker Desktop", shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Docker"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["sudo", "systemctl", "start", "docker"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("Waiting for Docker to start", end="", flush=True)
    for _ in range(30):
        time.sleep(2)
        print(".", end="", flush=True)
        if _check_docker_running():
            print(" ready.")
            return

    print()
    print("ERROR: Docker did not start in 60 seconds. Start it manually then re-run.")
    sys.exit(1)


def _ensure_env_file() -> None:
    if not ENV_FILE.exists():
        example = Path(__file__).parent / ".env.example"
        if example.exists():
            import shutil
            shutil.copy(example, ENV_FILE)
            print("Created .env from .env.example")
        else:
            print("ERROR: .env file not found and .env.example is missing.")
            sys.exit(1)


def _compose_up() -> None:
    print("\n── Building and starting containers ──────────────────────────")
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "--build", "-d"],
        text=True,
    )
    if result.returncode != 0:
        print("\nERROR: docker compose up failed.")
        print("Run:  docker compose logs")
        sys.exit(1)


def _wait_for_app() -> None:
    import urllib.request

    print("\n── Waiting for app to be ready ───────────────────────────────")
    for attempt in range(50):
        time.sleep(3)
        try:
            urllib.request.urlopen(HEALTH_URL, timeout=3)
            print(f"  Ready after ~{(attempt + 1) * 3}s")
            return
        except Exception:
            print(f"  [{attempt + 1}/50] Not ready yet...", end="\r")

    print("\nWARN: App may still be starting. Try opening manually:")
    print(f"  {APP_URL}")


def _print_logs_brief() -> None:
    print("\n── Recent deployment logs ────────────────────────────────────")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "logs",
         "--tail=15", "app", "worker", "frontend"],
        text=True,
    )


def _tail_logs() -> None:
    print("\n── Live logs (Ctrl+C to stop, containers keep running) ───────")
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "logs",
             "--follow", "--tail=15", "app", "worker"],
            text=True,
        )
    except KeyboardInterrupt:
        pass

    print("\n\nStopped following logs. Everything still running.\n")
    print(f"  UI        →  {APP_URL}")
    print( "  Stop all  →  docker compose down")
    print( "  All logs  →  docker compose logs -f\n")


def main() -> None:
    print("=" * 60)
    print("  AI Dev Team — startup")
    print("=" * 60)

    if not _check_docker_running():
        _start_docker_desktop()

    _ensure_env_file()
    _compose_up()
    _wait_for_app()
    _print_logs_brief()

    print("\n" + "=" * 60)
    print(f"  ✓  UI is live  →  {APP_URL}")
    print("=" * 60 + "\n")

    _tail_logs()


if __name__ == "__main__":
    main()
