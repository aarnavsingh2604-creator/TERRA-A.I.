"""Launch TERRA AI frontend and both backend services locally."""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
commands = [
    [sys.executable, str(ROOT / "backend_api.py")],
    [sys.executable, str(ROOT / "backend2_api.py")],
    [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py")],
]
processes = []
try:
    for command in commands:
        processes.append(subprocess.Popen(command, cwd=ROOT))
        time.sleep(1)
    print("TERRA AI services launched:")
    print("  Frontend:  http://localhost:8501")
    print("  Backend 1: http://127.0.0.1:5001")
    print("  Backend 2: http://127.0.0.1:5002")
    print("Press Ctrl+C to stop all services.")
    while True:
        for process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"A service exited with code {process.returncode}")
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping TERRA AI...")
finally:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
