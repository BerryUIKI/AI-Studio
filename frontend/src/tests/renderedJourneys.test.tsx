// @vitest-environment jsdom
import { useEffect } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Dialog } from '../components/ui/Dialog';
import { ViewContainer } from '../components/navigation/ViewContainer';
import { useNavigationStore } from '../stores/useNavigationStore';
import { useCreationSetupStore } from '../stores/useCreationSetupStore';
import { useCreativeStore } from '../stores/useCreativeStore';
import { CreationDock } from '../components/canvas/CreationDock';
import { AgentPanel } from '../components/agent/AgentPanel';
import { useAgentStore } from '../stores/useAgentStore';
import { acceptsCanvasShortcut } from '../utils/canvasShortcuts';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
  useCreationSetupStore.setState({ models: [], providers: [], loading: false, error: null });
  useCreativeStore.setState({ isGenerating: false, referenceImage: null, connectionId: 'comfyui-managed', model: '', error: null });
});

describe('rendered first-image and accessibility journeys', () => {
  it('traps focus, dismisses on Escape, and restores the triggering control', () => {
    const trigger = document.createElement('button');
    document.body.append(trigger); trigger.focus();
    const close = vi.fn();
    const modal = render(<Dialog title="Test dialog" onClose={close}><button>First</button><button>Last</button></Dialog>);
    expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true');
    expect(document.activeElement).toBe(screen.getByText('First'));
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(screen.getByText('Last'));
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(screen.getByText('First'));
    fireEvent.keyDown(document, { key: 'Escape' }); expect(close).toHaveBeenCalledOnce();
    modal.unmount(); expect(document.activeElement).toBe(trigger); trigger.remove();
  });

  it('unmounts inactive views and releases their listeners while retaining store state', () => {
    const mounted = vi.fn(); const disposed = vi.fn();
    function Canvas() { useEffect(() => { mounted(); return disposed; }, []); return <p>Canvas</p>; }
    useNavigationStore.setState({ activeView: 'canvas' });
    render(<ViewContainer>{{ canvas: <Canvas />, models: <p>Models</p> }}</ViewContainer>);
    act(() => useNavigationStore.getState().setActiveView('models'));
    expect(disposed).toHaveBeenCalledOnce();
    expect(screen.queryByText('Canvas')).toBeNull();
    expect(screen.getByText('Models')).toBeTruthy();
    act(() => useNavigationStore.getState().setActiveView('canvas'));
    expect(mounted).toHaveBeenCalledTimes(2);
  });

  it('offers a repair path and prevents generation with no provider or validated model', async () => {
    const cloud = vi.fn();
    render(<CreationDock onCloudSetup={cloud} />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Generate Image' }).hasAttribute('disabled')).toBe(true));
    fireEvent.click(screen.getByText('Set up cloud — no GPU required'));
    expect(cloud).toHaveBeenCalledOnce();
    expect(screen.queryByText('Experimental video')).toBeNull();
  });

  it('selects an explicit cloud provider and its model without exposing local parameters', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes('providers') ? [{
      id: 'fal', name: 'Fal.ai', is_configured: true, supported_models: ['flux-schnell'], capabilities: ['txt2img'], upload_disclosure: 'Prompts are uploaded to Fal.ai.',
    }] : [] })));
    render(<CreationDock />);
    await screen.findByRole('option', { name: 'Fal.ai' });
    fireEvent.change(screen.getByLabelText('Create with'), { target: { value: 'fal_ai' } });
    expect(useCreativeStore.getState().connectionId).toBe('fal_ai');
    expect(useCreativeStore.getState().model).toBe('flux-schnell');
    expect(screen.getByRole('button', { name: 'Generate Image' }).hasAttribute('disabled')).toBe(false);
    expect(screen.queryByText('Advanced')).toBeNull();
    expect(screen.queryByText('CFG Scale')).toBeNull();
    expect(screen.getByText('Prompts are uploaded to Fal.ai.')).toBeTruthy();
  });

  it.each(['input', 'textarea', 'select', 'button'])('respects focused %s controls', (tag) => {
    expect(acceptsCanvasShortcut(document.createElement(tag))).toBe(false);
  });

  it('respects contenteditable controls and dialog focus', () => {
    const editable = document.createElement('div'); editable.setAttribute('contenteditable', 'true');
    expect(acceptsCanvasShortcut(editable)).toBe(false);
    const dialog = document.createElement('div'); dialog.setAttribute('role', 'dialog');
    const control = document.createElement('span'); dialog.append(control);
    expect(acceptsCanvasShortcut(control)).toBe(false);
  });

  it('resends Agent conversation identity on a follow-up and restores it after panel remount', async () => {
    useAgentStore.setState({ conversations: {} });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() });
    const requests: Record<string, unknown>[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => ({ ok: true, json: async () => {
      if (url.includes('/conversation')) return null;
      requests.push(JSON.parse(String(init?.body)));
      return { conversation_id: 'conversation', message: { id: `reply-${requests.length}`, role: 'assistant', content: 'Reply', created_at: '2026-10-13T00:00:00Z' } };
    } })));
    const panel = render(<AgentPanel isOpen onClose={() => undefined} />);
    fireEvent.change(screen.getByLabelText('Message to Creative Assistant'), { target: { value: 'First' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await waitFor(() => expect(requests).toHaveLength(1));
    await waitFor(() => expect(useAgentStore.getState().conversations.unassigned.id).toBe('conversation'));
    panel.unmount(); render(<AgentPanel isOpen onClose={() => undefined} />);
    fireEvent.change(screen.getByLabelText('Message to Creative Assistant'), { target: { value: 'Follow-up' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].conversation_id).toBe('conversation');
  });
});
