import { AlertTriangle } from 'lucide-react';
import { useUiText } from '../../i18n/useUiText';
import type { AgentChatMessage } from '../../types/creative';

/**
 * Says so when the reply came from the rule engine after the configured model failed.
 *
 * Without it a degraded reply reads exactly like model reasoning, which is the
 * failure this exists to prevent. A reply that never attempted a model stays quiet.
 */
export function AgentPanelNotice({ message }: { message: AgentChatMessage }) {
  const ui = useUiText();
  if (message.agent_mode !== 'heuristic_fallback' || !message.agent_notice) return null;
  return (
    <div role="status" className="mt-2 flex items-start gap-1.5 rounded-lg border border-amber-800/50 bg-amber-950/40 px-2.5 py-2 text-[11px] leading-relaxed text-amber-200">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{ui.lookup(message.agent_notice)}</span>
    </div>
  );
}
