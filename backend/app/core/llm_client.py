"""
OpenAI-Compatible LLM Client with Function Calling & Local Ollama Support.

Enables Berry AI Studio to interface with local Ollama instances (e.g. qwen2.5:7b, deepseek-r1:8b)
as well as cloud providers (SiliconFlow, DeepSeek, OpenAI) using standard chat completions & tool calling.
Follows zero-pollution async design with graceful fallback.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional
import httpx

from app.schemas.cloud import LLMConfig

logger = logging.getLogger(__name__)


AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "propose_creative_plan",
            "description": "Formulate a concrete creative generative plan (text-to-image, image-to-image, video, upscale, inpaint) for user review and approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["txt2img", "img2img", "inpaint", "upscale", "txt2video", "img2video"],
                        "description": "Primary generative action type.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Detailed, high-quality descriptive generation prompt.",
                    },
                    "negative_prompt": {
                        "type": "string",
                        "description": "Negative prompt keywords to avoid low quality or unwanted elements.",
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                        "description": "Target image/video aspect ratio.",
                    },
                    "steps": {
                        "type": "integer",
                        "description": "Sampling inference steps (typically 20-30).",
                    },
                    "engine": {
                        "type": "string",
                        "enum": ["managed_comfyui", "fal_ai", "siliconflow", "managed_webui"],
                        "description": "Target execution engine. Default to managed_comfyui for privacy or fal_ai/siliconflow for cloud.",
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model checkpoint name if specified.",
                    },
                    "chain_upscale": {
                        "type": "boolean",
                        "description": "Whether to chain an automated 2x super-resolution upscaling pass.",
                    },
                },
                "required": ["action", "prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_system_models",
            "description": "Check currently available model checkpoints and indexed local weights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter category such as 'checkpoint', 'lora', 'upscaler'.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_or_repair_workflow",
            "description": "Diagnose issues or recommend repairs for a ComfyUI DAG workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_description": {
                        "type": "string",
                        "description": "Error message or observed problem in the workflow.",
                    }
                },
                "required": ["issue_description"],
            },
        },
    },
]


SYSTEM_PROMPT = """You are Berry AI Studio's autonomous creative assistant and workflow architect.
Your goals:
1. Help the user design and plan generative artworks, videos, and ComfyUI workflows.
2. When the user wants to generate or edit images/videos, use the `propose_creative_plan` tool to formulate a concrete, high-quality action plan. Expand simple user ideas with vivid visual details (lighting, composition, rendering style, camera angle, and artistic aesthetics).
3. If the user asks about available models or system state, call `inspect_system_models`.
4. If the user encounters workflow issues or asks to check DAG connections, call `diagnose_or_repair_workflow`.
5. Always answer politely in the user's language (supporting both Chinese and English).
6. Never leak raw ComfyUI tensors or low-level clip handles to the user. Maintain high-level creative clarity.
"""


class LLMClient:
    """Async client communicating with OpenAI-compatible LLM endpoints (Ollama, SiliconFlow, DeepSeek, OpenAI)."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig()
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Reuse long-lived pooled client to prevent connection exhaustion."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def aclose(self) -> None:
        """Close pooled client on shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        """Send chat completion request with optional tool calling."""
        base_url = self.config.base_url.rstrip("/")
        chat_url = f"{base_url}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        client = self._get_client()
        resp = await client.post(chat_url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM request to {chat_url} failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()
