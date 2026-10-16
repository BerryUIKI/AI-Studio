"""User cancellation terminates only owned code; remote completion is not invented."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from app.core.custom_provider_service import AdapterCancelled, CustomProviderService
from app.runners.creative_runner import CreativeRunner
from app.runtime.credentials import CredentialManager
from app.runtime.worker_ownership import OwnedWorkerTree
from app.schemas.creative import CreativeActionRequest
from app.schemas.custom_provider import CustomProviderSpec
from app.storage.db import DatabaseManager
from app.storage.task_store import TaskStore


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["rest", "javascript", "python"])
async def test_cancelled_adapter_stops_owned_worker_and_records_uncertain_remote_outcome(
    tmp_path: Path, mode: str
) -> None:
    from app.core.creative_tasks import CreativeTaskService

    credentials = CredentialManager(tmp_path)
    source = (
        "async function execute(input,ctx){await ctx.job_id('fixture-job');await ctx.request({});return {type:'image',value:'unused'}}"
        if mode == "javascript"
        else "async def execute(input,ctx):\n    await ctx.job_id('fixture-job')\n    await ctx.request({})\n    return {'type':'image','value':'unused'}"
    )
    spec = CustomProviderSpec(
        id="custom-cancel",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["fixture"],
        actions=["txt2img"],
        auth="none",
        mode=mode,
        source=source,
    )
    service = CustomProviderService(credentials)
    service.registry.save(spec, approve_execution=True)
    entered = asyncio.Event()
    owners = []
    manager = DatabaseManager(tmp_path / "tasks.db")
    tasks = TaskStore(manager)
    scheduler = CreativeTaskService(tasks)

    async def blocked(broker, operation):
        broker.dispatched = True
        entered.set()
        await asyncio.Event().wait()

    def owner(process):
        value = OwnedWorkerTree(process)
        owners.append(value)
        return value

    with (
        patch("app.runners.creative_runner.credentials_manager", credentials),
        patch("app.runners.creative_runner.task_store", tasks),
        patch("app.core.provider_broker.ProviderBroker.request", blocked),
        patch("app.runners.adapter_executor.OwnedWorkerTree", side_effect=owner),
    ):
        try:
            task_id = await scheduler.submit(
                CreativeActionRequest(
                    action="txt2img", model="fixture", connection_id=spec.id, seed=42
                ),
                CreativeRunner().execute,
            )
            worker = scheduler._workers[task_id]
            await asyncio.wait_for(entered.wait(), 10)
            assert await scheduler.cancel(task_id)
            await asyncio.wait_for(worker, 10)
            record = await tasks.get_task(task_id)
            assert record.status == "outcome-unknown"
            assert (
                record.metadata["adapter_cancelled"]
                and record.metadata["remote_outcome_unknown"]
            )
            assert "No automatic retry" in record.error
            if mode != "rest":
                assert record.metadata["provider_job_id"] == "fixture-job"
                assert owners and all(
                    item.process.returncode is not None for item in owners
                )
        finally:
            await scheduler.shutdown()


@pytest.mark.asyncio
async def test_pre_cancelled_execution_never_dispatches(tmp_path: Path) -> None:
    service = CustomProviderService(CredentialManager(tmp_path))
    spec = CustomProviderSpec(
        id="custom-before-cancel",
        name="Fixture",
        endpoint="https://fixture.invalid",
        models=["fixture"],
        actions=["txt2img"],
        auth="none",
    )
    service.registry.save(spec)
    cancel = asyncio.Event()
    cancel.set()
    with patch(
        "app.core.provider_broker.ProviderBroker.request",
        side_effect=AssertionError("Unexpected dispatch"),
    ):
        with pytest.raises(AdapterCancelled) as error:
            await service.execute(spec.id, {"model": "fixture"}, cancel_event=cancel)
    assert not error.value.outcome_unknown
