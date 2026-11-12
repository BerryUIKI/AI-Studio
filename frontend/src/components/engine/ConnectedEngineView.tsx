import { useUiText } from '../../i18n/useUiText';
import { useEngineStore } from '../../stores/useEngineStore';
import { useNavigationStore, type EngineViewType } from '../../stores/useNavigationStore';
import { EmbeddedEngineView } from './EmbeddedEngineView';

interface Props {
  engineType: EngineViewType;
  onDeployEngine: () => void;
  onOpenDirectory: (instanceId: string) => void;
}

export function ConnectedEngineView({ engineType, onDeployEngine, onOpenDirectory }: Props) {
  const ui = useUiText();
  const selectedId = useNavigationStore((state) => state.selectedEngineIds[engineType]);
  const instances = useEngineStore((state) => state.instances);
  const startEngine = useEngineStore((state) => state.startEngine);
  const candidates = instances.filter((instance) => instance.type === engineType);
  const instance = candidates.find((item) => item.id === selectedId)
    || candidates.find((item) => item.id === `${engineType}-managed`) || candidates[0];
  const endpoint = instance?.endpoint || (instance?.is_managed
    ? `http://127.0.0.1:${instance.port || (engineType === 'comfyui' ? 8188 : 7860)}` : null);

  return <EmbeddedEngineView key={instance?.id || engineType}
    title={instance?.name || (engineType === 'comfyui' ? ui('ui_comfyui') : ui('ui_sd_webui'))}
    endpoint={endpoint}
    isRunning={instance?.status === 'running' && instance.service_healthy !== false}
    isStarting={instance?.status === 'starting'}
    isInstalled={Boolean(instance && instance.status !== 'not_installed')}
    isManaged={instance?.is_managed ?? true}
    error={instance?.error_message}
    onStartEngine={async () => {
      if (!instance) throw new Error('No engine connection is registered. Open engine setup first.');
      const result = await startEngine(instance.id);
      if (!result.success) throw new Error(result.message || 'The engine could not be started.');
    }}
    onDeployEngine={onDeployEngine}
    onOpenDirectory={instance?.install_path ? () => onOpenDirectory(instance.id) : undefined}
  />;
}
