"""Cross-platform installer; run with Python 3.11+ from the checkout."""

import shutil
import subprocess
import sys
import venv
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required.")
root = Path(__file__).resolve().parents[1]
for tool in ("ffmpeg", "ffprobe"):
    if not shutil.which(tool):
        raise SystemExit(f"Install {tool} on PATH first; see README.md.")
venv.EnvBuilder(with_pip=True).create(root / ".venv")
python = (
    root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
)
subprocess.run(
    [str(python), "-m", "pip", "install", "-e", str(root) + "[agent]"], check=True
)
print("Installed:", python)
