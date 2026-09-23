import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  Send,
  X,
  Play,
  AlertCircle,
  ShieldCheck,
  RefreshCw,
  Image as ImageIcon,
  Zap,
} from 'lucide-react';
import { AgentChatMessage, AgentProposal, CreativeActionResult, ImageCardData } from '../../types/creative';
import { useCanvasStore } from '../../stores/useCanvasStore';


interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AgentPanel: React.FC<AgentPanelProps> = ({ isOpen, onClose }) => {
  const [messages, setMessages] = useState<AgentChatMessage[]>([
    {
      id: 'welcome-1',
      role: 'assistant',
      content:
        "Hello! I am your Berry Creative Assistant. You can describe any generative workflow in natural language (e.g. *'Create a photorealistic cyberpunk street scene in 16:9, then upscale 2x'* or *'Animate this picture'*), and I will formulate a transparent, human-in-the-loop action plan for your review.",
      created_at: new Date().toISOString(),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [executingProposalId, setExecutingProposalId] = useState<string | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const nodes = useCanvasStore((s) => s.nodes);
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedAssetId = selectedNode?.data?.assetId as string | undefined;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  if (!isOpen) return null;

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText.trim();
    if (!text || isLoading) return;

    const userMessage: AgentChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    if (!textToSend) setInputText('');
    setIsLoading(true);
    setExecutionError(null);

    try {
      const resp = await fetch('/api/v1/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          selected_asset_id: selectedAssetId,
        }),
      });

      if (!resp.ok) {
        throw new Error(`Agent error: HTTP ${resp.status}`);
      }

      const data = await resp.json();
      setMessages((prev) => [...prev, data.message]);
    } catch (err: any) {
      const errorMessage: AgentChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, I encountered an error: ${err.message || 'Unable to connect to Agent service'}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApproveAndRun = async (proposal: AgentProposal) => {
    setExecutingProposalId(proposal.id);
    setExecutionError(null);

    try {
      // Mark approved as required by the human-in-the-loop gate
      const approvedProposal = {
        ...proposal,
        approved: true,
      };

      const resp = await fetch('/api/v1/agent/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposal_id: proposal.id,
          proposal: approvedProposal,
        }),
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || `Execution failed with HTTP ${resp.status}`);
      }

      const results: CreativeActionResult[] = await resp.json();

      // Add resulting nodes to the canvas
      for (const res of results) {
        if (res.success && (res.image_url || res.video_url)) {
          const canvasStore = useCanvasStore.getState();
          const existingNodes = canvasStore.nodes;
          const xOffset = 100 + (existingNodes.length % 5) * 360;
          const yOffset = 100 + Math.floor(existingNodes.length / 5) * 420;

          const isVideo = Boolean(res.video_url || proposal.intent.includes('video'));
          const cardId = `${isVideo ? 'video' : 'image'}_agent_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;

          const cardData: ImageCardData = {
            assetId: res.asset_id,
            imageUrl: res.image_url || res.video_url || '',
            videoUrl: res.video_url,
            mediaType: isVideo ? 'video' : 'image',
            width: res.width,
            height: res.height,
            provenance: res.provenance,
            label: res.provenance?.prompt || proposal.title,
          };

          const newCardNode = {
            id: cardId,
            type: 'imageCard',
            position: { x: xOffset, y: yOffset },
            data: cardData as any,
          };

          useCanvasStore.setState({
            nodes: [...existingNodes, newCardNode],
            selectedNodeId: cardId,
          });
        }
      }

      // Append assistant completion message
      const completeMessage: AgentChatMessage = {
        id: `done-${Date.now()}`,
        role: 'assistant',
        content: `Action plan **${proposal.title}** executed successfully! The generated asset(s) have been placed on your creative canvas.`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, completeMessage]);
    } catch (err: any) {
      setExecutionError(err.message || 'Execution failed');
    } finally {
      setExecutingProposalId(null);
    }
  };

  const quickPrompts = [
    'Photorealistic cyberpunk street in 16:9',
    'Generate an anime landscape then upscale 2x',
    selectedAssetId ? 'Animate this image with smooth motion' : 'Video clip of ocean waves crashing',
    'What models do I have?',
  ];

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-slate-900 border-l border-slate-800 shadow-2xl text-slate-100">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950/60">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Creative Assistant</h2>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Human-in-the-Loop Active</span>
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Selected canvas context indicator */}
      {selectedAssetId && (
        <div className="flex items-center justify-between bg-indigo-950/40 border-b border-indigo-900/40 px-4 py-1.5 text-xs text-indigo-300">
          <div className="flex items-center gap-1.5 truncate">
            <ImageIcon className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
            <span className="truncate">Context: Active canvas asset selected</span>
          </div>
        </div>
      )}

      {/* Message History */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-[90%] rounded-xl px-3.5 py-2.5 text-sm ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-none shadow-md'
                  : 'bg-slate-800 text-slate-200 rounded-bl-none border border-slate-700/60'
              }`}
            >
              <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

              {/* Structured Transparent Proposal Card */}
              {msg.proposal && (
                <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/80 p-3 text-xs text-slate-300 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="font-semibold text-slate-100 flex items-center gap-1.5">
                      <Zap className="h-3.5 w-3.5 text-indigo-400" />
                      {msg.proposal.title}
                    </span>
                    <span className="rounded bg-indigo-900/60 border border-indigo-700/60 px-1.5 py-0.5 text-[10px] font-medium text-indigo-300 uppercase">
                      {msg.proposal.intent}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-slate-400">
                    <div>
                      <span className="text-slate-500 block text-[10px]">Engine:</span>
                      <span className="text-slate-200 font-mono text-[11px] truncate block">
                        {msg.proposal.target_engine}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">Model:</span>
                      <span className="text-slate-200 font-mono text-[11px] truncate block">
                        {msg.proposal.model}
                      </span>
                    </div>
                  </div>

                  {/* Multi-step pipeline if compound */}
                  {msg.proposal.chain_steps.length > 1 && (
                    <div className="rounded bg-slate-950/60 p-2 border border-slate-800 space-y-1">
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Execution Pipeline ({msg.proposal.chain_steps.length} Steps)
                      </span>
                      {msg.proposal.chain_steps.map((st) => (
                        <div key={st.step_number} className="flex items-center gap-1.5 text-slate-300 text-[11px]">
                          <span className="h-4 w-4 rounded-full bg-slate-800 text-[9px] flex items-center justify-center font-bold text-indigo-400">
                            {st.step_number}
                          </span>
                          <span className="font-medium text-indigo-300">{st.action}</span>
                          <span className="text-slate-500">- {st.description}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Transparent Cost / Privacy Notice */}
                  <div className="flex items-center gap-1.5 rounded bg-emerald-950/30 border border-emerald-800/40 p-1.5 text-[11px] text-emerald-400">
                    <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
                    <span>{msg.proposal.cost_disclaimer}</span>
                  </div>

                  {/* Human-in-the-Loop Action Gate */}
                  <div className="pt-1 flex items-center gap-2">
                    <button
                      onClick={() => handleApproveAndRun(msg.proposal!)}
                      disabled={executingProposalId === msg.proposal.id}
                      className="flex-1 flex items-center justify-center gap-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-white transition-colors shadow-sm"
                    >
                      {executingProposalId === msg.proposal.id ? (
                        <>
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          <span>Executing Plan...</span>
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5 fill-current" />
                          <span>Approve & Run</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
            <span className="mt-1 text-[10px] text-slate-500 px-1">
              {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-indigo-400 bg-slate-800/60 rounded-lg p-2.5 w-fit border border-slate-700/50">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            <span>Formulating transparent action plan...</span>
          </div>
        )}

        {executionError && (
          <div className="flex items-center gap-2 text-xs text-red-400 bg-red-950/40 rounded-lg p-2.5 border border-red-800/50">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{executionError}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts */}
      <div className="px-4 py-2 border-t border-slate-800/60 bg-slate-950/30">
        <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
          {quickPrompts.map((qp, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(qp)}
              disabled={isLoading}
              className="whitespace-nowrap rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-700/60 px-2.5 py-1 text-[11px] text-slate-300 transition-colors"
            >
              {qp}
            </button>
          ))}
        </div>
      </div>

      {/* Input Box */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/80">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={
              selectedAssetId
                ? 'Ask about selected image (e.g. animate, upscale, modify)...'
                : 'Describe what you want to create...'
            }
            disabled={isLoading}
            className="flex-1 rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputText.trim() || isLoading}
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white transition-colors shrink-0"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
