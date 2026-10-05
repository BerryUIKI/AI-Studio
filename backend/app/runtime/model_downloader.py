"""Multi-mirror resumable model download engine and supervisor (MH-M4)."""

import os
import sys
import time
import asyncio
import uuid
import hashlib
import httpx
from pathlib import Path
from typing import Dict, List, Optional

from app.storage.hub_catalog import HubCatalog
from app.storage.model_store import model_store
from app.runtime.installer import mirror_manager, installer
from app.schemas.model_hub import (
    HubModelRecord,
    DownloadTaskInfo,
    DownloadTaskStatus,
)


class DownloadWorker:
    def __init__(
        self,
        task_id: str,
        model: HubModelRecord,
        target_engine: str,
        target_path: Path,
        source_url: str,
    ):
        self.task_id = task_id
        self.model = model
        self.target_engine = target_engine
        self.target_path = target_path
        self.part_path = target_path.with_name(f"{target_path.name}.part")
        self.source_url = source_url

        self.status: DownloadTaskStatus = "pending"
        self.total_bytes = model.size_bytes
        self.downloaded_bytes = 0
        self.speed_bps = 0
        self.eta_seconds: Optional[int] = None
        self.error_message: Optional[str] = None

        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
        self._cancel_flag = False
        self._task: Optional[asyncio.Task] = None

    def to_info(self) -> DownloadTaskInfo:
        pct = (
            round((self.downloaded_bytes / self.total_bytes) * 100, 1)
            if self.total_bytes > 0
            else 0.0
        )
        return DownloadTaskInfo(
            task_id=self.task_id,
            model_id=self.model.id,
            model_name=self.model.name,
            target_engine=self.target_engine,
            target_path=str(self.target_path),
            status=self.status,
            total_bytes=self.total_bytes,
            downloaded_bytes=self.downloaded_bytes,
            progress_pct=min(100.0, pct),
            speed_bps=self.speed_bps,
            eta_seconds=self.eta_seconds,
            error_message=self.error_message,
        )

    async def _download_loop(self, candidate_urls: List[str], headers: dict, existing_bytes: int) -> bool:
        """Download bytes from candidate URLs into part_path."""
        last_time = time.monotonic()
        bytes_since_last = 0
        last_error = None
        download_success = False

        for url in candidate_urls:
            if self._cancel_flag:
                self.status = "cancelled"
                return False

            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=15.0, read=180.0, write=60.0, pool=15.0),
                    follow_redirects=True,
                    trust_env=False,
                ) as client:
                    async with client.stream("GET", url, headers=headers) as response:
                        if response.status_code in [200, 206]:
                            content_range = response.headers.get("content-range")
                            content_length = response.headers.get("content-length")

                            # Validate partial content resumption
                            if existing_bytes > 0:
                                if response.status_code == 206:
                                    # Expected Content-Range format: bytes START-END/TOTAL
                                    if content_range:
                                        try:
                                            range_spec = content_range.split()[1]
                                            start_byte = int(range_spec.split("-")[0])
                                            if start_byte != existing_bytes:
                                                # Incompatible range returned by server, reset and redownload from 0
                                                existing_bytes = 0
                                                mode = "wb"
                                                self.downloaded_bytes = 0
                                            else:
                                                mode = "ab"
                                                total_str = range_spec.split("/")[-1]
                                                if total_str != "*":
                                                    self.total_bytes = int(total_str)
                                        except Exception:
                                            existing_bytes = 0
                                            mode = "wb"
                                            self.downloaded_bytes = 0
                                    else:
                                        mode = "ab"
                                else:
                                    # Server returned 200 instead of 206: entire file being sent from 0
                                    mode = "wb"
                                    self.downloaded_bytes = 0
                                    existing_bytes = 0
                                    if content_length:
                                        self.total_bytes = int(content_length)
                            else:
                                mode = "wb"
                                self.downloaded_bytes = 0
                                if content_length:
                                    self.total_bytes = int(content_length)

                            with open(self.part_path, mode) as f:
                                async for chunk in response.aiter_bytes(chunk_size=65536):
                                    if self._cancel_flag:
                                        self.status = "cancelled"
                                        if self.part_path.exists():
                                            try:
                                                self.part_path.unlink()
                                            except Exception:
                                                pass
                                        return False

                                    while not self._pause_event.is_set():
                                        self.status = "paused"
                                        self.speed_bps = 0
                                        await asyncio.sleep(0.5)
                                        if self._cancel_flag:
                                            self.status = "cancelled"
                                            return False
                                        self.status = "downloading"

                                    f.write(chunk)
                                    chunk_len = len(chunk)
                                    self.downloaded_bytes += chunk_len
                                    bytes_since_last += chunk_len

                                    now = time.monotonic()
                                    elapsed = now - last_time
                                    if elapsed >= 1.0:
                                        self.speed_bps = int(bytes_since_last / elapsed)
                                        remaining_bytes = max(0, self.total_bytes - self.downloaded_bytes)
                                        self.eta_seconds = (
                                            int(remaining_bytes / self.speed_bps)
                                            if self.speed_bps > 0
                                            else None
                                        )
                                        last_time = now
                                        bytes_since_last = 0

                            download_success = True
                            break
                        else:
                            last_error = f"HTTP {response.status_code} from {url}"
            except Exception as e:
                last_error = str(e)
                continue

        if not download_success:
            if not self._cancel_flag:
                self.status = "failed"
                self.error_message = f"Failed to download model across candidate sources: {last_error}"
                self.speed_bps = 0
            return False

        return True

    async def run(self):
        self.status = "downloading"
        self.target_path.parent.mkdir(parents=True, exist_ok=True)

        existing_bytes = 0
        if self.part_path.exists():
            existing_bytes = self.part_path.stat().st_size
            self.downloaded_bytes = existing_bytes

        headers = {}
        if existing_bytes > 0:
            headers["Range"] = f"bytes={existing_bytes}-"

        # Build candidate URL list with selected source_url first, followed by all alternative sources
        candidate_urls = [self.source_url] if self.source_url else []
        for src in self.model.sources:
            if src.url and src.url not in candidate_urls:
                candidate_urls.append(src.url)

        download_success = await self._download_loop(candidate_urls, headers, existing_bytes)
        if not download_success:
            return

        # Verification: size and checksum checks before promotion
        if not self.part_path.exists():
            self.status = "failed"
            self.error_message = "Downloaded part file does not exist."
            self.speed_bps = 0
            return

        actual_size = self.part_path.stat().st_size

        # Check size if total_bytes / model.size_bytes is declared
        expected_size = self.total_bytes or self.model.size_bytes
        if expected_size and actual_size != expected_size:
            self.status = "failed"
            self.error_message = (
                f"Downloaded artifact size mismatch: expected {expected_size} bytes, "
                f"got {actual_size} bytes."
            )
            self.speed_bps = 0
            return

        # Check sha256 checksum if provided by catalog or record
        if self.model.sha256:
            hasher = hashlib.sha256()
            with open(self.part_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_sha256 = hasher.hexdigest().lower()
            expected_sha256 = self.model.sha256.strip().lower()
            if actual_sha256 != expected_sha256:
                self.status = "failed"
                self.error_message = (
                    f"Downloaded artifact SHA-256 integrity mismatch: expected {expected_sha256}, "
                    f"got {actual_sha256}."
                )
                self.speed_bps = 0
                return

        # Download and integrity verified: atomic replace to destination
        # On Windows, os.replace / Path.replace will atomically overwrite target_path without unlinking it first.
        # If replace fails, the previous target_path is preserved!
        try:
            self.part_path.replace(self.target_path)

            self.status = "completed"
            self.downloaded_bytes = actual_size
            self.speed_bps = 0
            self.eta_seconds = 0

            # Trigger model catalog hot rescan so the model is immediately usable
            try:
                await model_store.scan_all_roots_async()
            except Exception:
                pass

            # Notify llama_server_supervisor if category is llm
            if self.model.category == "llm":
                try:
                    from app.runtime.llama_server.llama_supervisor import llama_server_supervisor
                    llama_server_supervisor.list_local_models()
                except Exception:
                    pass

        except Exception as e:
            if not self._cancel_flag:
                self.status = "failed"
                self.error_message = f"Atomic promotion to destination failed: {e}"
                self.speed_bps = 0


class ModelDownloader:
    """Orchestrates model downloads with mirror selection and queue tracking."""

    def __init__(self):
        self._workers: Dict[str, DownloadWorker] = {}

    def _resolve_target_path(self, model: HubModelRecord, target_engine: str) -> Path:
        """Resolve engine destination directory based on model category."""
        filename = Path(model.sources[0].url.split("?")[0]).name if model.sources else f"{model.id}.safetensors"
        if not filename.endswith((".safetensors", ".pth", ".bin", ".gguf")):
            filename = f"{filename}.safetensors"

        # Determine engine root - use consistent engine_dir for all engines
        engine_root = installer.engine_dir

        if target_engine in ("comfyui", "llama_server"):
            # ComfyUI shared model paths (engine/models/)
            if model.category == "checkpoint":
                sub = engine_root / "models" / "checkpoints"
            elif model.category == "lora":
                sub = engine_root / "models" / "loras"
            elif model.category == "controlnet":
                sub = engine_root / "models" / "controlnet"
            elif model.category == "upscaler":
                sub = engine_root / "models" / "upscale_models"
            elif model.category == "vae":
                sub = engine_root / "models" / "vae"
            elif model.category == "llm":
                sub = engine_root / "models" / "llm"
            else:
                sub = engine_root / "models" / "other"
        else:
            # WebUI - use engine_dir/webui_models/ to match supervisor configuration
            webui_models = engine_root / "models"
            if model.category == "checkpoint":
                sub = webui_models / "checkpoints"
            elif model.category == "lora":
                sub = webui_models / "loras"
            elif model.category == "controlnet":
                sub = webui_models / "controlnet"
            elif model.category == "upscaler":
                sub = webui_models / "upscale_models"
            elif model.category == "vae":
                sub = webui_models / "vae"
            elif model.category == "llm":
                sub = webui_models / "llm"
            else:
                sub = webui_models / "other"

        return sub / filename

    def _select_source_url(self, model: HubModelRecord, mirror_preset: Optional[str]) -> str:
        """Select best URL based on active mirror configuration."""
        active_preset = mirror_preset or mirror_manager.get_config().active_preset
        if active_preset == "china_mainland":
            # Find mirror link first
            for src in model.sources:
                if "Mirror" in src.name or "ModelScope" in src.name or "hf-mirror" in src.url:
                    return src.url

        if model.sources:
            return model.sources[0].url
        return ""

    def start_download(
        self,
        model_id: str,
        target_engine: str = "comfyui",
        mirror_preset: Optional[str] = None,
    ) -> DownloadTaskInfo:
        model = HubCatalog.get_model(model_id)
        if not model:
            raise ValueError(f"Model '{model_id}' not found in catalog")

        # Check if already active
        for worker in self._workers.values():
            if worker.model.id == model_id and worker.status in ["downloading", "pending", "paused"]:
                return worker.to_info()

        task_id = f"dl_{uuid.uuid4().hex[:8]}"
        target_path = self._resolve_target_path(model, target_engine)
        source_url = self._select_source_url(model, mirror_preset)

        worker = DownloadWorker(
            task_id=task_id,
            model=model,
            target_engine=target_engine,
            target_path=target_path,
            source_url=source_url,
        )

        self._workers[task_id] = worker
        loop = asyncio.get_event_loop()
        worker._task = loop.create_task(worker.run())

        return worker.to_info()

    def list_tasks(self) -> List[DownloadTaskInfo]:
        return [w.to_info() for w in self._workers.values()]

    def pause_task(self, task_id: str) -> bool:
        worker = self._workers.get(task_id)
        if worker and worker.status == "downloading":
            worker._pause_event.clear()
            worker.status = "paused"
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        worker = self._workers.get(task_id)
        if worker and worker.status == "paused":
            worker._pause_event.set()
            worker.status = "downloading"
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        worker = self._workers.get(task_id)
        if worker:
            worker._cancel_flag = True
            worker._pause_event.set()
            if worker._task and not worker._task.done():
                worker._task.cancel()
            worker.status = "cancelled"
            return True
        return False


model_downloader = ModelDownloader()
