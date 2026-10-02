"""DAG graph analysis, cycle detection, and topological sorting."""

from collections import defaultdict, deque
from typing import Dict, List, Set
from app.schemas.workflow import WorkflowGraph, WorkflowNodeInstance


class CyclicDependencyError(Exception):
    """Raised when a circular wire loop is detected in the workflow graph."""
    pass


class DAGResolver:
    """Parses and validates a WorkflowGraph into an executable topological sequence."""

    def __init__(self, graph: WorkflowGraph) -> None:
        self.graph = graph
        self.node_map: Dict[str, WorkflowNodeInstance] = {n.id: n for n in graph.nodes}

        # Build adjacency list: parent -> children
        self.adjacency: Dict[str, List[str]] = defaultdict(list)
        # Reverse adjacency: child -> parents
        self.parents: Dict[str, List[str]] = defaultdict(list)
        # In-degree count for Kahn's algorithm
        self.in_degree: Dict[str, int] = {n.id: 0 for n in graph.nodes}

        for edge in graph.edges:
            if edge.source in self.node_map and edge.target in self.node_map:
                self.adjacency[edge.source].append(edge.target)
                self.parents[edge.target].append(edge.source)
                self.in_degree[edge.target] += 1

    def topological_sort(self, target_node_id: str | None = None) -> List[WorkflowNodeInstance]:
        """
        Sort nodes into a valid execution order using Kahn's algorithm.
        If target_node_id is provided, only sorts dependencies required for that node.
        """
        active_node_ids = set(self.node_map.keys())
        if target_node_id is not None:
            if target_node_id not in self.node_map:
                raise ValueError(f"Target node '{target_node_id}' does not exist in graph")
            active_node_ids = self._get_ancestors(target_node_id) | {target_node_id}

        # Compute in-degrees only among active nodes
        local_in_degree = {nid: 0 for nid in active_node_ids}
        for parent in active_node_ids:
            for child in self.adjacency[parent]:
                if child in active_node_ids:
                    local_in_degree[child] += 1

        queue = deque([nid for nid in active_node_ids if local_in_degree[nid] == 0])
        ordered_ids: List[str] = []

        while queue:
            curr = queue.popleft()
            ordered_ids.append(curr)

            for child in self.adjacency[curr]:
                if child in active_node_ids:
                    local_in_degree[child] -= 1
                    if local_in_degree[child] == 0:
                        queue.append(child)

        if len(ordered_ids) != len(active_node_ids):
            raise CyclicDependencyError("Circular dependency detected in workflow connections")

        return [self.node_map[nid] for nid in ordered_ids]

    def _get_ancestors(self, node_id: str) -> Set[str]:
        """Recursively gather all upstream ancestor nodes."""
        ancestors: Set[str] = set()
        queue = deque(self.parents[node_id])
        while queue:
            curr = queue.popleft()
            if curr not in ancestors:
                ancestors.add(curr)
                queue.extend(self.parents[curr])
        return ancestors

    def get_descendants(self, node_id: str) -> Set[str]:
        """Recursively gather all downstream descendant nodes."""
        descendants: Set[str] = set()
        queue = deque(self.adjacency[node_id])
        while queue:
            curr = queue.popleft()
            if curr not in descendants:
                descendants.add(curr)
                queue.extend(self.adjacency[curr])
        return descendants

    def get_parent_ids(self, node_id: str) -> List[str]:
        """Return direct upstream parent node IDs."""
        return self.parents.get(node_id, [])
