import { useEffect, useState } from 'react';
import { CheckCircle2, Cloud, ExternalLink, Key, Loader2, ShieldCheck, Trash2, X, XCircle } from 'lucide-react';

interface CloudProviderInfo {
  id: string;
  name: string;
  description: string;
  is_configured: boolean;
  redacted_key?: string;
  supported_models: string[];
  capabilities: string[];
  upload_disclosure: string;
  website_url: string;
}

interface CloudSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CloudSettingsModal = ({ isOpen, onClose }: CloudSettingsModalProps) => {
  const [providers, setProviders] = useState<CloudProviderInfo[]>([]);
  const [inputKeys, setInputKeys] = useState<Record<string, string>>({});
  const [testResults, setTestResults] = useState<Record<string, { loading: boolean; valid?: boolean; message?: string }>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  const fetchProviders = async () => {
    try {
      const res = await fetch('/api/v1/cloud/providers');
      if (res.ok) {
        const data = await res.json();
        setProviders(data);
      }
    } catch {
      // ignore fetch error
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchProviders();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSaveKey = async (providerId: string) => {
    const key = inputKeys[providerId];
    if (!key || !key.trim()) return;

    setSavingId(providerId);
    try {
      const res = await fetch('/api/v1/cloud/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_id: providerId, api_key: key.trim() }),
      });
      if (res.ok) {
        setInputKeys((prev) => ({ ...prev, [providerId]: '' }));
        await fetchProviders();
      }
    } finally {
      setSavingId(null);
    }
  };

  const handleDeleteKey = async (providerId: string) => {
    try {
      await fetch(`/api/v1/cloud/credentials/${providerId}`, { method: 'DELETE' });
      await fetchProviders();
      setTestResults((prev) => {
        const next = { ...prev };
        delete next[providerId];
        return next;
      });
    } catch {
      // ignore
    }
  };

  const handleTestKey = async (providerId: string) => {
    setTestResults((prev) => ({
      ...prev,
      [providerId]: { loading: true },
    }));

    const inlineKey = inputKeys[providerId];
    const payload = inlineKey?.trim()
      ? { provider_id: providerId, api_key: inlineKey.trim() }
      : { provider_id: providerId };

    try {
      const res = await fetch('/api/v1/cloud/credentials/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setTestResults((prev) => ({
        ...prev,
        [providerId]: {
          loading: false,
          valid: data.valid,
          message: data.message,
        },
      }));
    } catch (err: any) {
      setTestResults((prev) => ({
        ...prev,
        [providerId]: {
          loading: false,
          valid: false,
          message: err.message || 'Connection test failed',
        },
      }));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <Cloud className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-semibold text-sm text-slate-100">BYOK Cloud Providers</h2>
              <p className="text-[11px] text-slate-400">Bring Your Own Key for cloud creation with zero local GPU required</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Security & Privacy Notice */}
        <div className="px-6 py-2.5 bg-indigo-950/30 border-b border-indigo-900/30 flex items-center gap-2 text-xs text-indigo-300">
          <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0" />
          <span>Keys are stored in your protected local application data and never committed to workflows or logs.</span>
        </div>

        {/* Providers List */}
        <div className="p-6 overflow-y-auto flex flex-col gap-4">
          {providers.map((p) => {
            const test = testResults[p.id];
            return (
              <div
                key={p.id}
                className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col gap-3 transition hover:border-slate-700"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-slate-200">{p.name}</span>
                      {p.is_configured ? (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/50 text-[10px] font-medium">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Configured ({p.redacted_key})</span>
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 text-[10px]">
                          Not Configured
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{p.description}</p>
                  </div>

                  <a
                    href={p.website_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 transition"
                  >
                    <span>Get Key</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>

                {/* Capabilities & Upload Disclosure */}
                <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                  <span className="text-slate-400">Models: {p.supported_models.join(', ')}</span>
                  <span>•</span>
                  <span>{p.upload_disclosure}</span>
                </div>

                {/* API Key Input & Action Controls */}
                <div className="flex items-center gap-2 pt-1">
                  <div className="relative flex-1">
                    <Key className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="password"
                      value={inputKeys[p.id] || ''}
                      onChange={(e) =>
                        setInputKeys((prev) => ({ ...prev, [p.id]: e.target.value }))
                      }
                      placeholder={p.is_configured ? `Enter new key to replace ${p.redacted_key}` : "Enter API key (e.g. sk-...)"}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  {inputKeys[p.id] && (
                    <button
                      onClick={() => handleSaveKey(p.id)}
                      disabled={savingId === p.id}
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition"
                    >
                      {savingId === p.id ? 'Saving...' : 'Save'}
                    </button>
                  )}

                  <button
                    onClick={() => handleTestKey(p.id)}
                    disabled={(!p.is_configured && !inputKeys[p.id]) || test?.loading}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5 whitespace-nowrap"
                  >
                    {test?.loading && <Loader2 className="w-3 h-3 animate-spin text-indigo-400" />}
                    <span>Test Connection</span>
                  </button>

                  {p.is_configured && (
                    <button
                      onClick={() => handleDeleteKey(p.id)}
                      title="Remove key"
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Test Feedback Result */}
                {test && !test.loading && (
                  <div
                    className={`px-3 py-1.5 rounded-lg text-xs flex items-center gap-2 ${
                      test.valid
                        ? 'bg-emerald-950/50 text-emerald-300 border border-emerald-800/40'
                        : 'bg-rose-950/50 text-rose-300 border border-rose-800/40'
                    }`}
                  >
                    {test.valid ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                    <span>{test.message}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-900 border-t border-slate-800 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
