"""Planning and execution resolve the same parameters, inputs and cache identity."""

import asyncio
from dataclasses import dataclass
import inspect
import os
from pathlib import Path
from typing import Any

from app.core.cache import cache_store, compute_semantic_node_hash
from app.core.content_identity import hash_file, port_content_identity
from app.core.execution_contract import validate_output_contract
from app.nodes.registry import registry
from app.schemas.workflow import WorkflowGraph, WorkflowNodeInstance
from app.storage.model_store import model_store


@dataclass
class ResolvedWorkflowNode:
    params: dict[str, Any]
    inputs: dict[str, Any]
    node_hash: str | None
    cached_output: dict[str, Any] | None
    cache_reason: str | None = None


async def local_model_identity(name: str) -> str:
    records = await asyncio.to_thread(model_store.list_models)
    matches = [record for record in records if Path(record.file_path).name == name or record.file_path == name]
    if len(matches) != 1:
        return f"unverified:{name}"
    return await asyncio.to_thread(hash_file, Path(matches[0].file_path))


async def resolve_workflow_node(node: WorkflowNodeInstance, graph: WorkflowGraph,
                                outputs: dict[str, dict[str, Any]], runner: Any) -> ResolvedWorkflowNode:
    definition = registry.get(node.type)
    params = {param.name: param.default for param in definition.parameters}
    params.update(node.params)
    identity: dict[str, Any] = {}
    if node.type == "text.llm":
        model = params["model"]
        endpoint = params.get("base_url") or os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
        if not params.get("base_url") and model.startswith(("gpt-", "o1")):
            endpoint = os.environ.get("OPENAI_API_BASE", "https://api.openai.com")
            params["api_key"] = params.get("api_key") or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        params["base_url"] = endpoint.rstrip("/")
        identity = {"endpoint": params["base_url"], "model": model, "revision": params.get("model_revision")}
    elif node.type == "image.generate":
        model = params["model"]
        endpoint = "https://api.openai.com" if model == "dall-e-3" else "https://api.siliconflow.cn" if model == "sdxl-turbo" else "https://fal.run"
        identity = {"endpoint": endpoint, "model": model, "revision": params.get("model_revision")}
    elif node.type == "image.comfy.txt2img":
        from app.runners.comfy_runner import comfy_client
        identity = {"endpoint": comfy_client.base_url, "model": params["checkpoint"],
                    "model_content": await local_model_identity(params["checkpoint"]),
                    "runtime_revision": params.get("runtime_revision")}
    try:
        source = inspect.getsourcefile(runner)
    except TypeError:
        source = None
    runner_version = await asyncio.to_thread(hash_file, Path(source)) if source else "workflow-contract-v2"
    bindings: list[tuple[str, str, str]] = []
    inputs = {port.id: port.default_value for port in definition.inputs if port.default_value is not None}
    for edge in graph.edges:
        if edge.target != node.id:
            continue
        output = outputs.get(edge.source, {})
        if edge.source_handle not in output:
            return ResolvedWorkflowNode(params, inputs, None, None, "Upstream output is not yet known")
        value = output[edge.source_handle]
        source_node = next(item for item in graph.nodes if item.id == edge.source)
        source_definition = registry.get(source_node.type)
        port = next(port for port in source_definition.outputs if port.id == edge.source_handle)
        inputs[edge.target_handle] = value
        bindings.append((edge.target_handle, await port_content_identity(value, port.type), edge.source_handle))
    node_hash = compute_semantic_node_hash(node.type, {**params, "__execution_identity": identity}, bindings,
                                           runner_version=runner_version)
    cached = await cache_store.get_async(node_hash)
    if cached is not None:
        try:
            validate_output_contract(node.type, cached)
        except ValueError:
            await cache_store.invalidate_async(node_hash)
            cached = None
    return ResolvedWorkflowNode(params, inputs, node_hash, cached)
