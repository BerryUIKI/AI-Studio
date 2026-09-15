"""Built-in high-level node definitions."""

from app.nodes.registry import registry
from app.schemas.node import (
    DataType,
    NodeCategory,
    NodeDefinition,
    NodePort,
    ParameterDef,
    ParameterType,
    SelectOption,
)

# 1. Text Input Node
registry.register(
    NodeDefinition(
        type="input.text",
        title="Text Input",
        category=NodeCategory.INPUT,
        description="Raw text or prompt input block",
        inputs=[],
        outputs=[
            NodePort(id="text", name="Text Output", type=DataType.STRING)
        ],
        parameters=[
            ParameterDef(
                name="value",
                label="Prompt / Text",
                type=ParameterType.TEXTAREA,
                default="",
                description="Enter text or prompt",
            )
        ],
    )
)

# 2. LLM Prompt Expander / Generator
registry.register(
    NodeDefinition(
        type="text.llm",
        title="LLM Prompt Expander",
        category=NodeCategory.TEXT,
        description="Generate or refine text using OpenAI/DeepSeek compatible LLMs",
        inputs=[
            NodePort(id="prompt", name="Prompt", type=DataType.STRING, required=True),
            NodePort(id="system_prompt", name="System Instruction", type=DataType.STRING, required=False),
        ],
        outputs=[
            NodePort(id="result", name="Generated Text", type=DataType.STRING)
        ],
        parameters=[
            ParameterDef(
                name="model",
                label="Model",
                type=ParameterType.SELECT,
                default="deepseek-chat",
                options=[
                    SelectOption(label="DeepSeek Chat (V3)", value="deepseek-chat"),
                    SelectOption(label="GPT-4o Mini", value="gpt-4o-mini"),
                    SelectOption(label="GPT-4o", value="gpt-4o"),
                    SelectOption(label="Claude 3.5 Sonnet", value="claude-3-5-sonnet"),
                ],
            ),
            ParameterDef(
                name="temperature",
                label="Creativity (Temperature)",
                type=ParameterType.NUMBER,
                default=0.7,
                min_value=0.0,
                max_value=2.0,
                step=0.1,
            ),
        ],
    )
)

# 3. Cloud Image Generator (FLUX / SD)
registry.register(
    NodeDefinition(
        type="image.generate",
        title="Cloud Image Generator",
        category=NodeCategory.IMAGE,
        description="Generate high-fidelity images via cloud API (FLUX / SDXL)",
        inputs=[
            NodePort(id="prompt", name="Prompt", type=DataType.STRING, required=True),
            NodePort(id="ref_image", name="Reference Image", type=DataType.IMAGE, required=False),
        ],
        outputs=[
            NodePort(id="image", name="Output Image", type=DataType.IMAGE)
        ],
        parameters=[
            ParameterDef(
                name="model",
                label="Model",
                type=ParameterType.SELECT,
                default="flux-schnell",
                options=[
                    SelectOption(label="FLUX.1 [schnell] (Fast)", value="flux-schnell"),
                    SelectOption(label="FLUX.1 [dev] (High Quality)", value="flux-dev"),
                    SelectOption(label="SDXL Turbo", value="sdxl-turbo"),
                ],
            ),
            ParameterDef(
                name="aspect_ratio",
                label="Aspect Ratio",
                type=ParameterType.SELECT,
                default="1:1",
                options=[
                    SelectOption(label="1:1 Square", value="1:1"),
                    SelectOption(label="16:9 Landscape", value="16:9"),
                    SelectOption(label="9:16 Portrait (Shorts)", value="9:16"),
                    SelectOption(label="4:3 Standard", value="4:3"),
                ],
            ),
        ],
    )
)

# 4. Preview / Display Node
registry.register(
    NodeDefinition(
        type="output.preview",
        title="Media Preview",
        category=NodeCategory.OUTPUT,
        description="Inspect and preview text, image, or video outputs",
        inputs=[
            NodePort(id="media", name="Media Input", type=DataType.IMAGE, required=True),
        ],
        outputs=[],
        parameters=[],
    )
)
