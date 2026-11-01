import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { EngineRemovalDialog } from './EngineRemovalDialog';
import type { EngineInstance } from '../../stores/useEngineStore';

const instance: EngineInstance = {
  id: 'comfyui-managed', type: 'comfyui', name: 'ComfyUI', is_managed: true,
  is_builtin: false, status: 'stopped', capabilities: [],
};
const noop = () => undefined;

describe('removal confirmation', () => {
  it('explains complete backup retention before managed uninstall', () => {
    const markup = renderToStaticMarkup(<EngineRemovalDialog instance={instance} onClose={noop} onCompleted={noop} />);
    expect(markup).toContain('role="alertdialog"');
    expect(markup).toContain('entire engine folder');
    expect(markup).toContain('Shared models and application data stay in place');
    expect(markup).toContain('Uninstall and retain files');
  });
  it('discloses external removal as connection-only', () => {
    const markup = renderToStaticMarkup(<EngineRemovalDialog instance={{ ...instance, is_managed: false }} onClose={noop} onCompleted={noop} />);
    expect(markup).toContain('all its files stay in place');
    expect(markup).toContain('Remove connection');
    expect(markup).not.toContain('Uninstall and retain files');
  });
  it('requires the managed engine to be stopped', () => {
    const markup = renderToStaticMarkup(<EngineRemovalDialog instance={{ ...instance, status: 'running' }} onClose={noop} onCompleted={noop} />);
    expect(markup).toContain('Stop this managed engine');
    expect(markup).toMatch(/<button disabled=""[^>]*>Uninstall and retain files<\/button>/);
  });
});
