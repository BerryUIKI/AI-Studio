"""Open a configured local directory using the platform file manager."""

import os
from pathlib import Path
import subprocess
import sys


def open_directory(directory: Path) -> None:
    directory = directory.resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory does not exist: {directory}")
    if sys.platform == "win32":
        os.startfile(str(directory))
    else:
        command = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.run([command, str(directory)], check=True, timeout=5, capture_output=True)
