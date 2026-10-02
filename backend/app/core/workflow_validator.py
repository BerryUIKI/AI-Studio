"""ComfyUI workflow DAG validator (M10).

Parses ComfyUI prompt graphs, verifies topological integrity, checks required
port connections, detects cycles, and cross-checks model references.
"""

from typing import Any, Dict, List, Optional, Set
from app.schemas.workflow_analysis import (
    WorkflowIssue,
    WorkflowIssueSeverity,
    WorkflowValidationReport,
)

# Standard ComfyUI node port specifications: class_type -> required inputs with expected types
STANDARD_NODE_REQUIREMENTS: Dict[str, Dict[str, str]] = {
    "KSampler": {
        "model": "MODEL",
        "positive": "CONDITIONING",
        "negative": "CONDITIONING",
        "latent_image": "LATENT",
    },
    "KSamplerAdvanced": {
        "model": "MODEL",
        "positive": "CONDITIONING",
        "negative": "CONDITIONING",
        "latent_image": "LATENT",
    },
    "VAEDecode": {
        "samples": "LATENT",
        "vae": "VAE",
    },
    "VAEEncode": {
        "pixels": "IMAGE",
        "vae": "VAE",
    },
    "CLIPTextEncode": {
        "clip": "CLIP",
    },
    "SaveImage": {
        "images": "IMAGE",
    },
    "ImageUpscaleWithModel": {
        "upscale_model": "UPSCALE_MODEL",
        "image": "IMAGE",
    },
}

# Standard output slot types: class_type -> slot_index -> port_type
STANDARD_NODE_OUTPUTS: Dict[str, Dict[int, str]] = {
    "CheckpointLoaderSimple": {0: "MODEL", 1: "CLIP", 2: "VAE"},
    "LoadCheckpoint": {0: "MODEL", 1: "CLIP", 2: "VAE"},
    "VAELoader": {0: "VAE"},
    "EmptyLatentImage": {0: "LATENT"},
    "CLIPTextEncode": {0: "CONDITIONING"},
    "KSampler": {0: "LATENT"},
    "KSamplerAdvanced": {0: "LATENT"},
    "VAEDecode": {0: "IMAGE"},
    "VAEEncode": {0: "LATENT"},
    "UpscaleModelLoader": {0: "UPSCALE_MODEL"},
    "ImageUpscaleWithModel": {0: "IMAGE"},
}


