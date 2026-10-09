"""Verify runtime relocation and engine bootstrap without host Python or pip."""

import argparse
import importlib
import json
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    for value in (sys.prefix, sys.base_prefix):
        if Path(value).resolve() != runtime:
            raise RuntimeError(f"External Python prefix: {value}; expected {runtime}")
    if Path(sys.executable).resolve() != runtime / "python.exe":
        raise RuntimeError(f"External executable: {sys.executable}")
    for name in ("venv", "ensurepip", "pip", "fastapi", "pydantic", "uvicorn", "httpx", "aiosqlite", "PIL", "multipart"):
        module = importlib.import_module(name)
        if not Path(module.__file__).resolve().is_relative_to(runtime):
            raise RuntimeError(f"External module: {name}: {module.__file__}")
    env_dir = args.work_dir.resolve() / "engine-venv"
    subprocess.run([sys.executable, "-I", "-m", "venv", str(env_dir)], check=True)
    env_python = env_dir / "Scripts" / "python.exe"
    probe = subprocess.run(
        [str(env_python), "-I", "-c", "import sys, pip, json; print(json.dumps([sys.prefix, sys.base_prefix, pip.__file__]))"],
        check=True, capture_output=True, text=True,
    )
    prefix, base, pip_file = json.loads(probe.stdout)
    if Path(prefix).resolve() != env_dir or Path(base).resolve() != runtime:
        raise RuntimeError(f"Engine venv uses an external interpreter: {probe.stdout}")
    if not Path(pip_file).resolve().is_relative_to(env_dir):
        raise RuntimeError(f"Engine pip is outside its sandbox: {pip_file}")
    sys.path.insert(0, str(args.backend.resolve()))
    importlib.import_module("app.main")
    print(f"PASS Python {sys.version.split()[0]}: isolated backend imports, prefixes, venv and pip at {runtime}")


if __name__ == "__main__":
    main()
