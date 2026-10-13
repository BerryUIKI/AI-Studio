import { useEffect } from 'react';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCreationSetupStore, modelsForProvider, providerConnection, localModelAvailable, localModelFilename } from '../../stores/useCreationSetupStore';
import { useEngineStore } from '../../stores/useEngineStore';

interface CreationSetupProps {
  onCloudSetup: () => void;
  onLocalSetup: () => void;
}

export function useCreationReadiness() {
  const connection = useCreativeStore((state) => state.connectionId);
  const model = useCreativeStore((state) => state.model);
  const reference = useCreativeStore((state) => state.referenceImage);
  const models = useCreationSetupStore((state) => state.models);
  const providers = useCreationSetupStore((state) => state.providers);
  const loading = useCreationSetupStore((state) => state.loading);
  const error = useCreationSetupStore((state) => state.error);
  const instances = useEngineStore((state) => state.instances);
  const action = reference ? 'img2img' : 'txt2img';
  const provider = providers.find((item) => providerConnection(item.id) === connection);
  const engine = instances.find((item) => (item.connection_id || item.id) === connection);
  const choices = provider ? modelsForProvider(provider, action)
    : models.filter((item) => localModelAvailable(item, engine?.type || '')).map(localModelFilename);
  const ready = !loading && !error && choices.includes(model)
    && (provider ? provider.is_configured : engine?.status === 'running');
  return { ready, choices, provider, engine, loading, error, connection, model };
}

export function CreationSetup({ onCloudSetup, onLocalSetup }: CreationSetupProps) {
  const readiness = useCreationReadiness();
  const providers = useCreationSetupStore((state) => state.providers);
  const refresh = useCreationSetupStore((state) => state.refresh);
  const instances = useEngineStore((state) => state.instances);
  const reference = useCreativeStore((state) => state.referenceImage);
  const action = reference ? 'img2img' : 'txt2img';

  useEffect(() => { void refresh(); }, [refresh]);
  const selectConnection = (connection: string) => {
    const provider = providers.find((item) => providerConnection(item.id) === connection);
    useCreativeStore.getState().setConnectionId(connection);
    const engine = instances.find((instance) => (instance.connection_id || instance.id) === connection);
    const localModels = useCreationSetupStore.getState().models.filter((item) => localModelAvailable(item, engine?.type || '')).map(localModelFilename);
    useCreativeStore.getState().setModel(provider ? modelsForProvider(provider, action)[0] || '' : localModels[0] || '');
  };

  return <div className="flex flex-wrap items-center gap-2 text-sm">
    <label htmlFor="creation-target">Create with</label>
    <select id="creation-target" value={readiness.connection} onChange={(event) => selectConnection(event.target.value)} className="max-w-48 rounded border border-slate-700 bg-slate-950 px-2 py-1">
      <option value="">Choose provider or engine</option>
      {!providers.some((item) => providerConnection(item.id) === readiness.connection) && !instances.some((item) => (item.connection_id || item.id) === readiness.connection)
        && readiness.connection && <option value={readiness.connection}>Setup required</option>}
      {providers.filter((provider) => modelsForProvider(provider, action).length > 0).map((provider) => <option key={provider.id} value={providerConnection(provider.id)}>{provider.name}{provider.is_configured ? '' : ' — key needed'}</option>)}
      {instances.filter((instance) => ['comfyui', 'webui'].includes(instance.type)).map((instance) => <option key={instance.id} value={instance.connection_id || instance.id}>{instance.name} — {instance.status}</option>)}
    </select>
    <label htmlFor="creation-model">Model</label>
    <select id="creation-model" value={readiness.model} onChange={(event) => useCreativeStore.getState().setModel(event.target.value)} className="max-w-48 rounded border border-slate-700 bg-slate-950 px-2 py-1">
      <option value="">Choose a validated model</option>
      {!readiness.choices.includes(readiness.model) && readiness.model && <option value={readiness.model}>Model needs validation</option>}
      {readiness.choices.map((name) => <option key={name} value={name}>{name}</option>)}
    </select>
    <button type="button" onClick={() => void refresh()} className="rounded border border-slate-700 px-2 py-1">Refresh readiness</button>
    {!readiness.ready && <div role="status" className="w-full text-amber-200">
      {readiness.loading ? 'Checking setup…' : readiness.error || 'Choose a configured cloud provider, or start an engine and validate its model.'}
      <div className="mt-1 flex gap-3">
        <button type="button" className="underline" onClick={onCloudSetup}>Set up cloud — no GPU required</button>
        <button type="button" className="underline" onClick={onLocalSetup}>Set up local engine and models</button>
      </div>
    </div>}
    {readiness.provider && <p className="w-full text-xs text-slate-400">{readiness.provider.upload_disclosure}</p>}
    {readiness.engine && readiness.choices.length > 0 && <p className="w-full text-xs text-amber-200">Model structure and prerequisites checked. Engine inference compatibility still needs a successful generation.</p>}
  </div>;
}
