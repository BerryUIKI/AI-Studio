/**
 * Starter directory for the unified provider console.
 *
 * Presets only prefill a form; they add no routing, capability or compatibility
 * claims. Anything a preset fills in is editable, and a custom entry is always
 * available for endpoints the directory does not list.
 */
import type { ImageAction } from '../../api/customProviders';

export type ProviderKind = 'llm' | 'image';

export interface ProviderPreset {
  id: string;
  kind: ProviderKind;
  name: string;
  /** Host shown under the name; empty for presets with a configurable endpoint. */
  host: string;
  baseUrl: string;
  /** Text-protocol providers leave this empty and accept any model id. */
  models: string[];
  actions: ImageAction[];
  /** Unsplash-style single glyph; the UI falls back to the initial. */
  badge: string;
}

const allImageActions: ImageAction[] = ['txt2img', 'img2img', 'inpaint', 'upscale'];

export const LLM_PRESETS: ProviderPreset[] = [
  { id: 'llama_server', kind: 'llm', name: 'llama.cpp', host: 'Embedded · 127.0.0.1:8080', baseUrl: 'http://127.0.0.1:8080/v1', models: [], actions: [], badge: 'L' },
  { id: 'openai', kind: 'llm', name: 'OpenAI', host: 'api.openai.com', baseUrl: 'https://api.openai.com/v1', models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'], actions: [], badge: 'O' },
  { id: 'deepseek', kind: 'llm', name: 'DeepSeek', host: 'api.deepseek.com', baseUrl: 'https://api.deepseek.com/v1', models: ['deepseek-chat', 'deepseek-reasoner'], actions: [], badge: 'D' },
  { id: 'siliconflow', kind: 'llm', name: 'SiliconFlow', host: 'api.siliconflow.cn', baseUrl: 'https://api.siliconflow.cn/v1', models: ['Qwen/Qwen2.5-7B-Instruct'], actions: [], badge: 'S' },
  { id: 'moonshot', kind: 'llm', name: 'Moonshot', host: 'api.moonshot.cn', baseUrl: 'https://api.moonshot.cn/v1', models: ['moonshot-v1-8k'], actions: [], badge: 'M' },
  { id: 'zhipu', kind: 'llm', name: 'Zhipu GLM', host: 'open.bigmodel.cn', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-4-plus'], actions: [], badge: 'Z' },
];

export const IMAGE_PRESETS: ProviderPreset[] = [
  { id: 'fal', kind: 'image', name: 'fal.ai', host: 'fal.run', baseUrl: 'https://fal.run', models: ['fal-ai/flux/schnell'], actions: allImageActions, badge: 'F' },
  { id: 'openai_image', kind: 'image', name: 'OpenAI Images', host: 'api.openai.com', baseUrl: 'https://api.openai.com/v1', models: ['gpt-image-1', 'dall-e-3'], actions: ['txt2img', 'img2img'], badge: 'O' },
  { id: 'siliconflow_image', kind: 'image', name: 'SiliconFlow Images', host: 'api.siliconflow.cn', baseUrl: 'https://api.siliconflow.cn/v1', models: ['Kwai-Kolors/Kolors'], actions: ['txt2img', 'img2img'], badge: 'S' },
];

export function presetsFor(kind: ProviderKind): ProviderPreset[] {
  return kind === 'llm' ? LLM_PRESETS : IMAGE_PRESETS;
}
