// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectManagerModal } from '../components/project/ProjectManagerModal';
import { useProjectStore } from '../stores/useProjectStore';
import type { Project } from '../types/project';

const project: Project = {
  id: 'project', name: 'Acceptance canvas', version: 1,
  created_at: '2026-10-13T00:00:00Z', updated_at: '2026-10-13T00:00:00Z',
  canvas: { version: 1, nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
};

beforeEach(() => {
  useProjectStore.setState({ ...useProjectStore.getInitialState(), projects: [project],
    currentProject: project, createProject: vi.fn().mockResolvedValue(project),
    renameProject: vi.fn().mockResolvedValue(true) });
});
afterEach(() => { cleanup(); useProjectStore.setState(useProjectStore.getInitialState()); });

describe('project dialog accessible controls', () => {
  it('names project search and creation fields and submits the named field', async () => {
    render(<ProjectManagerModal isOpen />);
    expect(screen.getByRole('textbox', { name: 'Search projects...' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'New Project' }));
    const name = screen.getByRole('textbox', { name: 'Project name...' });
    fireEvent.change(name, { target: { value: 'Named project' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(useProjectStore.getState().createProject).toHaveBeenCalledWith('Named project'));
  });

  it('names rename input and icon controls and supports both cancel and save', async () => {
    render(<ProjectManagerModal isOpen />);
    fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Project name...' }), {
      target: { value: 'Cancelled name' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(useProjectStore.getState().renameProject).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Project name...' }), {
      target: { value: 'Saved name' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(useProjectStore.getState().renameProject).toHaveBeenCalledWith('project', 'Saved name'));
  });
});
