"""Node registry for managing and discovering available workflow nodes."""

from typing import Dict, List, Optional
from app.schemas.node import NodeDefinition, NodeCategory


class NodeRegistry:
    """In-memory registry of declarative node definitions."""

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeDefinition] = {}

    def register(self, node: NodeDefinition) -> None:
        """Register a node definition. Overwriting same type is permitted."""
        self._nodes[node.type] = node

    def get(self, node_type: str) -> Optional[NodeDefinition]:
        """Retrieve a node definition by its unique type."""
        return self._nodes.get(node_type)

    def list_all(self) -> List[NodeDefinition]:
        """List all registered node definitions."""
        return list(self._nodes.values())

    def list_by_category(self, category: NodeCategory) -> List[NodeDefinition]:
        """Filter node definitions by category."""
        return [n for n in self._nodes.values() if n.category == category]


# Global registry singleton
registry = NodeRegistry()
