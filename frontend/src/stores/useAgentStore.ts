import { create } from 'zustand';
import { AgentChatMessage } from '../types/creative';

interface Conversation {
  id?: string;
  messages: AgentChatMessage[];
}

interface AgentState {
  conversations: Record<string, Conversation>;
  append: (project: string, message: AgentChatMessage) => void;
  setIdentity: (project: string, id: string) => void;
  restore: (project: string, id: string, messages: AgentChatMessage[]) => void;
}

// The backend owns durable transcripts. Retain panel state across navigation;
// reload uses the saved project/conversation identity to restore the transcript.
export const useAgentStore = create<AgentState>((set) => ({
  conversations: {},
  append: (project, message) => set((state) => ({ conversations: { ...state.conversations,
    [project]: { ...state.conversations[project], messages: [...(state.conversations[project]?.messages ?? []), message].slice(-100) },
  } })),
  setIdentity: (project, id) => set((state) => ({ conversations: { ...state.conversations,
    [project]: { id, messages: state.conversations[project]?.messages ?? [] },
  } })),
  restore: (project, id, messages) => set((state) => state.conversations[project] ? state : ({
    conversations: { ...state.conversations, [project]: { id, messages: messages.slice(-100) } },
  })),
}));
