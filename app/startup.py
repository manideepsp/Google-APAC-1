import signal
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass
class ServiceProcess:
    name: str
    command: list[str]
    process: subprocess.Popen | None = None


SERVICES = [
    ServiceProcess("YouTube gRPC", [sys.executable, "-m", "app.services.youtube_service"]),
    ServiceProcess("Sheets gRPC", [sys.executable, "-m", "app.services.sheets_service"]),
    ServiceProcess(
        "FastAPI UI/API",
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
    ),
]


def start_services() -> None:
    for service in SERVICES:
        print(f"[startup] starting {service.name}...")
        service.process = subprocess.Popen(service.command)


def stop_services() -> None:
    for service in SERVICES:
        process = service.process
        if process is None:
            continue

        if process.poll() is None:
            print(f"[startup] stopping {service.name} (pid={process.pid})...")
            process.terminate()

    deadline = time.time() + 5
    for service in SERVICES:
        process = service.process
        if process is None:
            continue

        if process.poll() is not None:
            continue

        remaining = deadline - time.time()
        if remaining > 0:
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                pass

        if process.poll() is None:
            print(f"[startup] force killing {service.name} (pid={process.pid})...")
            process.kill()


def watch_services() -> int:
    while True:
        for service in SERVICES:
            process = service.process
            if process is None:
                continue

            code = process.poll()
            if code is not None:
                print(f"[startup] {service.name} exited with code {code}")
                return code

        time.sleep(0.5)


def main() -> int:
    def _handle_signal(signum, _frame):
        print(f"\n[startup] received signal {signum}, shutting down...")
        stop_services()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        start_services()
        print("[startup] all services started. Press Ctrl+C to stop.")
        return watch_services()
    except KeyboardInterrupt:
        print("\n[startup] interrupted, shutting down...")
        return 0
    finally:
        stop_services()


if __name__ == "__main__":
    raise SystemExit(main())
