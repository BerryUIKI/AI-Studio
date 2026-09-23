"""Rule- and regex-based conversational assistant service for workflow and engine control (M9).

Provides deterministic intent matching, parameter extraction, model/engine recommendation, transparent
action plan formulation, and human-in-the-loop proposal execution. Bounded heuristic capabilities;
does not claim unconstrained natural-language understanding or arbitrary workflow synthesis.
"""

import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.schemas.agent import (
    AgentActionStep,
    AgentChatMessage,
    AgentChatRequest,
    AgentChatResponse,
    AgentIntent,
    AgentProposal,
)
from app.schemas.creative import (
    CreativeActionRequest,
    CreativeActionResult,
    CreativeActionType,
)


class AgentService:
    def __init__(
        self,
        model_catalog=None,
        credential_manager=None,
        creative_runner=None,
    ):
        self.model_catalog = model_catalog
        self.credential_manager = credential_manager
        self.creative_runner = creative_runner
        # In-memory conversation state: conversation_id -> list of AgentChatMessage
        self.conversations: Dict[str, List[AgentChatMessage]] = {}

    def _extract_aspect_ratio(self, text: str) -> str:
        lower = text.lower()
        if "16:9" in lower or "landscape" in lower or "widescreen" in lower or "wide" in lower:
            return "16:9"
        if "9:16" in lower or "portrait" in lower or "vertical" in lower:
            return "9:16"
        if "4:3" in lower:
            return "4:3"
        if "3:4" in lower:
            return "3:4"
        return "1:1"

    def _extract_steps(self, text: str) -> int:
        match = re.search(r"(\d+)\s*steps?", text, re.IGNORECASE)
        if match:
            return min(max(int(match.group(1)), 1), 60)
        lower = text.lower()
        if "high quality" in lower or "ultra detail" in lower or "photorealistic" in lower:
            return 30
        if "draft" in lower or "fast" in lower or "quick" in lower:
            return 15
        return 20

    def _extract_seed(self, text: str) -> int:
        match = re.search(r"seed\s*[:=]?\s*(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return -1

    def _extract_clean_prompt(self, text: str) -> str:
        # Strip common conversational commands
        cleaned = re.sub(
            r"^(please\s+)?(can\s+you\s+)?(create|generate|make|render|draw|animate)\s+(an?\s+)?(image|picture|video|animation)?(\s+of)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        # Remove trailing chain instructions like "then upscale 2x"
        cleaned = re.sub(r"(,\s*)?(and\s+)?then\s+upscale.*$", "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned if cleaned else text

    def _detect_engine(self, text: str, preferred: Optional[str] = None) -> tuple[str, str]:
        """Returns (engine_id, cost_disclaimer)."""
        lower = text.lower()
        if preferred:
            if preferred in ("fal_ai", "fal"):
                return "fal_ai", "Cloud BYOK: Uses your configured Fal.ai API key"
            if preferred in ("siliconflow", "silicon"):
                return "siliconflow", "Cloud BYOK: Uses your configured SiliconFlow API key"
            if preferred == "managed_webui":
                return "managed_webui", "Local SD WebUI: Free local execution on your hardware"
            return "managed_comfyui", "Local ComfyUI: Free local execution, 100% private"

        if "fal" in lower:
            return "fal_ai", "Cloud BYOK: Uses your configured Fal.ai API key"
        if "silicon" in lower:
            return "siliconflow", "Cloud BYOK: Uses your configured SiliconFlow API key"
        if "webui" in lower:
            return "managed_webui", "Local SD WebUI: Free local execution on your hardware"

        return "managed_comfyui", "Local ComfyUI: Free local execution, 100% private"

    def _resolve_model(self, engine_id: str, action: CreativeActionType) -> str:
        """Finds suitable default or catalog-indexed model for the engine and action."""
        if engine_id == "fal_ai":
            if action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO):
                return "fal-ai/fast-svd"
            return "fal-ai/flux/schnell"
        if engine_id == "siliconflow":
            if action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO):
                return "THUDM/CogVideoX-5b"
            return "black-forest-labs/FLUX.1-schnell"

        # Check local model catalog if available
        if self.model_catalog:
            try:
                models = self.model_catalog.get_models()
                if models:
                    return models[0].name
            except Exception:
                pass

        if action in (CreativeActionType.TXT2VIDEO, CreativeActionType.IMG2VIDEO):
            return "svd_xt.safetensors"
        return "v1-5-pruned-emaonly.safetensors"

    async def process_chat(self, req: AgentChatRequest) -> AgentChatResponse:
        """Process conversational user message and formulate a transparent action plan."""
        conv_id = req.conversation_id or str(uuid4())
        if conv_id not in self.conversations:
            self.conversations[conv_id] = []

        history = self.conversations[conv_id]
        user_msg = AgentChatMessage(role="user", content=req.message)
        history.append(user_msg)

        msg_lower = req.message.lower()

        # Check for informational questions without creative action intent
        if any(q in msg_lower for q in ["what models", "list models", "available models"]):
            model_names = []
            if self.model_catalog:
                try:
                    models = self.model_catalog.get_models()
                    model_names = [m.name for m in models]
                except Exception:
                    pass
            content = f"You have {len(model_names)} model(s) indexed: {', '.join(model_names) if model_names else 'No models found yet.'} You can rescan or add directories in the Environment Manager."
            assistant_msg = AgentChatMessage(role="assistant", content=content)
            history.append(assistant_msg)
            return AgentChatResponse(conversation_id=conv_id, message=assistant_msg, proposal=None)

        if any(q in msg_lower for q in ["how are you", "help", "what can you do", "who are you"]):
            content = (
                "I am your Berry AI Creative Assistant. I can help you formulate, configure, "
                "and execute generative workflows across local ComfyUI, WebUI, and cloud providers. "
                "Tell me what you'd like to create (e.g. 'Create a futuristic cityscape in 16:9') "
                "and I'll prepare a transparent action plan for your review."
            )
            assistant_msg = AgentChatMessage(role="assistant", content=content)
            history.append(assistant_msg)
            return AgentChatResponse(conversation_id=conv_id, message=assistant_msg, proposal=None)

        if any(w in msg_lower for w in ["validate workflow", "repair workflow", "diagnose workflow", "check graph"]):
            content = (
                "Berry Studio includes an automated ComfyUI DAG validator and repair engine (M10). "
                "You can submit workflows via `/api/v1/workflow/validate` to inspect topological cycles, "
                "missing MODEL/CLIP/VAE connections, and missing checkpoint dependencies. "
                "The repair engine reconnects unambiguous broken links and substitutes family-compatible "
                "indexed checkpoints while blocking ambiguous or cross-family mutations."
            )
            assistant_msg = AgentChatMessage(role="assistant", content=content)
            history.append(assistant_msg)
            return AgentChatResponse(conversation_id=conv_id, message=assistant_msg, proposal=None)

        # Detect intent
        is_video = any(w in msg_lower for w in ["video", "animate", "animation", "motion", "clip"])
        is_upscale = any(w in msg_lower for w in ["upscale", "super resolution", "enlarge", "2x", "4x"])
        is_inpaint = any(w in msg_lower for w in ["inpaint", "mask", "replace object", "fill in"])
        has_compound_upscale = is_upscale and any(w in msg_lower for w in ["then", "and", "after", "create", "generate"])

        target_engine, cost_disclaimer = self._detect_engine(req.message, req.preferred_engine)
        aspect_ratio = self._extract_aspect_ratio(req.message)
        steps = self._extract_steps(req.message)
        seed = self._extract_seed(req.message)
        prompt = self._extract_clean_prompt(req.message)

        chain_steps: List[AgentActionStep] = []
        explanation_parts = []

        if is_video:
            if req.selected_asset_id:
                action_type = CreativeActionType.IMG2VIDEO
                intent_name = "img2video"
                title = "Image-to-Video Animation Plan"
                summary = f"Animate selected image using {target_engine}."
                explanation_parts.append(f"Using selected canvas image as source for video motion synthesis.")
            else:
                action_type = CreativeActionType.TXT2VIDEO
                intent_name = "txt2video"
                title = "Text-to-Video Generation Plan"
                summary = f"Synthesize new video clip from prompt using {target_engine}."
                explanation_parts.append(f"Generating video sequence from text prompt.")

            model = self._resolve_model(target_engine, action_type)
            params = {
                "prompt": prompt,
                "negative_prompt": "low quality, flickering, jittery, distorted",
                "fps": 16,
                "num_frames": 25,
                "motion_bucket_id": 127,
                "aspect_ratio": aspect_ratio,
                "seed": seed,
            }
            if req.selected_asset_id:
                params["input_image_id"] = req.selected_asset_id

            chain_steps.append(
                AgentActionStep(
                    step_number=1,
                    action=action_type,
                    engine_id=target_engine,
                    model=model,
                    parameters=params,
                    description=summary,
                )
            )

        elif is_upscale and not has_compound_upscale:
            action_type = CreativeActionType.UPSCALE
            intent_name = "upscale"
            title = "Image Upscaling Plan"
            summary = f"Upscale image 2x using {target_engine}."
            model = self._resolve_model(target_engine, action_type)
            params = {
                "input_image_id": req.selected_asset_id or "",
                "upscale_factor": 2.0,
            }
            explanation_parts.append("Super-resolution upscaling to double visual fidelity.")
            chain_steps.append(
                AgentActionStep(
                    step_number=1,
                    action=action_type,
                    engine_id=target_engine,
                    model=model,
                    parameters=params,
                    description=summary,
                )
            )

        elif is_inpaint:
            action_type = CreativeActionType.INPAINT
            intent_name = "inpaint"
            title = "Inpainting Editing Plan"
            summary = f"Inpaint masked region with target prompt using {target_engine}."
            model = self._resolve_model(target_engine, action_type)
            params = {
                "prompt": prompt,
                "negative_prompt": "blurry, bad seams, artifacting",
                "input_image_id": req.selected_asset_id or "",
                "steps": steps,
                "cfg_scale": 7.5,
                "denoise": 0.85,
                "seed": seed,
            }
            explanation_parts.append("Localized inpainting replacement inside specified mask area.")
            chain_steps.append(
                AgentActionStep(
                    step_number=1,
                    action=action_type,
                    engine_id=target_engine,
                    model=model,
                    parameters=params,
                    description=summary,
                )
            )

        else:
            # Standard Text-to-Image (with optional chained upscale)
            action_type = CreativeActionType.TXT2IMG
            intent_name = "txt2img"
            title = "Text-to-Image Creation Plan"
            summary = f"Generate {aspect_ratio} image via {target_engine}."
            model = self._resolve_model(target_engine, action_type)
            params = {
                "prompt": prompt,
                "negative_prompt": "blurry, low quality, deformed, distorted, bad anatomy",
                "aspect_ratio": aspect_ratio,
                "steps": steps,
                "cfg_scale": 7.0,
                "seed": seed,
            }
            explanation_parts.append(f"Generating image with prompt: '{prompt}' at {aspect_ratio} aspect ratio.")
            chain_steps.append(
                AgentActionStep(
                    step_number=1,
                    action=action_type,
                    engine_id=target_engine,
                    model=model,
                    parameters=params,
                    description=f"Generate initial image at {aspect_ratio}",
                )
            )

            if has_compound_upscale:
                title = "Compound Generate & Upscale Plan"
                summary += " Followed by 2x high-resolution upscaling."
                explanation_parts.append("Chaining an automated 2x upscaling pass upon completion.")
                chain_steps.append(
                    AgentActionStep(
                        step_number=2,
                        action=CreativeActionType.UPSCALE,
                        engine_id=target_engine,
                        model=model,
                        parameters={"upscale_factor": 2.0},
                        description="Upscale result 2x",
                    )
                )

        explanation = " ".join(explanation_parts)
        proposal = AgentProposal(
            intent=intent_name,
            title=title,
            summary=summary,
            target_engine=target_engine,
            model=chain_steps[0].model,
            parameters=chain_steps[0].parameters,
            chain_steps=chain_steps,
            estimated_calls=len(chain_steps),
            cost_disclaimer=cost_disclaimer,
            explanation=explanation,
            requires_user_approval=True,
            approved=False,
        )

        content = (
            f"I have prepared an action plan for: **{title}**.\n\n"
            f"- **Target Engine**: `{target_engine}`\n"
            f"- **Model**: `{proposal.model}`\n"
            f"- **Parameters**: Aspect ratio `{aspect_ratio}`, Steps `{steps}`\n"
            f"- **Cost & Privacy**: {cost_disclaimer}\n\n"
            f"Please review the proposed plan below and click **Approve & Run** when ready."
        )

        assistant_msg = AgentChatMessage(role="assistant", content=content, proposal=proposal)
        history.append(assistant_msg)

        return AgentChatResponse(
            conversation_id=conv_id,
            message=assistant_msg,
            proposal=proposal,
        )

    async def execute_proposal(self, proposal: AgentProposal, project_id: Optional[str] = None) -> List[CreativeActionResult]:
        """Execute an approved proposal through CreativeRunner with strict human-in-the-loop gate."""
        if not proposal.approved:
            raise PermissionError("Cannot execute unapproved proposal. Explicit user approval is required.")

        if not self.creative_runner:
            raise RuntimeError("CreativeRunner is not available on AgentService.")

        results: List[CreativeActionResult] = []
        last_asset_id: Optional[str] = None

        for step in proposal.chain_steps:
            params = dict(step.parameters)
            # If chained step needs input image from prior step
            if step.action in (CreativeActionType.UPSCALE, CreativeActionType.IMG2IMG, CreativeActionType.IMG2VIDEO):
                if not params.get("input_image_id") and last_asset_id:
                    params["input_image_id"] = last_asset_id

            req = CreativeActionRequest(
                action=step.action,
                engine_id=step.engine_id,
                model=step.model,
                project_id=project_id,
                **params,
            )
            result = await self.creative_runner.execute(req)
            results.append(result)
            if result.asset_id:
                last_asset_id = result.asset_id

        return results
