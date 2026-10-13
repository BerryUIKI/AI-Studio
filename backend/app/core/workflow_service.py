"""Typed workflow orchestration shared by planning and durable execution."""

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
import json
import logging
import time
from typing import Any, Dict, List

from starlette.websockets import WebSocketDisconnect
from app.core.cache import CacheStore
from app.core.dag import CyclicDependencyError, DAGResolver
from app.core.execution_contract import ExecutionContractError, validate_execution_contract, validate_output_contract
from app.core.task_registry import TaskLifecycleRegistry
from app.core.workflow_runs import WorkflowEventSink
from app.core.workflow_spec import resolve_workflow_node
from app.nodes.registry import registry
from app.schemas.events import GraphFinishedEvent, GraphStartedEvent, NodeErrorEvent, NodeOutputEvent, NodeStatusEvent, RunCancelledEvent, WorkflowEvent
from app.schemas.task import WorkflowRunRequest
from app.schemas.workflow import ExecutionPlan, PlannedNodeStep, WorkflowGraph

logger = logging.getLogger(__name__)
# JSON port values are intentionally heterogeneous; runner parameters are validated by node schemas.
NodeRunner = Callable[[str, dict[str, Any], dict[str, Any]], AsyncIterator[WorkflowEvent]]
InputRunner = Callable[[str, dict[str, Any]], AsyncIterator[WorkflowEvent]]

class WorkflowPlanError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code

