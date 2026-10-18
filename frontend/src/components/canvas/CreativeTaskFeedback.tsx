import { Loader2 } from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { useUiText } from '../../i18n/useUiText';
import { useCreativeStore } from '../../stores/useCreativeStore';

type CreativeTaskStatusProps = Pick<ReturnType<typeof useCreativeStore.getState>,
  'isGenerating' | 'generationNotice' | 'generationStage' | 'activeTaskId' | 'cancellationRequested' | 'cancelGeneration'>;

export const CreativeTaskStatus = ({ isGenerating, generationNotice, generationStage, activeTaskId, cancellationRequested, cancelGeneration }: CreativeTaskStatusProps) => {
  const ui = useUiText();
  return (
  <>
    {generationNotice && <p role="status" className="px-3 text-xs text-amber-200">{generationNotice}</p>}
    {isGenerating && (
      <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-indigo-950/50 border border-indigo-800/60 text-xs">
        <div className="flex items-center gap-2.5">
          <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
          <div className="flex flex-col">
            <span className="font-medium text-indigo-200">{generationStage || ui("ui_running")}</span>
            <span className="text-[10px] text-slate-400">{activeTaskId || ui("ui_waiting_for_task_admission")}</span>
          </div>
        </div>
        <button type="button" onClick={() => void cancelGeneration()} disabled={!activeTaskId || cancellationRequested}
          className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-200 disabled:opacity-50">
          {cancellationRequested ? ui("ui_cancellation_requested") : ui("ui_cancel")}
        </button>
      </div>
    )}
  </>
);
};


export function CreativeTaskFeedback() {
  const ui = useUiText();
  const state = useCreativeStore(useShallow((store) => ({
    error: store.error, isGenerating: store.isGenerating, generationNotice: store.generationNotice,
    generationStage: store.generationStage, activeTaskId: store.activeTaskId,
    cancellationRequested: store.cancellationRequested, cancelGeneration: store.cancelGeneration,
  })));
  return <div className="space-y-2">
    {state.error && <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-rose-800 bg-rose-950/60 px-3 py-2 text-sm text-rose-200">
      <p>{state.error}</p>
      <button type="button" onClick={() => useCreativeStore.setState({ error: null })}
        className="shrink-0 rounded border border-rose-700 px-2 py-1">{ui('ui_dismiss')}</button>
    </div>}
    <CreativeTaskStatus {...state} />
  </div>;
}