class WorkflowValidator:
    def __init__(self, model_catalog=None):
        self.model_catalog = model_catalog

    def validate(self, workflow: Dict[str, Any]) -> WorkflowValidationReport:
        """Validate a ComfyUI prompt dictionary."""
        issues: List[WorkflowIssue] = []
        missing_models: List[str] = []

        if not isinstance(workflow, dict) or not workflow:
            issues.append(
                WorkflowIssue(
                    node_id="root",
                    node_class="workflow",
                    issue_type="empty_workflow",
                    message="Workflow graph is empty or not a valid dictionary.",
                    severity=WorkflowIssueSeverity.ERROR,
                )
            )
            return WorkflowValidationReport(
                valid=False,
                node_count=0,
                issues=issues,
                missing_models=[],
                has_cycle=False,
            )

        # 1. Check for topological cycles
        has_cycle, cycle_nodes = self._detect_cycles(workflow)
        if has_cycle:
            for nid in cycle_nodes:
                cls_name = workflow.get(nid, {}).get("class_type", "Unknown")
                issues.append(
                    WorkflowIssue(
                        node_id=nid,
                        node_class=cls_name,
                        issue_type="cycle_detected",
                        message=f"Node '{nid}' is part of a cyclic dependency loop.",
                        severity=WorkflowIssueSeverity.ERROR,
                    )
                )

        # 2. Per-node validation
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                issues.append(
                    WorkflowIssue(
                        node_id=str(node_id),
                        node_class="unknown",
                        issue_type="invalid_node_structure",
                        message=f"Node '{node_id}' data must be a dictionary.",
                        severity=WorkflowIssueSeverity.ERROR,
                    )
                )
                continue

            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})

            if not class_type:
                issues.append(
                    WorkflowIssue(
                        node_id=str(node_id),
                        node_class="",
                        issue_type="missing_class_type",
                        message=f"Node '{node_id}' is missing required 'class_type'.",
                        severity=WorkflowIssueSeverity.ERROR,
                    )
                )
                continue

            # Check model availability
            if class_type in ("CheckpointLoaderSimple", "LoadCheckpoint"):
                ckpt_name = inputs.get("ckpt_name", "")
                if not ckpt_name:
                    issues.append(
                        WorkflowIssue(
                            node_id=str(node_id),
                            node_class=class_type,
                            input_slot="ckpt_name",
                            issue_type="missing_parameter",
                            message=f"Checkpoint node '{node_id}' has no 'ckpt_name' specified.",
                            severity=WorkflowIssueSeverity.ERROR,
                        )
                    )
                elif self.model_catalog:
                    try:
                        indexed = [m.name for m in self.model_catalog.get_models()]
                        if indexed and ckpt_name not in indexed:
                            missing_models.append(ckpt_name)
                            issues.append(
                                WorkflowIssue(
                                    node_id=str(node_id),
                                    node_class=class_type,
                                    input_slot="ckpt_name",
                                    issue_type="missing_model",
                                    message=f"Checkpoint '{ckpt_name}' is not indexed in local model catalog.",
                                    severity=WorkflowIssueSeverity.WARNING,
                                )
                            )
                    except Exception:
                        pass

            # Check required slot connections
            req_slots = STANDARD_NODE_REQUIREMENTS.get(class_type, {})
            for slot_name, expected_type in req_slots.items():
                if slot_name not in inputs:
                    issues.append(
                        WorkflowIssue(
                            node_id=str(node_id),
                            node_class=class_type,
                            input_slot=slot_name,
                            issue_type="missing_connection",
                            message=f"Node '{node_id}' ({class_type}) is missing required input connection for '{slot_name}' ({expected_type}).",
                            severity=WorkflowIssueSeverity.ERROR,
                        )
                    )
                else:
                    val = inputs[slot_name]
                    # Link is represented as [target_node_id, slot_index]
                    if isinstance(val, (list, tuple)) and len(val) >= 2:
                        src_id, slot_idx = str(val[0]), val[1]
                        if src_id not in workflow:
                            issues.append(
                                WorkflowIssue(
                                    node_id=str(node_id),
                                    node_class=class_type,
                                    input_slot=slot_name,
                                    issue_type="broken_link",
                                    message=f"Node '{node_id}' connects to non-existent source node '{src_id}'.",
                                    severity=WorkflowIssueSeverity.ERROR,
                                )
                            )
                        else:
                            # Verify port type compatibility if known
                            src_class = workflow[src_id].get("class_type", "")
                            src_outputs = STANDARD_NODE_OUTPUTS.get(src_class, {})
                            if slot_idx in src_outputs:
                                actual_type = src_outputs[slot_idx]
                                if actual_type != expected_type:
                                    issues.append(
                                        WorkflowIssue(
                                            node_id=str(node_id),
                                            node_class=class_type,
                                            input_slot=slot_name,
                                            issue_type="type_mismatch",
                                            message=f"Type mismatch on '{node_id}.{slot_name}': expected {expected_type}, received {actual_type} from '{src_id}' [{slot_idx}].",
                                            severity=WorkflowIssueSeverity.ERROR,
                                        )
                                    )

        has_errors = any(i.severity == WorkflowIssueSeverity.ERROR for i in issues)
        valid = (not has_errors) and (not has_cycle)

        return WorkflowValidationReport(
            valid=valid,
            node_count=len(workflow),
            issues=issues,
            missing_models=list(set(missing_models)),
            has_cycle=has_cycle,
        )

    def _detect_cycles(self, workflow: Dict[str, Any]) -> tuple[bool, Set[str]]:
        """DFS cycle detection for directed graph."""
        adj: Dict[str, List[str]] = {str(k): [] for k in workflow.keys()}
        for nid, data in workflow.items():
            if not isinstance(data, dict):
                continue
            inputs = data.get("inputs", {})
            for val in inputs.values():
                if isinstance(val, (list, tuple)) and len(val) >= 2:
                    src_id = str(val[0])
                    if src_id in adj:
                        adj[src_id].append(str(nid))

        visited: Dict[str, int] = {k: 0 for k in adj}  # 0: unvisited, 1: visiting, 2: visited
        cycle_nodes: Set[str] = set()

        def dfs(node: str, stack: List[str]) -> bool:
            visited[node] = 1
            stack.append(node)
            for nxt in adj.get(node, []):
                if visited.get(nxt, 0) == 1:
                    # Cycle found
                    idx = stack.index(nxt) if nxt in stack else 0
                    for c_node in stack[idx:]:
                        cycle_nodes.add(c_node)
                    return True
                elif visited.get(nxt, 0) == 0:
                    if dfs(nxt, stack):
                        return True
            stack.pop()
            visited[node] = 2
            return False

        has_cycle = False
        for n in list(adj.keys()):
            if visited[n] == 0:
                if dfs(n, []):
                    has_cycle = True

        return has_cycle, cycle_nodes
