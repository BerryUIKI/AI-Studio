import { useEffect, useRef, useState } from 'react';
import { removeEngine, type EngineRemovalResult } from '../../api/engineLifecycle';
import type { EngineInstance } from '../../stores/useEngineStore';

interface Props {
  instance: EngineInstance;
  onClose: () => void;
  onCompleted: () => void;
}

export function EngineRemovalDialog({ instance, onClose, onCompleted }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EngineRemovalResult | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const done = useRef<HTMLButtonElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  const running = instance.is_managed && instance.status === 'running';

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancel.current?.focus();
    return () => previous?.focus();
  }, []);
  useEffect(() => { if (result) done.current?.focus(); }, [result]);
  useEffect(() => { if (busy) dialog.current?.focus(); }, [busy]);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await removeEngine(instance));
      onCompleted();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The engine action failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !busy) close.current();
    }}>
      <div ref={dialog} tabIndex={-1} role="alertdialog" aria-modal="true" aria-labelledby="engine-removal-title" aria-describedby="engine-removal-description"
        className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 text-slate-100 shadow-2xl"
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === 'Escape' && !busy) close.current();
          if (event.key === 'Tab') {
            const buttons = [...(dialog.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])];
            const first = buttons[0], last = buttons[buttons.length - 1];
            if (!buttons.length) event.preventDefault();
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
          }
        }}>
        <h2 id="engine-removal-title" className="text-lg font-semibold">{instance.is_managed ? 'Uninstall' : 'Remove connection to'} {instance.name}</h2>
        <p id="engine-removal-description" className="mt-3 text-sm text-slate-300">
          {instance.is_managed
            ? 'The isolated Python environment will be removed. The entire engine folder will be moved to a retained backup, preserving models, outputs, custom nodes and settings. Shared models and application data stay in place. Reinstallation creates a fresh engine; retained files can be recovered from the backup.'
            : 'This removes the saved connection. The external engine, its process and all its files stay in place.'}
        </p>
        {running && <p role="alert" className="mt-3 text-sm text-amber-300">Stop this managed engine before uninstalling it.</p>}
        {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
        {result && <div role="status" className="mt-3 space-y-2 text-sm text-emerald-300">
          <p>{instance.is_managed ? 'Managed installation removed.' : 'Connection removed.'}</p>
          {result.retained_path && <p className="break-all">Retained backup: {result.retained_path}</p>}
          {result.warning && <p className="text-amber-300">{result.warning}</p>}
        </div>}
        <div className="mt-5 flex justify-end gap-3">
          {result ? <button ref={done} onClick={onClose} className="rounded-lg bg-slate-700 px-4 py-2 text-sm">Done</button> : <>
            <button ref={cancel} disabled={busy} onClick={onClose} className="rounded-lg bg-slate-700 px-4 py-2 text-sm disabled:opacity-50">Cancel</button>
            <button disabled={busy || running} onClick={() => void confirm()} className="rounded-lg bg-red-700 px-4 py-2 text-sm disabled:opacity-50">
              {busy ? 'Working…' : instance.is_managed ? 'Uninstall and retain files' : 'Remove connection'}
            </button>
          </>}
        </div>
      </div>
    </div>
  );
}
