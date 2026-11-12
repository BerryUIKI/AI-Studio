// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Titlebar, type TitlebarProps } from '../components/titlebar/Titlebar';
import { defaultBuiltinInstances, useEngineStore } from '../stores/useEngineStore';

vi.mock('../components/titlebar/GpuStatusIndicator', () => ({ GpuStatusIndicator: () => null }));
afterEach(() => { cleanup(); useEngineStore.setState({ instances: defaultBuiltinInstances }); });

const noop = () => undefined;
const props: TitlebarProps = {
  backendOnline: true, comfyStatus: { online: true, port: 8999 }, runtimeStatus: null,
  toggleRuntime: noop, onImportImage: noop, onOpenCloud: noop, onOpenManager: noop,
  showAgentPanel: false, onToggleAgent: noop, showNodePalette: false, onToggleNodePalette: noop,
  onRunWorkflow: noop, isExecuting: false, hasNodes: false, onClearCanvas: noop,
};

it('opens the configured managed endpoint rather than the prototype port', () => {
  useEngineStore.setState({ instances: [{ ...defaultBuiltinInstances.find((item) => item.id === 'comfyui-managed')!, endpoint: 'http://127.0.0.1:9311', connection_id: 'comfyui-managed' }] });
  render(<Titlebar {...props} />);
  expect(screen.getByRole('link', { name: 'Open ComfyUI native web interface in a new tab' }).getAttribute('href')).toBe('http://127.0.0.1:9311');
});

it('uses the reported healthy service port when no connection endpoint is indexed', () => {
  useEngineStore.setState({ instances: [] });
  render(<Titlebar {...props} />);
  expect(screen.getByRole('link', { name: 'Open ComfyUI native web interface in a new tab' }).getAttribute('href')).toBe('http://127.0.0.1:8999');
});
