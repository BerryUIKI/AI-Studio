"""ComfyUI workflow repair engine (M10).

Applies deterministic heuristics to repair disconnected ports, missing model
references, and broken graph topology in ComfyUI prompt workflows.
"""

import copy
from typing import Any, Dict, List, Optional
from app.core.workflow_validator import (
    STANDARD_NODE_OUTPUTS,
    WorkflowValidator,
)
from app.schemas.workflow_analysis import (
    RepairAction,
    WorkflowIssueSeverity,
    WorkflowRepairResult,
)


class WorkflowRepairer:
    def __init__(self, model_catalog=None):
        self.model_catalog = model_catalog
        self.validator = WorkflowValidator(model_catalog=model_catalog)

    def _find_nodes_with_output(self, workflow: Dict[str, Any], port_type: str) -> List[tuple[str, int]]:
        """Finds all (node_id, slot_index) producing the given port_type."""
        matches = []
        for nid, data in workflow.items():
            if not isinstance(data, dict):
                continue
            cls_name = data.get("class_type", "")
            slots = STANDARD_NODE_OUTPUTS.get(cls_name, {})
            for s_idx, p_type in slots.items():
                if p_type == port_type:
                    matches.append((str(nid), s_idx))
        return matches

    def repair(self, workflow: Dict[str, Any]) -> WorkflowRepairResult:
        """Repair issues in a ComfyUI prompt workflow."""
        orig_report = self.validator.validate(workflow)
        if orig_report.valid:
            return WorkflowRepairResult(
                success=True,
                original_valid=True,
                repaired_valid=True,
                repairs_applied=[],
                repaired_workflow=workflow,
                remaining_issues=[],
            )

        repaired = copy.deepcopy(workflow)
        repairs: List[RepairAction] = []

        # 1. Substitute missing checkpoints if available in model catalog
        if self.model_catalog:
            try:
                indexed_models = self.model_catalog.get_models()
                if indexed_models:
                    default_ckpt = indexed_models[0].name
                    for nid, node_data in repaired.items():
                        if node_data.get("class_type") in ("CheckpointLoaderSimple", "LoadCheckpoint"):
                            cur_ckpt = node_data.get("inputs", {}).get("ckpt_name", "")
                            indexed_names = [m.name for m in indexed_models]
                            if (not cur_ckpt) or (cur_ckpt not in indexed_names):
                                node_data.setdefault("inputs", {})["ckpt_name"] = default_ckpt
                                repairs.append(
                                    RepairAction(
                                        node_id=str(nid),
                                        node_class=node_data["class_type"],
                                        action_type="replace_model",
                                        description=f"Substituted unavailable checkpoint '{cur_ckpt}' with indexed model '{default_ckpt}'.",
                                        target_input="ckpt_name",
                                        new_value=default_ckpt,
                                    )
                                )
            except Exception:
                pass

        # 2. Repair missing required connections
        vae_sources = self._find_nodes_with_output(repaired, "VAE")
        clip_sources = self._find_nodes_with_output(repaired, "CLIP")
        model_sources = self._find_nodes_with_output(repaired, "MODEL")
        latent_sources = self._find_nodes_with_output(repaired, "LATENT")
        cond_sources = self._find_nodes_with_output(repaired, "CONDITIONING")

        for nid, node_data in repaired.items():
            if not isinstance(node_data, dict):
                continue
            cls_name = node_data.get("class_type", "")
            inputs = node_data.setdefault("inputs", {})

            # Repair VAEDecode / VAEEncode missing VAE
            if cls_name in ("VAEDecode", "VAEEncode"):
                if "vae" not in inputs or not inputs["vae"]:
                    if vae_sources:
                        src_id, slot_idx = vae_sources[0]
                        inputs["vae"] = [src_id, slot_idx]
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="reconnect_slot",
                                description=f"Connected missing 'vae' input to node '{src_id}' [slot {slot_idx}].",
                                target_input="vae",
                                source_node_id=src_id,
                                source_output_slot=slot_idx,
                            )
                        )

            # Repair CLIPTextEncode missing CLIP
            if cls_name == "CLIPTextEncode":
                if "clip" not in inputs or not inputs["clip"]:
                    if clip_sources:
                        src_id, slot_idx = clip_sources[0]
                        inputs["clip"] = [src_id, slot_idx]
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="reconnect_slot",
                                description=f"Connected missing 'clip' input to node '{src_id}' [slot {slot_idx}].",
                                target_input="clip",
                                source_node_id=src_id,
                                source_output_slot=slot_idx,
                            )
                        )

            # Repair KSampler missing MODEL
            if cls_name in ("KSampler", "KSamplerAdvanced"):
                if "model" not in inputs or not inputs["model"]:
                    if model_sources:
                        src_id, slot_idx = model_sources[0]
                        inputs["model"] = [src_id, slot_idx]
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="reconnect_slot",
                                description=f"Connected missing 'model' input to node '{src_id}' [slot {slot_idx}].",
                                target_input="model",
                                source_node_id=src_id,
                                source_output_slot=slot_idx,
                            )
                        )

                # Repair KSampler missing latent_image
                if "latent_image" not in inputs or not inputs["latent_image"]:
                    # Look for EmptyLatentImage first, or any latent source
                    empty_latents = [
                        (s_id, s_slot)
                        for s_id, s_slot in latent_sources
                        if repaired.get(s_id, {}).get("class_type") == "EmptyLatentImage"
                    ]
                    target = empty_latents[0] if empty_latents else (latent_sources[0] if latent_sources else None)
                    if target:
                        src_id, slot_idx = target
                        inputs["latent_image"] = [src_id, slot_idx]
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="reconnect_slot",
                                description=f"Connected missing 'latent_image' input to node '{src_id}' [slot {slot_idx}].",
                                target_input="latent_image",
                                source_node_id=src_id,
                                source_output_slot=slot_idx,
                            )
                        )

                # Repair KSampler missing positive / negative conditioning
                if ("positive" not in inputs or not inputs["positive"]) and len(cond_sources) >= 1:
                    src_id, slot_idx = cond_sources[0]
                    inputs["positive"] = [src_id, slot_idx]
                    repairs.append(
                        RepairAction(
                            node_id=str(nid),
                            node_class=cls_name,
                            action_type="reconnect_slot",
                            description=f"Connected missing 'positive' conditioning to node '{src_id}'.",
                            target_input="positive",
                            source_node_id=src_id,
                            source_output_slot=slot_idx,
                        )
                    )

                if ("negative" not in inputs or not inputs["negative"]) and len(cond_sources) >= 2:
                    src_id, slot_idx = cond_sources[1]
                    inputs["negative"] = [src_id, slot_idx]
                    repairs.append(
                        RepairAction(
                            node_id=str(nid),
                            node_class=cls_name,
                            action_type="reconnect_slot",
                            description=f"Connected missing 'negative' conditioning to node '{src_id}'.",
                            target_input="negative",
                            source_node_id=src_id,
                            source_output_slot=slot_idx,
                        )
                    )

        # 3. Final validation of repaired workflow
        final_report = self.validator.validate(repaired)
        remaining_errors = [i for i in final_report.issues if i.severity == WorkflowIssueSeverity.ERROR]

        return WorkflowRepairResult(
            success=len(remaining_errors) == 0 and not final_report.has_cycle,
            original_valid=orig_report.valid,
            repaired_valid=final_report.valid,
            repairs_applied=repairs,
            repaired_workflow=repaired,
            remaining_issues=final_report.issues,
        )
