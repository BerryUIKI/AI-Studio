import React, { useEffect, useState, useRef } from 'react';
import { EngineInstance } from '../../stores/useEngineStore';
import { X, RefreshCw, Copy, Check, Terminal } from 'lucide-react';

interface EngineLogViewerProps {
  isOpen: boolean;
  instance: EngineInstance | null;
  onClose: () => void;
}

export const EngineLogViewer: React.FC<EngineLogViewerProps> = ({
  isOpen,
  instance,
  onClose,
}) => {
  const [logs, setLogs] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const logContainerRef = useRef<HTMLDivElement | null>(null);

  const fetchLogs = async () => {
    if (!instance) return;
    setIsLoading(true);
    try {
      const res = await fetch(`/api/v1/runtime/${instance.id}/logs?lines=200`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      } else {
        setLogs([`Failed to fetch logs: ${res.statusText}`]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setLogs([`Error connecting to backend log service: ${msg}`]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && instance) {
      fetchLogs();
      const interval = setInterval(fetchLogs, 4000);
      return () => clearInterval(interval);
    }
  }, [isOpen, instance]);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const handleCopy = () => {
    navigator.clipboard.writeText(logs.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen || !instance) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none">
      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl flex flex-col h-[75vh] max-h-[650px] overflow-hidden text-slate-100">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800 bg-slate-950/40">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span>{instance.name} Logs</span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                  {instance.status}
                </span>
              </h2>
              <p className="text-[11px] text-slate-400 font-mono">
                {instance.endpoint || instance.install_path || 'Managed Runtime'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-1.5">
            <button
              onClick={fetchLogs}
              title="Refresh Logs"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={handleCopy}
              title="Copy all logs"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
            <button
              onClick={onClose}
              title="Close"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Log Viewer Terminal */}
        <div
          ref={logContainerRef}
          className="flex-1 p-4 bg-slate-950 font-mono text-xs overflow-y-auto leading-relaxed text-slate-300 space-y-1 select-text"
        >
          {logs.length === 0 ? (
            <div className="text-slate-500 italic">No output logs recorded yet for this instance.</div>
          ) : (
            logs.map((line, idx) => {
              const isError = line.toLowerCase().includes('error') || line.toLowerCase().includes('exception');
              const isWarning = line.toLowerCase().includes('warn');
              return (
                <div
                  key={idx}
                  className={`break-words ${
                    isError
                      ? 'text-rose-400'
                      : isWarning
                      ? 'text-amber-400'
                      : 'text-slate-300'
                  }`}
                >
                  {line}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-2.5 bg-slate-950/80 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
          <span>Showing latest {logs.length} lines</span>
          <span className="font-mono">Auto-refresh every 4s</span>
        </div>
      </div>
    </div>
  );
};
