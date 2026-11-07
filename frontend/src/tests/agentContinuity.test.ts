import { beforeEach, describe, expect, it } from 'vitest';
import { useAgentStore } from '../stores/useAgentStore';
import { nextResultPosition } from '../utils/canvasPlacement';

describe('project-linked Agent state', () => {
  beforeEach(() => useAgentStore.setState({ conversations: {} }));

  it('keeps conversation identity and bounds messages separately for each project', () => {
    useAgentStore.getState().setIdentity('a', 'conversation-a');
    for (let i = 0; i < 120; i++) useAgentStore.getState().append('a', { id: String(i), role: 'user', content: String(i), created_at: 'now' });
    useAgentStore.getState().setIdentity('b', 'conversation-b');
    expect(useAgentStore.getState().conversations.a.id).toBe('conversation-a');
    expect(useAgentStore.getState().conversations.a.messages).toHaveLength(100);
    expect(useAgentStore.getState().conversations.b.messages).toHaveLength(0);
  });

  it('does not overwrite a new conversation with a delayed history response', () => {
    useAgentStore.getState().setIdentity('a', 'new');
    useAgentStore.getState().restore('a', 'old', []);
    expect(useAgentStore.getState().conversations.a.id).toBe('new');
  });

  it('places repeated results near their source without overlapping', () => {
    const source = { id: 'source', type: 'imageCard', position: { x: 20, y: 30 }, data: { assetId: 'asset', imageUrl: '', width: 512, height: 512 } };
    const first = nextResultPosition([source], 'asset');
    const second = nextResultPosition([source, { ...source, id: 'output', position: first }], 'asset');
    expect(first).toEqual({ x: 380, y: 30 });
    expect(second).toEqual({ x: 380, y: 470 });
  });
});
