export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };
export type AdapterMode = 'rest' | 'javascript' | 'python' | 'python_sdk';
export type ImageAction = 'txt2img' | 'img2img' | 'inpaint' | 'upscale';

export interface CustomProviderSpec {
  id: string;
  name: string;
  endpoint: string;
  models: string[];
  actions: ImageAction[];
  mode: AdapterMode;
  source: string;
  body_template: Record<string, Json>;
  result_path: string;
  response_format: 'url' | 'b64_json';
  auth: 'bearer' | 'header' | 'none';
  auth_header: string;
  request_timeout: number;
  worker_timeout: number;
  max_requests: number;
  requirements: string;
  sdk_allow_credentials: boolean;
  upload_disclosure: string;
  revision?: string;
}

export interface CustomProviderRecord {
  spec: CustomProviderSpec;
  trusted_revision: string | null;
  execution_trusted: boolean;
}

export interface FixtureResult {
  output: { type: string; value: Json };
  broker_requests: number;
  evidence_level: 'broker-fixture';
  live_inference: false;
}

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1/custom-providers${path}`, {
    method, ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  });
  if (!response.ok) throw new Error(`Custom platform operation failed (HTTP ${response.status}). Check the configuration, approval and isolated environment.`);
  return response.json() as Promise<T>;
}

export const customProviders = {
  list: () => request<CustomProviderRecord[]>(''),
  save: (spec: CustomProviderSpec, approve_execution: boolean) => request<CustomProviderRecord>('', 'PUT', { spec, approve_execution }),
  remove: (id: string) => request<{ success: boolean }>(`/${encodeURIComponent(id)}`, 'DELETE'),
  fixture: (id: string, inputs: Record<string, Json>, response: Json) =>
    request<FixtureResult>(`/${encodeURIComponent(id)}/fixture`, 'POST', { inputs, response }),
  prepare: (id: string) => request<{ ready: boolean }>(`/${encodeURIComponent(id)}/prepare-sdk`, 'POST'),
};

export const STARTER_SOURCE: Record<Exclude<AdapterMode, 'rest'>, string> = {
  javascript: `async function execute(input, ctx) {
  const result = await ctx.request({body: {model: input.model, prompt: input.prompt, size: input.width + 'x' + input.height}});
  return {type: 'image', value: {url: result.data[0].url}};
}`,
  python: `async def execute(input, ctx):
    result = await ctx.request({'body': {'model': input['model'], 'prompt': input['prompt'], 'size': f"{input['width']}x{input['height']}"}})
    return {'type': 'image', 'value': {'url': result['data'][0]['url']}}
`,
  python_sdk: `async def execute(input, ctx):
    # Import your approved, pinned SDK here. SDK code has OS/network access.
    # ctx.api_key is available only with explicit SDK credential access.
    # This starter uses the host broker so fixture responses work without a key.
    result = await ctx.request({'body': {'model': input['model'], 'prompt': input['prompt']}})
    return {'type': 'image', 'value': {'url': result['data'][0]['url']}}
`,
};

export function newCustomProvider(): CustomProviderSpec {
  return { id: 'custom-platform', name: '', endpoint: '', models: [], actions: ['txt2img'], mode: 'rest', source: '',
    body_template: { model: '{{model}}', prompt: '{{prompt}}', size: '{{width}}x{{height}}', n: 1 },
    result_path: 'data.0.url', response_format: 'url', auth: 'bearer', auth_header: 'Authorization',
    request_timeout: 120, worker_timeout: 150, max_requests: 4, requirements: '', sdk_allow_credentials: false,
    upload_disclosure: 'Prompts and selected input images are sent to this user-configured platform.' };
}
