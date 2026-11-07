"""Disposable review probes; no real provider calls or engine installation."""
import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[3] / ".review-runtime"
os.environ['BERRY_DATA_DIR'] = str(ROOT / 'probe-data')
os.environ['AI_WORKFLOW_ENGINE_DIR'] = str(ROOT / 'probe-engines')
sys.path.insert(0, str(ROOT.parent / 'backend'))

from app.runtime.credentials import CredentialManager
from app.runtime.supervisor import ComfySupervisor
from app.runtime.webui_supervisor import WebUISupervisor
from app.storage.model_store import ModelStore
from app.schemas.cloud import CloudProviderId, LLMConfig
from app.schemas.creative import CreativeActionRequest
from app.schemas.engine import EngineType
from app.storage.asset_store import asset_store
from app.storage.db import db_manager
from app.core.cache import CacheStore
from app.runners.creative_runner import CreativeRunner, resolve_effective_provider
from app.runtime.installer import IsolatedEngineInstaller
from app.runners.webui_runner import WebUIRunner
from app.runtime.model_downloader import DownloadWorker
from app.schemas.model_hub import HubModelRecord, ModelSource
from fastapi.testclient import TestClient
import app.main as main
import httpx

results = {}

async def run():
    creds = CredentialManager(ROOT / 'dummy-credentials')
    dummy = 'review-dummy-key-not-a-real-secret'
    creds.set_key(CloudProviderId.FAL, dummy)
    results['credential_saved_as_plaintext'] = dummy in creds.creds_file.read_text()
    with patch.object(main.credentials_manager, 'get_llm_config', return_value=LLMConfig(api_key=dummy)):
        with TestClient(main.app) as client:
            resp = client.get('/api/v1/agent/llm/config')
            results['unauthenticated_llm_config_returns_raw_key'] = resp.json().get('api_key') == dummy
            resp = client.post('/api/v1/runtime/start', headers={'Origin': 'https://untrusted.example'})
            results['cross_origin_simple_post_reaches_sensitive_handler'] = resp.status_code == 200 and resp.json().get('code') == 'NOT_INSTALLED'
            with client.websocket_connect('/ws/workflow/run', headers={'Origin': 'https://untrusted.example'}) as ws:
                ws.send_json({'run_id': 'review-unknown-node', 'graph': {'nodes': [{'id': 'missing', 'type': 'review.unknown', 'params': {}}], 'edges': []}})
                events = []
                while True:
                    event = ws.receive_json()
                    events.append(event)
                    if event.get('type') == 'GRAPH_FINISHED':
                        break
                results['unknown_runner_final_status'] = events[-1].get('status')
                results['cross_origin_websocket_accepted'] = events[0].get('type') == 'GRAPH_STARTED'

    results['comfy_accepts_unrelated_python_pid'] = ComfySupervisor(ROOT / 'pid-fixture')._verify_process_identity(os.getpid())
    results['webui_accepts_unrelated_python_pid'] = WebUISupervisor(ROOT / 'pid-fixture')._verify_process_identity(os.getpid())

    fixture = ROOT / 'unknown-models'
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / 'unknown.gguf').write_bytes(b'not-a-real-model')
    ms = ModelStore(ROOT / 'model-fixture')
    ms.add_root('user-root', str(fixture), 'Review fixture')
    record = ms.scan_all_roots()[0]
    results['unknown_invalid_model_ready'] = {'ready': record.is_ready, 'architecture': record.architecture.value, 'compatibility': record.engine_compatibility}
    results['custom_model_root_lost_after_reconstruction'] = 'user-root' not in ModelStore(ROOT / 'model-fixture').roots

    # The installer skips repository download for any existing destination,
    # and skips dependency setup when requirements/pip do not exist.
    broken_dir = ROOT / 'incomplete-engine'
    (broken_dir / 'comfyui').mkdir(parents=True, exist_ok=True)
    installer = IsolatedEngineInstaller(broken_dir)
    with patch.object(installer, 'create_isolated_venv', new=AsyncMock(return_value=True)):
        manifest = await installer.install_engine(EngineType.COMFYUI)
    results['incomplete_engine_reported_completed'] = {'phase': manifest.phase.value, 'entrypoint_exists': (broken_dir / 'comfyui' / 'main.py').exists()}

    cache = CacheStore(db_manager)
    await cache.clear_all_async()
    runner = CreativeRunner()
    asset = await asset_store.save_bytes(b'review-image-fixture', 'fixture.png')
    fake_action = {'asset_id': asset.id, 'image_url': f'/api/v1/assets/{asset.id}/content', 'width': 512, 'height': 512}
    with patch('app.runners.creative_runner.cache_store', cache), patch.object(runner, '_run_comfy', new=AsyncMock(return_value=fake_action)) as execute:
        await runner.execute(CreativeActionRequest(action='txt2img', seed=42))
        asset_store.get_absolute_path(asset).unlink()
        result = await runner.execute(CreativeActionRequest(action='txt2img', seed=42))
        results['missing_asset_cache_hit_returns_success'] = {'success': result.success, 'cached': result.is_cached, 'actual_calls': execute.await_count, 'file_exists': asset_store.get_absolute_path(asset).exists()}

    conn = await db_manager.get_connection()
    for table in ['runs', 'tasks']:
        cursor = await conn.execute(f'SELECT COUNT(*) FROM {table}')
        results[f'creative_execution_persisted_{table}'] = (await cursor.fetchone())[0]

    captured = {}
    def transport(req):
        captured.update(json.loads(req.content))
        return httpx.Response(200, json={'images': ['cmV2aWV3']})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        await WebUIRunner()._run_txt2img(client, CreativeActionRequest(action='txt2img', model='chosen-checkpoint.safetensors', seed=42))
    results['webui_payload_honors_selected_model'] = 'override_settings' in captured or 'sd_model_checkpoint' in captured

    # Resolve identity and dispatch independently with fake keys/provider calls.
    cloud_req = CreativeActionRequest(action='txt2img', engine_id='fal_ai', model='sdxl-turbo', seed=42)
    dispatch = []
    async def fake_sf(*args, **kwargs):
        dispatch.append('siliconflow')
        return 'https://fixture.example/output.png'
    async def fake_fal(*args, **kwargs):
        dispatch.append('fal_ai')
        return 'https://fixture.example/output.png'
    with patch('app.runners.creative_runner.credentials_manager.get_key', return_value=dummy), patch('app.runners.creative_runner._call_siliconflow', new=fake_sf), patch('app.runners.creative_runner._call_fal_ai', new=fake_fal), patch.object(asset_store, 'save_image_from_url', new=AsyncMock(return_value=asset)):
        resolved = resolve_effective_provider(cloud_req)
        await runner._run_cloud(cloud_req)
    results['cloud_provider_resolution_dispatch_mismatch'] = {'hash_provider': resolved, 'actual_provider': dispatch}

    active_checks = []
    async def fake_update(engine_type, has_active_tasks_fn):
        active_checks.append(has_active_tasks_fn())
        return None
    main.creative_runner.active_tasks['review-active-task'] = {'engine': 'managed_comfyui'}
    try:
        with patch.object(main.installer, 'update_engine', new=fake_update):
            await main.trigger_engine_update(EngineType.COMFYUI)
    finally:
        main.creative_runner.active_tasks.pop('review-active-task', None)
    results['engine_update_detects_running_creative_task'] = active_checks

    # Corrupt download is marked complete despite explicit checksum/size metadata.
    download_model = HubModelRecord(id='review-model', name='Fixture', architecture='unknown', category='checkpoint', version='review', size_bytes=100, parameter_count='0', author='Review', description='Fixture', preview_image_url='', min_vram_mb=0, optimal_vram_mb=0, sha256='0' * 64, sources=[ModelSource(name='Fixture', url='https://fixture.example/model')])
    worker = DownloadWorker('review-download', download_model, 'comfyui', ROOT / 'download-fixture' / 'model.safetensors', 'https://fixture.example/model')
    real_client = httpx.AsyncClient
    def fake_client(**kwargs):
        return real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'corrupt-model')))
    with patch('app.runtime.model_downloader.httpx.AsyncClient', side_effect=fake_client):
        await worker.run()
    results['bad_checksum_model_download_completed'] = {'status': worker.status, 'actual_size': worker.target_path.stat().st_size, 'expected_size': 100}
    # Read-only status polling must not invalidate an active installation.
    from app.schemas.engine import InstallPhase
    from app.runtime.llama_server.llama_supervisor import LlamaServerSupervisor
    polling_installer = IsolatedEngineInstaller(ROOT / 'polling-fixture')
    polling_manifest = polling_installer.read_manifest(EngineType.COMFYUI)
    polling_manifest.phase = InstallPhase.DOWNLOADING
    polling_installer.write_manifest(polling_manifest)
    results['active_install_status_read_changes_phase'] = polling_installer.read_manifest(EngineType.COMFYUI).phase.value
    # Never terminate a real process: both ownership lookup and taskkill are mocked.
    llama = LlamaServerSupervisor()
    with patch.object(llama, 'get_pid', return_value=12345), patch('app.runtime.llama_server.llama_supervisor.subprocess.run'), patch.object(llama, '_clean_pid_file'):
        results['successful_llama_stop_result'] = llama.stop()
    await db_manager.close()

asyncio.run(run())
print(json.dumps(results, indent=2))
(ROOT / 'probe-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')

