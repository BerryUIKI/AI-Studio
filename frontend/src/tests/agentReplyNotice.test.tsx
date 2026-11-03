// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { AgentPanelNotice } from '../components/agent/AgentPanelNotice';
import type { AgentChatMessage } from '../types/creative';

const message = (overrides: Partial<AgentChatMessage>): AgentChatMessage => ({
  id: 'm1', role: 'assistant', content: 'Reply', created_at: '2026-11-03T00:00:00Z', ...overrides,
});

afterEach(cleanup);

describe('agent reply notice', () => {
  it('shows the notice when the model was tried and failed', () => {
    render(<AgentPanelNotice message={message({ agent_mode: 'heuristic_fallback', agent_notice: 'The language model could not be used (connection refused).' })} />);
    expect(screen.getByRole('status').textContent).toContain('connection refused');
  });

  it('stays quiet for a normal model reply', () => {
    render(<AgentPanelNotice message={message({ agent_mode: 'llm' })} />);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('stays quiet when no model was configured, since nothing was attempted', () => {
    render(<AgentPanelNotice message={message({ agent_mode: 'heuristic', agent_notice: null })} />);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('stays quiet for messages saved before the field existed', () => {
    render(<AgentPanelNotice message={message({})} />);
    expect(screen.queryByRole('status')).toBeNull();
  });
});
