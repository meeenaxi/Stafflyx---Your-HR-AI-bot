#!/usr/bin/env python3
"""
NovaCorp HR AI - Launch All Interfaces

Starts Admin (port 7860) and Employee (port 7861) servers as separate subprocesses.
Kills any existing process on those ports first to avoid bind errors on Windows.
"""

import sys
import os
import subprocess
import time
import signal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def kill_port(port: int):
    """Kill whatever is already listening on the given port (Windows + Linux/Mac)."""
    if sys.platform == "win32":
        try:
            # Find PIDs using the port
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    subprocess.run(["taskkill", "/PID", pid, "/F"],
                                   capture_output=True)
                    print(f"  Killed existing process on port {port} (PID {pid})")
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f"tcp:{port}"],
                capture_output=True, text=True
            )
            for pid in result.stdout.strip().splitlines():
                subprocess.run(["kill", "-9", pid], capture_output=True)
                print(f"  Killed existing process on port {port} (PID {pid})")
        except Exception:
            pass


ADMIN_CMD = [
    sys.executable, "-m", "uvicorn",
    "frontend.admin_ui.admin_app:app",
    "--host", "0.0.0.0",
    "--port", "7860",
    "--log-level", "warning",
]

USER_CMD = [
    sys.executable, "-m", "uvicorn",
    "frontend.user_ui.user_app:app",
    "--host", "0.0.0.0",
    "--port", "7861",
    "--log-level", "warning",
]


def main():
    print("""
+--------------------------------------------------------------+
|         NovaCorp HR AI  --  Launching All Interfaces         |
+--------------------------------------------------------------+
|  Admin Console:    http://localhost:7860                     |
|  Employee Portal:  http://localhost:7861                     |
+--------------------------------------------------------------+
    """)

    print("Clearing ports...")
    kill_port(7860)
    kill_port(7861)
    time.sleep(1)

    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT

    admin_proc = subprocess.Popen(ADMIN_CMD, cwd=PROJECT_ROOT, env=env)
    print(f"[Admin]    Started (PID {admin_proc.pid}) -> http://localhost:7860")

    time.sleep(1)

    user_proc = subprocess.Popen(USER_CMD, cwd=PROJECT_ROOT, env=env)
    print(f"[Employee] Started (PID {user_proc.pid}) -> http://localhost:7861")
    print("\nPress Ctrl+C to stop both servers.\n")

    def shutdown(signum, frame):
        print("\nShutting down NovaCorp HR AI...")
        admin_proc.terminate()
        user_proc.terminate()
        try:
            admin_proc.wait(timeout=5)
            user_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            admin_proc.kill()
            user_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(2)
        if admin_proc.poll() is not None:
            code = admin_proc.returncode
            if code != 0:
                print(f"[Admin]    Server exited (code {code}), restarting...")
            kill_port(7860)
            time.sleep(1)
            admin_proc = subprocess.Popen(ADMIN_CMD, cwd=PROJECT_ROOT, env=env)
        if user_proc.poll() is not None:
            code = user_proc.returncode
            if code != 0:
                print(f"[Employee] Server exited (code {code}), restarting...")
            kill_port(7861)
            time.sleep(1)
            user_proc = subprocess.Popen(USER_CMD, cwd=PROJECT_ROOT, env=env)


if __name__ == "__main__":
    main()
