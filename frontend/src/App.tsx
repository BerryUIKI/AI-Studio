import { useEffect, useState } from 'react';
import { Activity, Cpu, Sparkles } from 'lucide-react';

interface SystemInfo {
  name: string;
  version: string;
  runners: {
    api: { status: string };
    comfyui: { status: string; installed: boolean };
  };
}

export default function App() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);

  useEffect(() => {
    fetch('/health')
      .then((res) => {
        if (res.ok) setBackendOnline(true);
      })
      .catch(() => setBackendOnline(false));

    fetch('/api/v1/info')
      .then((res) => res.json())
      .then((data) => setInfo(data))
      .catch(() => {});
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100">
      {/* Top Header Bar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/60 backdrop-blur px-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-sm tracking-wide">AI-Workflow</h1>
            <p className="text-[11px] text-slate-400">API-First Creative Canvas</p>
          </div>
        </div>

        {/* Engine Status Indicators */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700">
            <Activity className={`w-3.5 h-3.5 ${backendOnline ? 'text-emerald-400' : 'text-rose-400 animate-pulse'}`} />
            <span className="text-slate-300">Backend: {backendOnline ? 'Online' : 'Connecting...'}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700">
            <Cpu className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-slate-300">
              ComfyUI: {info?.runners?.comfyui?.installed ? 'Ready' : 'Optional (Standby)'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Canvas Workspace Container */}
      <main className="flex-1 relative flex items-center justify-center bg-slate-950">
        <div className="text-center p-8 rounded-xl border border-dashed border-slate-800 max-w-md">
          <Sparkles className="w-10 h-10 text-indigo-400 mx-auto mb-3" />
          <h2 className="text-lg font-medium text-slate-200">Creative Canvas Ready</h2>
          <p className="text-xs text-slate-400 mt-1">
            Universal 5-type node system and dirty-check caching engine initialized.
          </p>
        </div>
      </main>
    </div>
  );
}
