from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"
ENV_FILE     = Path(__file__).parent / ".env"
APP_URL      = "http://localhost:8010"
HEALTH_URL   = "http://localhost:8010/api/state"

# Common Docker Desktop install paths on Windows
DOCKER_DESKTOP_PATHS = [
    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Docker\Docker Desktop.exe"),
]


def _run(cmd: list[str], capture: bool = False, shell: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        shell=shell,
    )


def _check_docker_running() -> bool:
    result = _run(["docker", "info"], capture=True)
    return result.returncode == 0


def _start_docker_desktop() -> None:
    print("Docker is not running. Attempting to start Docker Desktop...")

    if sys.platform == "win32":
        # Find Docker Desktop executable
        docker_exe = None
        for path in DOCKER_DESKTOP_PATHS:
            if Path(path).exists():
                docker_exe = path
                break

        if docker_exe:
            print(f"Found Docker Desktop at: {docker_exe}")
            subprocess.Popen(
                [docker_exe],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Fallback: try via shell start command
            print("Docker Desktop exe not found, trying shell start...")
            subprocess.Popen(
                "start Docker Desktop",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    elif sys.platform == "darwin":
        subprocess.Popen(
            ["open", "-a", "Docker"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        # Linux
        subprocess.Popen(
            ["sudo", "systemctl", "start", "docker"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print("Waiting for Docker to start", end="", flush=True)
    for _ in range(30):
        time.sleep(2)
        print(".", end="", flush=True)
        if _check_docker_running():
            print(" ready.")
            return

    print()
    print("ERROR: Docker did not start in 60 seconds.")
    print("Please start Docker Desktop manually, then re-run driver.py")
    sys.exit(1)


def _ensure_env_file() -> None:
    if not ENV_FILE.exists():
        example = Path(__file__).parent / ".env.example"
        if example.exists():
            import shutil
            shutil.copy(example, ENV_FILE)
            print(f"Created .env from .env.example")
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
        print("Run this to see full error:")
        print("  docker compose logs")
        sys.exit(1)


def _wait_for_app() -> None:
    import urllib.request
    import urllib.error

    print("\n── Waiting for app to be ready ───────────────────────────────")
    for attempt in range(40):
        time.sleep(3)
        try:
            urllib.request.urlopen(HEALTH_URL, timeout=3)
            print(f"  App is ready after ~{(attempt + 1) * 3}s")
            return
        except Exception:
            print(f"  [{attempt + 1}/40] Not ready yet...", end="\r")

    print("\nERROR: App did not become ready in time.")
    print("Check logs with:  docker compose logs app")
    sys.exit(1)


def _print_logs_brief() -> None:
    print("\n── Recent deployment logs ────────────────────────────────────")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "logs",
         "--tail=30", "app", "worker"],
        text=True,
    )


def _tail_logs() -> None:
    print("\n── Live logs (Ctrl+C to stop following, app stays running) ───")
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "logs",
             "--follow", "--tail=20", "app", "worker"],
            text=True,
        )
    except KeyboardInterrupt:
        pass

    print("\n\nStopped following logs. Containers are still running.")
    print(f"\n  Dashboard  →  {APP_URL}")
    print(  "  Stop all   →  docker compose down")
    print(  "  All logs   →  docker compose logs -f\n")


def main() -> None:
    print("=" * 60)
    print("  AI Dev Team — startup")
    print("=" * 60)

    # 1. Check Docker is running
    if not _check_docker_running():
        _start_docker_desktop()

    # 2. Ensure .env exists
    _ensure_env_file()

    # 3. Build + start all containers
    _compose_up()

    # 4. Wait for FastAPI health check
    _wait_for_app()

    # 5. Print last 30 lines of logs
    _print_logs_brief()

    # 6. Print URL
    print("\n" + "=" * 60)
    print(f"  ✓  App is running  →  {APP_URL}")
    print("=" * 60 + "\n")

    # 7. Tail live logs until Ctrl+C
    _tail_logs()


if __name__ == "__main__":
    main()
