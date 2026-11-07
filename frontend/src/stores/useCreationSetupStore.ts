import { create } from 'zustand';
import { CreativeActionType } from '../types/creative';

export interface CreationModel {
  id: string;
  name: string;
  file_path: string;
  category: string;
  is_ready: boolean;
  engine_compatibility: string[];
  possible_engines?: string[];
  integrity_status?: string;
  architecture_status?: string;
  architecture?: string;
  dependency_status?: string;
  guidance?: string;
}

export interface CreationProvider {
  id: string;
  name: string;
  is_configured: boolean;
  supported_models: string[];
  action_models?: Record<string, string[]>;
  capabilities: string[];
  upload_disclosure: string;
  provider_revision?: string;
  credential_revision?: number;
  setup_guidance?: string;
}

interface CreationSetupState {
  models: CreationModel[];
  providers: CreationProvider[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export const providerConnection = (id: string) => id === 'fal' ? 'fal_ai' : id;
export const modelsForProvider = (provider: CreationProvider, action: CreativeActionType): string[] =>
  provider.capabilities.includes(action) ? (provider.action_models?.[action] || provider.supported_models).filter((name) => provider.id !== 'openai' || name.startsWith('dall-e-')) : [];

let pending: Promise<void> | null = null;
export const localModelAvailable = (model: CreationModel, engine: string): boolean =>
  model.category === 'checkpoint' && (
    model.is_ready && model.engine_compatibility.includes(engine)
    || model.integrity_status === 'structurally-valid' && model.architecture_status === 'recognized'
      && model.dependency_status !== 'missing' && ['sd15', 'sd21', 'sdxl'].includes(model.architecture || '')
      && Boolean(model.possible_engines?.includes(engine))
  );
export const localModelFilename = (model: CreationModel): string => model.file_path.split(/[\\/]/).pop() || model.name;
export const useCreationSetupStore = create<CreationSetupState>((set) => ({
  models: [], providers: [], loading: false, error: null,
  refresh: () => {
    if (pending) return pending;
    set({ loading: true, error: null });
    pending = (async () => {
      try {
        const [models, providers] = await Promise.all([fetch('/api/v1/models'), fetch('/api/v1/cloud/providers')]);
        if (!models.ok || !providers.ok) throw new Error('Could not check models and providers. Refresh or open setup.');
        set({ models: await models.json(), providers: await providers.json() });
      } catch (cause) {
        set({ error: cause instanceof Error ? cause.message : 'Setup unavailable' });
      } finally {
        set({ loading: false });
        pending = null;
      }
    })();
    return pending;
  },
}));
