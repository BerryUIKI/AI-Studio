// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Dialog } from '../components/ui/Dialog';
import { ExitConfirmDialog } from '../components/launcher/ExitConfirmDialog';
import { EngineNotInstalledModal } from '../components/launcher/EngineNotInstalledModal';
import { defaultBuiltinInstances } from '../stores/useEngineStore';

afterEach(cleanup);

it('only dismisses the topmost dialog and restores focus to its parent', () => {
  const parentClose = vi.fn(), childClose = vi.fn();
  const parent = render(<Dialog title="Parent" onClose={parentClose}><button>Open child</button></Dialog>);
  const opener = screen.getByRole('button', { name: 'Open child' });
  opener.focus();
  const child = render(<Dialog title="Child" onClose={childClose}><button>Child action</button></Dialog>);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(childClose).toHaveBeenCalledOnce();
  expect(parentClose).not.toHaveBeenCalled();
  child.unmount();
  expect(document.activeElement).toBe(opener);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(parentClose).toHaveBeenCalledOnce();
  parent.unmount();
});

it('makes remembered exit policy keyboard selectable without bypassing active-task decisions', () => {
  const keep = vi.fn(), stop = vi.fn(), cancel = vi.fn();
  render(<ExitConfirmDialog isOpen runningEngines={[]} activeTasksCount={2} onKeepRunning={keep} onCloseAllAndExit={stop} onCancel={cancel} />);
  expect(screen.getByRole('dialog', { name: 'Exit Berry' })).toBeTruthy();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Remember my choice in Settings' }));
  fireEvent.click(screen.getByRole('button', { name: 'Keep Running' }));
  expect(keep).toHaveBeenCalledWith(true);
  expect(stop).not.toHaveBeenCalled();
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(cancel).toHaveBeenCalledOnce();
});

it('offers named keyboard-accessible repair actions and restores the opener', () => {
  const opener = document.createElement('button');
  document.body.append(opener); opener.focus();
  const close = vi.fn(), deploy = vi.fn();
  const modal = render(<EngineNotInstalledModal isOpen instance={defaultBuiltinInstances.find((item) => item.type === 'comfyui')!} onClose={close} onDeploy={deploy} onLocate={vi.fn()} />);
  expect(screen.getByRole('dialog', { name: 'Engine setup required' })).toBeTruthy();
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close engine setup' }));
  fireEvent.click(screen.getByRole('button', { name: /Deploy/ }));
  expect(deploy).toHaveBeenCalledWith('comfyui');
  modal.unmount(); expect(document.activeElement).toBe(opener); opener.remove();
});
