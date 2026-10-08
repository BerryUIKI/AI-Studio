"""Validate execution contracts before any workflow inference is submitted."""

from collections.abc import Mapping, Sequence

from app.nodes.registry import registry
from app.schemas.workflow import WorkflowGraph, WorkflowNodeInstance


class ExecutionContractError(ValueError):
    """A node or binding cannot be executed under the registered contract."""

    def __init__(self, node_id: str, message: str) -> None:
        super().__init__(message)
        self.node_id = node_id


def validate_execution_contract(
    graph: WorkflowGraph,
    nodes: Sequence[WorkflowNodeInstance],
    runners: Mapping[str, object],
) -> None:
    """Validate active nodes and incoming bindings, including required inputs.

    The preview presentation sink intentionally accepts all five port types.
    Execution nodes otherwise require identical source and target types.
    """
    active_ids = {node.id for node in nodes}
    definitions = {}
    for node in nodes:
        definition = registry.get(node.type)
        if definition is None or not callable(runners.get(node.type)):
            raise ExecutionContractError(node.id, f"No runner contract for node type: {node.type}")
        definitions[node.id] = definition

    bound_inputs: set[tuple[str, str]] = set()
    for edge in graph.edges:
        if edge.target not in active_ids:
            continue
        source = definitions[edge.source]
        target = definitions[edge.target]
        output = next((port for port in source.outputs if port.id == edge.source_handle), None)
        input_port = next((port for port in target.inputs if port.id == edge.target_handle), None)
        if output is None or input_port is None:
            raise ExecutionContractError(edge.target, f"Edge '{edge.id}' references an unknown port")
        binding = (edge.target, edge.target_handle)
        if binding in bound_inputs:
            raise ExecutionContractError(edge.target, f"Multiple bindings for input '{edge.target_handle}'")
        bound_inputs.add(binding)
        if output.type != input_port.type and target.type != "output.preview":
            raise ExecutionContractError(edge.target, f"Port type mismatch on edge '{edge.id}'")

    for node in nodes:
        for port in definitions[node.id].inputs:
            if port.required and (node.id, port.id) not in bound_inputs and port.default_value is None:
                raise ExecutionContractError(node.id, f"Missing required input '{port.id}' for '{node.id}'")
