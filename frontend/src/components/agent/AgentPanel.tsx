import { useUiText } from '../../i18n/useUiText';
import { mediaCardFields } from '../../utils/media';
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
  Layers,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  PanelRightClose,
} from 'lucide-react';
import { AgentChatMessage, AgentProposal, CreativeActionResult, ImageCardData } from '../../types/creative';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { useProjectStore } from '../../stores/useProjectStore';
import { useAgentStore } from '../../stores/useAgentStore';
import { nextResultPosition } from '../../utils/canvasPlacement';
import { formatDateTime } from '../../i18n/format';


interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  inline?: boolean;
}

export const AgentPanel: React.FC<AgentPanelProps> = ({ isOpen, onClose, inline = false }) => {
  const ui = useUiText();
  const projectId = useProjectStore((state) => state.currentProject?.id);
  const conversationKey = projectId ?? 'unassigned';
  const conversation = useAgentStore((state) => state.conversations[conversationKey]);
  const messages: AgentChatMessage[] = conversation?.messages.length ? conversation.messages : [
    {
      id: 'welcome-1',
      role: 'assistant',
      content:
        ui("ui_hello_i_am_your_berry_creative_assistant_you"),
      created_at: new Date().toISOString(),
    },
  ];
  const appendMessage = (message: AgentChatMessage) => useAgentStore.getState().append(conversationKey, message);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [executingProposalId, setExecutingProposalId] = useState<string | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [expandedGraphs, setExpandedGraphs] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen || conversation) return;
    const controller = new AbortController();
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    void fetch(`/api/v1/agent/conversation${query}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(ui("ui_conversation_history_unavailable"));
        const saved: { conversation_id: string; messages: AgentChatMessage[] } | null = await response.json();
        if (saved) useAgentStore.getState().restore(conversationKey, saved.conversation_id, saved.messages);
      }).catch(() => { /* Chat remains available when history cannot be fetched. */ });
    return () => controller.abort();
  }, [isOpen, projectId, conversationKey, conversation]);

  const toggleGraphExpanded = (proposalId: string) => {
    setExpandedGraphs((prev) => ({ ...prev, [proposalId]: !prev[proposalId] }));
  };

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

    appendMessage(userMessage);
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
          conversation_id: conversation?.id,
          project_id: projectId,
        }),
      });

      if (!resp.ok) {
        throw new Error(ui("ui_agent_error_http_value", { value1: resp.status }));
      }

      const data: { conversation_id: string; message: AgentChatMessage } = await resp.json();
      useAgentStore.getState().setIdentity(conversationKey, data.conversation_id);
      appendMessage(data.message);
    } catch (err: unknown) {
      const errorMessage: AgentChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: ui("ui_agent_request_failed_value", { value1: err instanceof Error ? err.message : 'Unable to connect to Agent service' }),
        created_at: new Date().toISOString(),
      };
      appendMessage(errorMessage);
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
          project_id: projectId,
        }),
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || ui("ui_execution_failed_with_http_value", { value1: resp.status }));
      }

      const results: CreativeActionResult[] = await resp.json();

      if (results.some((result) => !result.success)) throw new Error(results.find((result) => !result.success)?.error_message || ui("ui_agent_step_failed"));
      if (useProjectStore.getState().currentProject?.id !== projectId) {
        appendMessage({ id: `done-${Date.now()}`, role: 'assistant', content: ui("ui_results_are_saved_in_the_original_project_task"), created_at: new Date().toISOString() });
        return;
      }
      if (results.length <= 1) useCanvasStore.getState().pushSnapshot();
      const frameOrigin = nextResultPosition(useCanvasStore.getState().nodes, selectedAssetId);

      // Automatically group multi-item proposals into a bounded workspace frame (Issue #38)
      if (results.length > 1) {
        const frameWidth = Math.min(1200, results.length * 360 + 60);
        useCanvasStore.getState().addWorkspaceFrame(
          `Agent Plan: ${proposal.title}`,
          frameOrigin,
          { width: frameWidth, height: Math.ceil(results.length / 3) * 440 + 80 }
        );
      }

      // Add resulting nodes to the canvas
      for (let idx = 0; idx < results.length; idx++) {
        const res = results[idx];
        if (res.success && (res.image_url || res.video_url)) {
          const canvasStore = useCanvasStore.getState();
          const existingNodes = canvasStore.nodes;
          const position = results.length > 1
            ? { x: frameOrigin.x + 40 + (idx % 3) * 360, y: frameOrigin.y + 40 + Math.floor(idx / 3) * 440 }
            : nextResultPosition(existingNodes, selectedAssetId);

          const isVideo = Boolean(res.video_url || proposal.intent.includes('video'));
          const cardId = `${isVideo ? 'video' : 'image'}_agent_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;

          const cardData: ImageCardData = {
        ...mediaCardFields(res),
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
            position,
            data: cardData,
          };

          useCanvasStore.setState({
            nodes: [...existingNodes, newCardNode],
            selectedNodeId: cardId,
          });
          canvasStore.notifyCanvasChange();
        }
      }

      // Append assistant completion message
      const completeMessage: AgentChatMessage = {
        id: `done-${Date.now()}`,
        role: 'assistant',
        content: ui("ui_action_plan_value_executed_successfully_the_generated_asset", { value1: proposal.title }),
        created_at: new Date().toISOString(),
      };
      appendMessage(completeMessage);
    } catch (err: unknown) {
      setExecutionError(err instanceof Error ? err.message : ui("ui_execution_failed"));
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
    <div
      className={
        inline
          ? 'flex w-full h-full flex-col bg-slate-900 text-slate-100 overflow-hidden'
          : 'fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-slate-900 border-l border-slate-800 shadow-2xl text-slate-100'
      }
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950/60">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100">{ui("ui_creative_assistant")}</h2>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>{ui("ui_human_in_the_loop_active")}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onClose}
            title={ui("ui_collapse_sidebar")}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
          <button
            onClick={onClose}
            title={ui("ui_close_assistant")}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Selected canvas context indicator */}
      {selectedAssetId && (
        <div className="flex items-center justify-between bg-indigo-950/40 border-b border-indigo-900/40 px-4 py-1.5 text-xs text-indigo-300">
          <div className="flex items-center gap-1.5 truncate">
            <ImageIcon className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
            <span className="truncate">{ui("ui_context_active_canvas_asset_selected")}</span>
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
                      <span className="text-slate-500 block text-[10px]">{ui("ui_engine")}</span>
                      <span className="text-slate-200 font-mono text-[11px] truncate block">
                        {msg.proposal.target_engine}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">{ui("ui_model_2")}</span>
                      <span className="text-slate-200 font-mono text-[11px] truncate block">
                        {msg.proposal.model}
                      </span>
                    </div>
                  </div>

                  {/* Multi-step pipeline if compound */}
                  {msg.proposal.chain_steps.length > 1 && (
                    <div className="rounded bg-slate-950/60 p-2 border border-slate-800 space-y-1">
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                        {ui("ui_execution_pipeline")}{msg.proposal.chain_steps.length} {ui("ui_steps")}</span>
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

                  {/* Bounded ComfyUI Reviewable Graph */}
                  {msg.proposal.workflow_graph && (
                    <div className="rounded bg-slate-950/70 p-2.5 border border-slate-800 space-y-2">
                      <div
                        onClick={() => toggleGraphExpanded(msg.proposal!.id)}
                        className="flex items-center justify-between cursor-pointer select-none"
                      >
                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
                          <Layers className="h-3.5 w-3.5 text-indigo-400" />
                          <span>{ui("ui_comfyui_execution_dag")}{msg.proposal.workflow_graph.node_count} {ui("ui_nodes_2")}{msg.proposal.workflow_graph.stages.length} {ui("ui_stages")}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {msg.proposal.workflow_graph.is_valid ? (
                            <span className="flex items-center gap-1 rounded bg-emerald-950/60 border border-emerald-800/60 px-1.5 py-0.5 text-[10px] text-emerald-400">
                              <CheckCircle2 className="h-3 w-3" /> {ui("ui_validated")}</span>
                          ) : (
                            <span className="flex items-center gap-1 rounded bg-amber-950/60 border border-amber-800/60 px-1.5 py-0.5 text-[10px] text-amber-400">
                              <AlertTriangle className="h-3 w-3" /> {ui("ui_issues")}</span>
                          )}
                          {expandedGraphs[msg.proposal.id] ? (
                            <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
                          )}
                        </div>
                      </div>

                      {/* Notice keeping raw ComfyUI handles off creative canvas */}
                      <p className="text-[10px] text-slate-400">
                        {ui("ui_encapsulated_dag_internal_clip_latent_vae_wiring_stays")}</p>

                      {expandedGraphs[msg.proposal.id] && (
                        <div className="mt-2 space-y-2 pt-2 border-t border-slate-800/80">
                          <div className="space-y-1">
                            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                              {ui("ui_execution_stages")}</span>
                            {msg.proposal.workflow_graph.stages.map((st) => (
                              <div key={st.stage_number} className="flex items-start gap-1.5 text-[11px] text-slate-300">
                                <span className="h-4 w-4 rounded-full bg-slate-800 text-[9px] flex items-center justify-center font-bold text-indigo-400 shrink-0 mt-0.5">
                                  {st.stage_number}
                                </span>
                                <div>
                                  <span className="font-medium text-slate-200">{st.name}</span>
                                  <span className="text-slate-500 font-mono text-[10px] ml-1">({st.node_type})</span>
                                  <p className="text-[10px] text-slate-400">{st.description}</p>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Required Models Checklist */}
                          <div className="space-y-1 pt-1">
                            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                              {ui("ui_required_models")}</span>
                            <div className="flex flex-wrap gap-1">
                              {msg.proposal.workflow_graph.required_models.map((m) => {
                                const isMissing = msg.proposal!.workflow_graph!.missing_models.includes(m);
                                return (
                                  <span
                                    key={m}
                                    className={`rounded px-1.5 py-0.5 text-[10px] font-mono border ${
                                      isMissing
                                        ? 'bg-rose-950/40 border-rose-800/60 text-rose-300'
                                        : 'bg-slate-900 border-slate-800 text-slate-300'
                                    }`}
                                  >
                                    {m} {isMissing ? ui("ui_missing") : ''}
                                  </span>
                                );
                              })}
                            </div>
                          </div>

                          {/* Recovery guidance if issues exist */}
                          {msg.proposal.workflow_graph.recovery_guidance && (
                            <div className="rounded bg-amber-950/40 border border-amber-800/50 p-2 text-[10px] text-amber-300">
                              <span className="font-semibold block mb-0.5">{ui("ui_recovery_guidance")}</span>
                              <span>{msg.proposal.workflow_graph.recovery_guidance}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Transparent Cost / Privacy Notice */}
                  <div className="flex items-center gap-1.5 rounded bg-emerald-950/30 border border-emerald-800/40 p-1.5 text-[11px] text-emerald-400">
                    <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
                    <span>{msg.proposal.cost_disclaimer}</span>
                  </div>

                  {/* Human-in-the-Loop Action Gate */}
                  <div className="pt-1 flex flex-col gap-1.5">
                    {msg.proposal.workflow_graph && !msg.proposal.workflow_graph.is_valid && (
                      <div className="flex flex-col gap-1 text-[11px] text-amber-400 bg-amber-950/30 border border-amber-800/40 rounded p-2">
                        <div className="flex items-center gap-1.5 font-medium">
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                          <span>{ui("ui_local_comfyui_is_not_ready_or_models_are")}</span>
                        </div>
                        <span className="text-[10px] text-amber-300/80">
                          {ui("ui_you_can_switch_this_proposal_to_run_via")}</span>
                        <div className="flex gap-1.5 mt-1">
                          <button
                            onClick={() => handleSendMessage(`Use Fal.ai to generate: ${msg.proposal!.parameters.prompt || msg.proposal!.title}`)}
                            className="rounded bg-indigo-600/80 hover:bg-indigo-600 px-2 py-0.5 text-[10px] font-medium text-white transition-colors"
                          >
                            {ui("ui_switch_to_fal_ai")}</button>
                          <button
                            onClick={() => handleSendMessage(`Use SiliconFlow to generate: ${msg.proposal!.parameters.prompt || msg.proposal!.title}`)}
                            className="rounded bg-indigo-600/80 hover:bg-indigo-600 px-2 py-0.5 text-[10px] font-medium text-white transition-colors"
                          >
                            {ui("ui_switch_to_siliconflow")}</button>
                        </div>
                      </div>
                    )}
                    <button
                      onClick={() => handleApproveAndRun(msg.proposal!)}
                      disabled={executingProposalId === msg.proposal.id || Boolean(msg.proposal.workflow_graph && !msg.proposal.workflow_graph.is_valid)}
                      className="w-full flex items-center justify-center gap-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-400 px-3 py-1.5 text-xs font-semibold text-white transition-colors shadow-sm"
                    >
                      {executingProposalId === msg.proposal.id ? (
                        <>
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          <span>{ui("ui_executing_plan")}</span>
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5 fill-current" />
                          <span>{ui("ui_approve_run")}</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
            <span className="mt-1 text-[10px] text-slate-500 px-1">
              {formatDateTime(msg.created_at, true)}
            </span>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-indigo-400 bg-slate-800/60 rounded-lg p-2.5 w-fit border border-slate-700/50">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            <span>{ui("ui_formulating_transparent_action_plan")}</span>
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
            aria-label={ui("ui_message_to_creative_assistant")}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={
              selectedAssetId
                ? ui("ui_ask_about_selected_image_e_g_animate_upscale")
                : ui("ui_describe_what_you_want_to_create")
            }
            disabled={isLoading}
            className="flex-1 rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
          />
          <button
            type="submit"
            aria-label={ui("ui_send_message")}
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
