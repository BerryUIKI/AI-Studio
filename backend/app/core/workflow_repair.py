"""ComfyUI workflow repair engine (M10).

Applies deterministic heuristics to repair disconnected ports, missing model
references, and broken graph topology in ComfyUI prompt workflows.
Strictly prevents automatic model or port substitutions when compatibility is uncertain.
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


def infer_model_family(name: str) -> str:
    """Infer model architecture family from filename."""
    lower = name.lower()
    if any(k in lower for k in ["xl", "sdxl", "base-1.0", "refiner"]):
        return "sdxl"
    if "flux" in lower:
        return "flux"
    if "svd" in lower:
        return "svd"
    if any(k in lower for k in ["v1-5", "sd15", "1.5", "v1.5", "stable-diffusion-v1"]):
        return "sd15"
    if "sd2" in lower or "v2-1" in lower:
        return "sd2"
    return "unknown"


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
        """Repair issues in a ComfyUI prompt workflow with strict compatibility guards."""
        orig_report = self.validator.validate(workflow)
        if orig_report.valid and not orig_report.missing_models:
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

        # 1. Substitute missing checkpoints ONLY when architecture compatibility is certain
        if self.model_catalog:
            try:
                indexed_models = self.model_catalog.get_models()
                indexed_names = [m.name for m in indexed_models]

                for nid, node_data in repaired.items():
                    if node_data.get("class_type") in ("CheckpointLoaderSimple", "LoadCheckpoint"):
                        cur_ckpt = node_data.get("inputs", {}).get("ckpt_name", "")

                        if not cur_ckpt:
                            # No model specified at all: pick first indexed model if available
                            if indexed_models:
                                fallback_ckpt = indexed_models[0].name
                                node_data.setdefault("inputs", {})["ckpt_name"] = fallback_ckpt
                                repairs.append(
                                    RepairAction(
                                        node_id=str(nid),
                                        node_class=node_data["class_type"],
                                        action_type="replace_model",
                                        description=f"Assigned available indexed model '{fallback_ckpt}' to empty checkpoint slot.",
                                        target_input="ckpt_name",
                                        new_value=fallback_ckpt,
                                    )
                                )
                        elif cur_ckpt not in indexed_names:
                            # A specific model was requested but is not in the catalog
                            cur_family = infer_model_family(cur_ckpt)
                            if cur_family == "unknown":
                                # Unknown architecture family: DO NOT guess or substitute!
                                repairs.append(
                                    RepairAction(
                                        node_id=str(nid),
                                        node_class=node_data["class_type"],
                                        action_type="substitution_blocked",
                                        description=(
                                            f"Model substitution blocked for '{cur_ckpt}': architecture family is unknown. "
                                            "Automatic replacement prevented to avoid graph corruption."
                                        ),
                                        target_input="ckpt_name",
                                    )
                                )
                            else:
                                # Find an indexed model of the exact same family
                                matching_candidates = [
                                    m.name for m in indexed_models if infer_model_family(m.name) == cur_family
                                ]
                                if matching_candidates:
                                    sub_model = matching_candidates[0]
                                    node_data.setdefault("inputs", {})["ckpt_name"] = sub_model
                                    repairs.append(
                                        RepairAction(
                                            node_id=str(nid),
                                            node_class=node_data["class_type"],
                                            action_type="replace_model",
                                            description=(
                                                f"Substituted unavailable {cur_family.upper()} checkpoint '{cur_ckpt}' "
                                                f"with compatible indexed model '{sub_model}'."
                                            ),
                                            target_input="ckpt_name",
                                            new_value=sub_model,
                                        )
                                    )
                                else:
                                    # No model in the matching family exists
                                    repairs.append(
                                        RepairAction(
                                            node_id=str(nid),
                                            node_class=node_data["class_type"],
                                            action_type="substitution_blocked",
                                            description=(
                                                f"Model substitution blocked for '{cur_ckpt}': no indexed model in the "
                                                f"matching '{cur_family.upper()}' family is available."
                                            ),
                                            target_input="ckpt_name",
                                        )
                                    )
            except Exception:
                pass

        # 2. Repair missing required connections with ambiguity guards
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
                    if len(vae_sources) == 1:
                        src_id, slot_idx = vae_sources[0]
                        inputs["vae"] = [src_id, slot_idx]
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="reconnect_slot",
                                description=f"Connected missing 'vae' input to unambiguous source node '{src_id}' [slot {slot_idx}].",
                                target_input="vae",
                                source_node_id=src_id,
                                source_output_slot=slot_idx,
                            )
                        )
                    elif len(vae_sources) > 1:
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="substitution_blocked",
                                description=f"Automatic VAE connection blocked: {len(vae_sources)} ambiguous VAE sources detected.",
                                target_input="vae",
                            )
                        )

            # Repair CLIPTextEncode missing CLIP
            if cls_name == "CLIPTextEncode":
                if "clip" not in inputs or not inputs["clip"]:
                    if len(clip_sources) == 1:
                        src_id, slot_idx = clip_sources[0]
                        inputs["clip"] = [src_id, slot_idx]
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="reconnect_slot",
                                description=f"Connected missing 'clip' input to unambiguous source node '{src_id}' [slot {slot_idx}].",
                                target_input="clip",
                                source_node_id=src_id,
                                source_output_slot=slot_idx,
                            )
                        )
                    elif len(clip_sources) > 1:
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="substitution_blocked",
                                description=f"Automatic CLIP connection blocked: {len(clip_sources)} ambiguous CLIP sources detected.",
                                target_input="clip",
                            )
                        )

            # Repair KSampler missing MODEL
            if cls_name in ("KSampler", "KSamplerAdvanced"):
                if "model" not in inputs or not inputs["model"]:
                    if len(model_sources) == 1:
                        src_id, slot_idx = model_sources[0]
                        inputs["model"] = [src_id, slot_idx]
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="reconnect_slot",
                                description=f"Connected missing 'model' input to unambiguous source node '{src_id}' [slot {slot_idx}].",
                                target_input="model",
                                source_node_id=src_id,
                                source_output_slot=slot_idx,
                            )
                        )
                    elif len(model_sources) > 1:
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="substitution_blocked",
                                description=f"Automatic MODEL connection blocked: {len(model_sources)} ambiguous MODEL sources detected.",
                                target_input="model",
                            )
                        )

                # Repair KSampler missing latent_image
                if "latent_image" not in inputs or not inputs["latent_image"]:
                    empty_latents = [
                        (s_id, s_slot)
                        for s_id, s_slot in latent_sources
                        if repaired.get(s_id, {}).get("class_type") == "EmptyLatentImage"
                    ]
                    if len(empty_latents) == 1:
                        src_id, slot_idx = empty_latents[0]
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
                    elif len(empty_latents) > 1:
                        repairs.append(
                            RepairAction(
                                node_id=str(nid),
                                node_class=cls_name,
                                action_type="substitution_blocked",
                                description=f"Automatic latent connection blocked: {len(empty_latents)} ambiguous EmptyLatentImage sources detected.",
                                target_input="latent_image",
                            )
                        )

                # Repair KSampler missing positive / negative conditioning
                if ("positive" not in inputs or not inputs["positive"]) and len(cond_sources) == 2:
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

                if ("negative" not in inputs or not inputs["negative"]) and len(cond_sources) == 2:
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
