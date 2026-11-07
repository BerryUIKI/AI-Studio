// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { FirstImageGuide } from '../components/canvas/FirstImageGuide';
import { useCanvasStore } from '../stores/useCanvasStore';
import { useEngineStore, type EngineInstance } from '../stores/useEngineStore';
import { useCreationSetupStore } from '../stores/useCreationSetupStore';

const noop = () => undefined;

const engine = (overrides: Partial<EngineInstance>): EngineInstance => ({
  id: 'comfyui-managed', type: 'comfyui', name: 'ComfyUI Engine', status: 'stopped',
  ...overrides,
} as EngineInstance);

const provider = (overrides: Record<string, unknown>) => ({
  id: 'fal', name: 'fal.ai', is_configured: false, capabilities: ['txt2img'],
  supported_models: [], action_models: {}, description: '', upload_disclosure: '', website_url: '',
  ...overrides,
});

beforeEach(() => {
  useCanvasStore.setState({ nodes: [] });
  useEngineStore.setState({ instances: [] });
  useCreationSetupStore.setState({ models: [], providers: [], loading: false, error: null });
});
afterEach(cleanup);

describe('first-image guide', () => {
  it('stays out of the way once the canvas has content', () => {
    useCanvasStore.setState({ nodes: [{ id: 'n1' } as never] });
    render(<FirstImageGuide onCloudSetup={noop} onLocalSetup={noop} onOpenModels={noop} />);
    expect(screen.queryByLabelText('Create your first image')).toBeNull();
  });

  it('names the missing key instead of offering a generic cloud option', () => {
    useCreationSetupStore.setState({ providers: [provider({ capabilities: ['txt2img'] })] as never });
    render(<FirstImageGuide onCloudSetup={noop} onLocalSetup={noop} onOpenModels={noop} />);
    expect(screen.getByText(/Add an API key for a cloud provider/)).toBeTruthy();
    expect(screen.getByText('Set up cloud')).toBeTruthy();
  });

  it('reports a stopped engine rather than hiding the local path', () => {
    useEngineStore.setState({ instances: [engine({ status: 'stopped' })] });
    render(<FirstImageGuide onCloudSetup={noop} onLocalSetup={noop} onOpenModels={noop} />);
    expect(screen.getByText(/ComfyUI Engine is stopped/)).toBeTruthy();
    expect(screen.getByText('Start engine')).toBeTruthy();
  });

  it('reports a running engine that has no usable checkpoint', () => {
    useEngineStore.setState({ instances: [engine({ status: 'running' })] });
    render(<FirstImageGuide onCloudSetup={noop} onLocalSetup={noop} onOpenModels={noop} />);
    expect(screen.getByText(/no usable checkpoint/)).toBeTruthy();
    expect(screen.getByText('Browse models')).toBeTruthy();
  });

  it('reports the available checkpoints when the engine can use them', () => {
    useEngineStore.setState({ instances: [engine({ status: 'running' })] });
    useCreationSetupStore.setState({
      models: [{
        name: 'v1-5', category: 'checkpoint', file_path: 'C:/models/v1-5.safetensors',
        is_ready: true, engine_compatibility: ['comfyui'],
      }] as never,
    });
    render(<FirstImageGuide onCloudSetup={noop} onLocalSetup={noop} onOpenModels={noop} />);
    expect(screen.getByText(/1 usable checkpoint/)).toBeTruthy();
    // Nothing left to set up on this path.
    expect(screen.queryByText('Start engine')).toBeNull();
    expect(screen.queryByText('Browse models')).toBeNull();
  });
});
