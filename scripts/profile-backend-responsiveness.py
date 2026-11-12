"""Measure real isolated HTTP scans/imports without engines or paid requests.

Run the same dataset and interpreter against both handover commits. Generated
safetensors are indexing fixtures, never inference models. Cold means a fresh
application index, not an evicted OS filesystem cache. Raw samples stay external.
"""

import argparse
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import socket
import struct
import subprocess
import sys
import time
from typing import Any

import httpx
from PIL import Image


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def dataset(root: Path, count: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        size = 256 * 1024 * 1024 if index == 0 else 16
        path = root / f"indexing-only-{index:05d}.safetensors"
        if path.exists():
            continue
        header = json.dumps({"fixture": {"dtype": "U8", "shape": [size],
                                        "data_offsets": [0, size]}}).encode()
        with path.open("wb") as target:
            target.write(struct.pack("<Q", len(header)))
            target.write(header)
            target.seek(size - 1, os.SEEK_CUR)
            target.write(b"\0")


async def measure(client: httpx.AsyncClient, name: str, method: str, path: str,
                  **kwargs: Any) -> dict[str, Any]:
    samples: dict[str, list[float]] = {"health": [], "missing_task": []}
    statuses: dict[str, list[int]] = {key: [] for key in samples}
    finished = asyncio.Event()

    async def probe(key: str, endpoint: str) -> None:
        while not finished.is_set():
            start = time.perf_counter()
            response = await client.get(endpoint)
            samples[key].append((time.perf_counter() - start) * 1000)
            statuses[key].append(response.status_code)
            await asyncio.sleep(0.1)

    probes = [asyncio.create_task(probe("health", "/health")),
              asyncio.create_task(probe("missing_task", "/api/v1/creative/tasks/profiler-missing"))]
    start = time.perf_counter()
    try:
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        elapsed = (time.perf_counter() - start) * 1000
    finally:
        finished.set()
        await asyncio.gather(*probes)
    summary = {key: {"count": len(values), "p50_ms": percentile(values, .5),
                     "p95_ms": percentile(values, .95), "max_ms": max(values)}
               for key, values in samples.items()}
    if any(code != 200 for code in statuses["health"]) or any(
        code != 404 for code in statuses["missing_task"]
    ):
        raise RuntimeError("Unexpected health/task status during profiling")
    return {"operation": name, "elapsed_ms": elapsed, "status": response.status_code,
            "summary": summary, "samples_ms": samples, "statuses": statuses}


async def run(args: argparse.Namespace) -> None:
    repo = args.repo.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    buffer = io.BytesIO()
    # Real 48 MiB uncompressed PNG exercises decoding, hashing, persistence and DB writes.
    with Image.new("RGB", (4096, 4096), "purple") as image:
        image.save(buffer, "PNG", compress_level=0)
    media = buffer.getvalue()
    report: dict[str, Any] = {"commit": commit, "python": sys.version,
                             "platform": platform.platform(), "started_utc": time.strftime(
                                 "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                             "dataset": {"counts": args.counts, "large_file_bytes": 268435456,
                                         "inference_models": False, "os_cache_evicted": False},
                             "upload": {"bytes": len(media), "sha256": hashlib.sha256(media).hexdigest()},
                             "runs": []}
    for count in args.counts:
        library = args.dataset.resolve() / str(count)
        dataset(library, count)
        for repetition in range(args.repetitions):
            isolated = output / f"{count}-{repetition}"
            isolated.mkdir()
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            env = os.environ.copy()
            env.update(BERRY_DATA_DIR=str(isolated / "data"),
                       AI_WORKFLOW_ENGINE_DIR=str(isolated / "engines"), BERRY_PORT=str(port))
            with (isolated / "server.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                                            "--host", "127.0.0.1", "--port", str(port),
                                            "--no-access-log"], cwd=repo / "backend", env=env,
                                           stdout=log, stderr=log)
                try:
                    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}",
                                                 timeout=120, trust_env=False) as client:
                        for attempt in range(200):
                            if process.poll() is not None:
                                raise RuntimeError(f"Backend exited; inspect {isolated / 'server.log'}")
                            try:
                                (await client.get("/health")).raise_for_status()
                                break
                            except httpx.ConnectError:
                                await asyncio.sleep(.1)
                        else:
                            raise RuntimeError("Backend did not become healthy")
                        added = await client.post("/api/v1/models/roots", json={
                            "path": str(library), "label": "Indexing fixtures"})
                        added.raise_for_status()
                        records = []
                        for label in ("cold_index_scan", "warm_incremental_scan"):
                            records.append(await measure(client, label, "POST", "/api/v1/models/rescan"))
                        for poll in range(10):
                            records.append(await measure(client, "routine_manager_poll", "GET",
                                                         "/api/v1/manager/status"))
                        records.append(await measure(client, "media_import", "POST",
                                                     "/api/v1/creative/upload", files={
                                                         "file": ("profile.png", media, "image/png")}))
                        records.append(await measure(client, "hardware_probe", "GET",
                                                     "/api/v1/hardware/readiness"))
                        report["runs"].append({"count": count, "repetition": repetition,
                                               "records": records})
                        (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                        print(f"{commit[:12]} {count} files repetition {repetition + 1}: "
                              f"cold {records[0]['elapsed_ms']:.1f} ms, "
                              f"warm {records[1]['elapsed_ms']:.1f} ms", flush=True)
                finally:
                    # The retained Popen handle identifies only this profiler's backend.
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--counts", type=int, nargs="+", default=[1000, 10000])
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 1 or any(count < 1 for count in args.counts):
        parser.error("Counts and repetitions must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