@dataclass(frozen=True)
class WorkflowExecutionService:
    runners: Mapping[str, NodeRunner]
    cache: CacheStore
    tasks: TaskLifecycleRegistry
    cancellations: dict[str, asyncio.Event]
    input_runner: InputRunner

    async def plan(self, graph: WorkflowGraph, target_node: str | None = None) -> ExecutionPlan:
        """Analyze workflow graph, validate DAG cycles, and compute dirty-check cache hashes."""
        try:
            resolver = DAGResolver(graph)
            sorted_nodes = resolver.topological_sort(target_node_id=target_node)
            validate_execution_contract(graph, sorted_nodes, self.runners)
        except CyclicDependencyError as err:
            raise WorkflowPlanError(status_code=400, detail=str(err))
        except ExecutionContractError as err:
            raise WorkflowPlanError(status_code=400, detail=str(err))
        except ValueError as err:
            raise WorkflowPlanError(status_code=404, detail=str(err))

        steps: List[PlannedNodeStep] = []
        known_outputs: dict[str, dict[str, Any]] = {}
        cached_count = 0

        for node in sorted_nodes:
            parents = resolver.get_parent_ids(node.id)
            try:
                spec = await resolve_workflow_node(node, graph, known_outputs, self.runners[node.type])
            except (ValueError, OSError) as error:
                raise WorkflowPlanError(status_code=400, detail=str(error)) from error
            is_cached = spec.cached_output is not None
            if is_cached:
                cached_count += 1
                known_outputs[node.id] = spec.cached_output
            elif node.type == "input.text":
                # Pure text inputs are known without invoking an inference runner.
                known_outputs[node.id] = {"text": spec.params["value"]}

            steps.append(
                PlannedNodeStep(
                    node_id=node.id,
                    node_type=node.type,
                    node_hash=spec.node_hash or "",
                    is_cached=is_cached,
                    dependencies=parents,
                    cache_reason=spec.cache_reason,
                )
            )

        return ExecutionPlan(
            steps=steps,
            total_nodes=len(steps),
            cached_nodes_count=cached_count,
        )


    async def execute(self, request: WorkflowRunRequest, websocket: WorkflowEventSink) -> None:
        """Execute into a durable event sink without owning any client connection."""
        graph = request.graph
        target_node = request.target_node_id
        run_id = request.run_id
        # Register cancellation token
        cancel_event = websocket.cancel_event
        self.cancellations[run_id] = cancel_event
        self.tasks.register_task(
            task_id=run_id,
            task_type="workflow_graph",
            cancel_event=cancel_event,
            metadata={"target_node": target_node},
        )

        try:
            resolver = DAGResolver(graph)
            sorted_nodes = resolver.topological_sort(target_node_id=target_node)
            validate_execution_contract(graph, sorted_nodes, self.runners)
        except ExecutionContractError as e:
            await websocket.send_text(NodeErrorEvent(node_id=e.node_id, message=str(e), run_id=run_id).model_dump_json())
            for node in graph.nodes:
                await websocket.send_text(NodeStatusEvent(node_id=node.id, status="error" if node.id == e.node_id else "cancelled", run_id=run_id).model_dump_json())
            await websocket.send_text(GraphFinishedEvent(run_id=run_id, execution_time_ms=0, status="failed").model_dump_json())
            await websocket.close()
            self.cancellations.pop(run_id, None)
            self.tasks.unregister_task(run_id)
            return
        except CyclicDependencyError as e:
            await websocket.send_text(json.dumps({"type": "ERROR", "message": str(e), "run_id": run_id}))
            await websocket.close()
            self.cancellations.pop(run_id, None)
            self.tasks.unregister_task(run_id)
            return
        except ValueError as e:
            await websocket.send_text(json.dumps({"type": "ERROR", "message": str(e), "run_id": run_id}))
            await websocket.close()
            self.cancellations.pop(run_id, None)
            self.tasks.unregister_task(run_id)
            return

        # Check cache status for active nodes
        cached_count = 0
        node_outputs: Dict[str, Dict[str, Any]] = {}

        start_time = time.monotonic()
        failed_node_ids: set[str] = set()

        try:
            await websocket.send_text(
                GraphStartedEvent(run_id=run_id, total_nodes=len(sorted_nodes), cached_nodes=cached_count).model_dump_json()
            )

            for node in sorted_nodes:
                # Check cancellation
                if cancel_event.is_set():
                    await websocket.send_text(RunCancelledEvent(run_id=run_id).model_dump_json())
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    await websocket.send_text(
                        GraphFinishedEvent(run_id=run_id, execution_time_ms=elapsed_ms, status="cancelled").model_dump_json()
                    )
                    break

                # Check if any upstream ancestor failed
                ancestors = resolver._get_ancestors(node.id)
                if any(anc in failed_node_ids for anc in ancestors):
                    # Abort this node due to upstream failure
                    await websocket.send_text(
                        NodeStatusEvent(node_id=node.id, status="cancelled", run_id=run_id).model_dump_json()
                    )
                    continue

                spec = await resolve_workflow_node(node, graph, node_outputs, self.runners[node.type])
                inputs = spec.inputs
                await websocket.bind_inputs(node.id, inputs, spec.params)
                node_hash = spec.node_hash
                if node_hash is None:
                    raise ValueError(spec.cache_reason)
                # Check cache (memory or SQLite)
                cached_output = spec.cached_output
                if cached_output is not None:
                    await websocket.send_text(NodeStatusEvent(node_id=node.id, status="cached", run_id=run_id).model_dump_json())
                    await websocket.send_text(
                        NodeOutputEvent(node_id=node.id, output=cached_output, run_id=run_id).model_dump_json()
                    )
                    node_outputs[node.id] = cached_output
                    continue

                # Dispatch to runner
                runner = self.runners.get(node.type)
                if runner is None:
                    failed_node_ids.add(node.id)
                    err_msg = f"No runner for node type: {node.type}"
                    await websocket.send_text(NodeErrorEvent(node_id=node.id, message=err_msg, run_id=run_id).model_dump_json())
                    await websocket.send_text(NodeStatusEvent(node_id=node.id, status="error", run_id=run_id).model_dump_json())
                    continue

                output: Dict[str, Any] = {}
                node_has_error = False

                try:
                    if node.type == "input.text":
                        async for event in self.input_runner(node.id, spec.params):
                            if cancel_event.is_set():
                                break
                            if isinstance(event, NodeOutputEvent):
                                validate_output_contract(node.type, event.output)
                            event.run_id = run_id
                            await websocket.send_text(event.model_dump_json())
                            if isinstance(event, NodeOutputEvent):
                                output = event.output
                    else:
                        async for event in runner(node.id, inputs, spec.params):
                            if cancel_event.is_set():
                                break
                            if isinstance(event, NodeOutputEvent):
                                validate_output_contract(node.type, event.output)
                            event.run_id = run_id
                            await websocket.send_text(event.model_dump_json())
                            if isinstance(event, NodeErrorEvent):
                                node_has_error = True
                            elif isinstance(event, NodeOutputEvent):
                                output = event.output
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected during execution of node %s (run_id: %s)", node.id, run_id)
                    cancel_event.set()
                    break
                except Exception as e:
                    node_has_error = True
                    try:
                        await websocket.send_text(NodeErrorEvent(node_id=node.id, message=str(e), run_id=run_id).model_dump_json())
                        await websocket.send_text(NodeStatusEvent(node_id=node.id, status="error", run_id=run_id).model_dump_json())
                    except (WebSocketDisconnect, RuntimeError):
                        cancel_event.set()
                        break

                if cancel_event.is_set():
                    await websocket.send_text(RunCancelledEvent(run_id=run_id).model_dump_json())
                    await websocket.send_text(GraphFinishedEvent(run_id=run_id, execution_time_ms=(time.monotonic() - start_time) * 1000, status="cancelled").model_dump_json())
                    break

                definition = registry.get(node.type)
                if not node_has_error and definition and any(port.id not in output for port in definition.outputs):
                    node_has_error = True
                    await websocket.send_text(NodeErrorEvent(node_id=node.id, message="Runner did not return its declared outputs", run_id=run_id).model_dump_json())

                if node_has_error:
                    failed_node_ids.add(node.id)
                    # Notify cancellation for all unexecuted descendants
                    descendants = resolver.get_descendants(node.id)
                    for desc_id in descendants:
                        await websocket.send_text(
                            NodeStatusEvent(node_id=desc_id, status="cancelled", run_id=run_id).model_dump_json()
                        )
                    # Conclude run as failed
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    await websocket.send_text(
                        GraphFinishedEvent(run_id=run_id, execution_time_ms=elapsed_ms, status="failed").model_dump_json()
                    )
                    break

                # Cache successful output
                if output:
                    if spec.cacheable:
                        await self.cache.set_async(node_hash, output)
                    node_outputs[node.id] = output

            else:
                # Loop completed without break
                elapsed_ms = (time.monotonic() - start_time) * 1000
                await websocket.send_text(
                    GraphFinishedEvent(run_id=run_id, execution_time_ms=elapsed_ms, status="failed" if failed_node_ids else "completed").model_dump_json()
                )

        except WebSocketDisconnect:
            logger.info("Client cleanly disconnected from workflow run %s", run_id)
            cancel_event.set()
        finally:
            self.cancellations.pop(run_id, None)
            self.tasks.unregister_task(run_id)
            try:
                await websocket.close()
            except Exception:
                pass
