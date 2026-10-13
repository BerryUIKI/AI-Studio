"""Opt-in SDK dependencies live in a provider-owned environment, never core Python."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from app.core.workers import run_blocking
from app.runners.adapter_executor import AdapterError
from app.runtime.worker_ownership import (
    OwnedWorkerTree,
    worker_environment,
    worker_process_options,
)
from app.schemas.custom_provider import CustomProviderRecord, CustomProviderSpec
from app.storage.db import get_default_data_dir


def sdk_directory(spec: CustomProviderSpec, data_dir: Path | None = None) -> Path:
    data_root = (data_dir or get_default_data_dir()).resolve()
    root = data_root / "provider-sdks"
    if not root.resolve().is_relative_to(data_root):
        raise AdapterError("SDK root must remain inside application data")
    revision = hashlib.sha256((spec.requirements + sys.version).encode()).hexdigest()
    target = root / spec.id / revision
    if not target.resolve().is_relative_to(root.resolve()):
        raise AdapterError("SDK environment must remain inside application data")
    return target


def sdk_ready(spec: CustomProviderSpec, data_dir: Path | None = None) -> bool:
    target = sdk_directory(spec, data_dir)
    marker = target / "ready.json"
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
        environment = target / ".venv"
        if not environment.resolve().is_relative_to(target.resolve()):
            return False
        interpreter = environment / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        return interpreter.is_file() and value == {
            "requirements": spec.requirements,
            "python": sys.version,
        }
    except (ValueError, OSError):
        return False


def sdk_module_paths(
    spec: CustomProviderSpec, data_dir: Path | None = None
) -> list[str]:
    target = sdk_directory(spec, data_dir)
    if not sdk_ready(spec, data_dir):
        raise AdapterError(
            "Prepare the approved SDK environment before running this platform"
        )
    environment = target / ".venv"
    directory = (
        environment / "Lib/site-packages"
        if sys.platform == "win32"
        else environment
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    if not directory.resolve().is_relative_to(target.resolve()):
        raise AdapterError("SDK packages must remain inside their isolated environment")
    return [str(directory)]


def sdk_dependency_revision(
    spec: CustomProviderSpec, data_dir: Path | None = None
) -> str:
    """Fingerprint executable package bytes; exclude interpreter-generated caches."""
    directory = Path(sdk_module_paths(spec, data_dir)[0])
    digest = hashlib.sha256((spec.requirements + sys.version).encode())
    for path in sorted(directory.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            if not path.resolve().is_relative_to(directory.resolve()):
                raise AdapterError(
                    "SDK package files must remain in the isolated environment"
                )
            digest.update(str(path.relative_to(directory)).encode())
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
    return digest.hexdigest()


async def prepare_sdk_environment(
    record: CustomProviderRecord, data_dir: Path | None = None
) -> None:
    if record.spec.mode != "python_sdk" or not record.execution_trusted:
        raise AdapterError(
            "SDK preparation requires explicit trust for this descriptor revision"
        )
    spec = record.spec
    target = sdk_directory(spec, data_dir)
    if await run_blocking(sdk_ready, spec, data_dir):
        return
    await run_blocking(target.mkdir, parents=True, exist_ok=True)
    if not (target / ".venv").resolve().is_relative_to(target.resolve()):
        raise AdapterError(
            "SDK environment path points outside application-owned storage"
        )
    requirements = target / "requirements.txt"
    await run_blocking(requirements.write_text, spec.requirements, encoding="utf-8")
    # Code is fixed by Berry; dependency strings are validated, pinned and hashed.
    program = """import json,pathlib,subprocess,sys,venv
spec=json.loads(sys.stdin.readline())
target=pathlib.Path(spec['target'])
environment=target/'.venv'
if not environment.resolve().is_relative_to(target.resolve()): raise RuntimeError('SDK path redirected')
venv.EnvBuilder(with_pip=bool(spec['dependencies']),clear=True).create(environment)
if spec['dependencies']:
    python=environment/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    subprocess.run([str(python),'-m','pip','install','--no-input','--disable-pip-version-check','--require-hashes','--only-binary=:all:','--cache-dir',str(target/'cache'),'-r',str(target/'requirements.txt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
"""
    process = await asyncio.create_subprocess_exec(
        sys._base_executable,
        "-I",
        "-c",
        program,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        env=worker_environment(),
        **worker_process_options(),
    )
    owner = None
    try:
        owner = OwnedWorkerTree(process)
        process.stdin.write(
            (
                json.dumps(
                    {"target": str(target), "dependencies": bool(spec.requirements)}
                )
                + "\n"
            ).encode()
        )
        await process.stdin.drain()
        process.stdin.close()
        code = await asyncio.wait_for(process.wait(), 300)
        if code != 0:
            raise AdapterError(
                "SDK preparation failed. Check pinned dependency versions/hashes and bundled venv/ensurepip support; core Python was not modified."
            )
        marker = {"requirements": spec.requirements, "python": sys.version}
        await run_blocking(
            (target / "ready.json").write_text, json.dumps(marker), encoding="utf-8"
        )
    except asyncio.TimeoutError:
        raise AdapterError(
            "SDK preparation exceeded its deadline; no ready environment was published"
        ) from None
    finally:
        if owner:
            await owner.close()
        else:
            if process.returncode is None:
                process.kill()
            await process.wait()
