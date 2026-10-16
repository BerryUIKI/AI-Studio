import { useCreativeStore } from '../stores/useCreativeStore';
import { providerConnection, useCreationSetupStore } from '../stores/useCreationSetupStore';
import { CreativeActionType } from '../types/creative';

/** Cloud actions come from the selected catalog entry; local adapters retain their UI. */
export function useCreativeCapabilities() {
  const connection = useCreativeStore((state) => state.connectionId);
  const capabilities = useCreationSetupStore((state) => {
    const provider = state.providers.find((item) => providerConnection(item.id) === connection);
    if (provider) return provider.capabilities.join(',');
    return ['cloud', 'cloud_default', 'volcengine', 'openai', 'fal_ai', 'siliconflow'].includes(connection) || connection.startsWith('custom-') ? '' : null;
  });
  return (action: CreativeActionType) => capabilities === null || capabilities.split(',').includes(action);
}
