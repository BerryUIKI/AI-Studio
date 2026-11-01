import { useEffect, useMemo, useState } from 'react';
import { Bot, Image as ImageIcon, KeyRound, Loader2, Plus, Search, Terminal, Trash2, X } from 'lucide-react';
import { useUiText } from '../../i18n/useUiText';
import { customProviders, type CustomProviderRecord } from '../../api/customProviders';
import { presetsFor, type ProviderKind, type ProviderPreset } from './providerCatalog';

type Category = 'official' | 'third-party' | 'local' | 'custom';

const categoryOf = (preset: ProviderPreset): Category => {
  if (preset.baseUrl.startsWith('http://127.0.0.1') || preset.baseUrl.startsWith('http://localhost')) return 'local';
  return 'official';
};

const CATEGORY_ORDER: Category[] = ['official', 'third-party', 'local', 'custom'];

interface LlmConfig {
  provider: string;
  model: string;
  base_url: string;
  api_key?: string;
  temperature?: number;
  enabled: boolean;
}

interface CustomProviderInfo {
  id: string;
  name: string;
  description: string;
  is_configured: boolean;
  redacted_key?: string;
  supported_models: string[];
  capabilities: string[];
  upload_disclosure: string;
  website_url: string;
  key_test_supported?: boolean;
}

export function ProviderRegistry() {
  const ui = useUiText();
  const [kind, setKind] = useState<ProviderKind>('llm');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<Category | 'all'>('all');
  const [catalog, setCatalog] = useState<{ llm: LlmConfig | null; image: CustomProviderInfo[] }>({ llm: null, image: [] });
  const [custom, setCustom] = useState<CustomProviderRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<ProviderPreset | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [notice, setNotice] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const [llmRes, imageRes, customRes] = await Promise.all([
        fetch('/api/v1/agent/llm/config'),
        fetch('/api/v1/cloud/providers'),
        customProviders.list(),
      ]);
      const llm = llmRes.ok ? (await llmRes.json()) as LlmConfig : null;
      const image = imageRes.ok
        ? ((await imageRes.json()) as CustomProviderInfo[]).filter((provider) =>
            provider.capabilities.some((action) => ['txt2img', 'img2img', 'inpaint', 'upscale'].includes(action)))
        : [];
      setCatalog({ llm, image });
      setCustom(customRes);
    } catch {
      setNotice(ui('ui_provider_load_failed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const presets = useMemo(() => {
    const base = presetsFor(kind);
    const needle = query.trim().toLowerCase();
    return base.filter((preset) => {
      if (category !== 'all' && categoryOf(preset) !== category) return false;
      if (!needle) return true;
      return `${preset.name} ${preset.host} ${preset.models.join(' ')}`.toLowerCase().includes(needle);
    });
  }, [kind, query, category]);

  const configured = (preset: ProviderPreset) =>
    kind === 'llm'
      ? catalog.llm?.provider === preset.id && Boolean(catalog.llm?.base_url)
      : catalog.image.some((item) => item.id === preset.id && item.is_configured);

  const customForKind = custom.filter((record) =>
    kind === 'image' ? record.spec.actions.length > 0 : record.spec.actions.length === 0);

  return (
    <section aria-label={ui('ui_provider_console')} className="flex w-full h-full flex-col bg-slate-950 text-slate-100 overflow-hidden">
      <div className="flex min-h-0 flex-1">
        <aside className="w-56 shrink-0 border-r border-white/[0.08] p-3">
          <p className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{ui('ui_provider_kind')}</p>
          {([
            { id: 'llm' as const, label: ui('ui_provider_kind_llm'), icon: Bot },
            { id: 'image' as const, label: ui('ui_provider_kind_image'), icon: ImageIcon },
          ]).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => { setKind(item.id); setEditing(null); }}
              aria-pressed={kind === item.id}
              className={`mb-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition ${kind === item.id ? 'bg-indigo-600/15 text-indigo-200' : 'text-slate-300 hover:bg-slate-900'}`}
            >
              <item.icon className="h-4 w-4" />
              <span className="truncate">{item.label}</span>
            </button>
          ))}
          <button
            type="button"
            disabled
            title={ui('ui_provider_kind_cli_soon')}
            className="mb-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-slate-600"
          >
            <Terminal className="h-4 w-4" />
            <span className="truncate">{ui('ui_provider_kind_cli')}</span>
          </button>

          <p className="px-2 pb-2 pt-4 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{ui('ui_provider_source')}</p>
          {(['all', ...CATEGORY_ORDER] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setCategory(item)}
              aria-pressed={category === item}
              className={`mb-1 flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition ${category === item ? 'bg-slate-800 text-slate-100' : 'text-slate-400 hover:bg-slate-900'}`}
            >
              <span>{ui(`ui_provider_source_${item}` as never)}</span>
            </button>
          ))}
        </aside>

        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex items-center gap-2 border-b border-white/[0.08] px-6 py-3">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                aria-label={ui('ui_provider_search')}
                placeholder={ui('ui_provider_search')}
                className="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-slate-200 placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <button
              type="button"
              onClick={() => setEditing({ id: 'custom', kind, name: '', host: '', baseUrl: '', models: [], actions: [], badge: '+' })}
              className="flex shrink-0 items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
            >
              <Plus className="h-3.5 w-3.5" />
              {ui('ui_provider_add_custom')}
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                {ui('ui_provider_loading')}
              </div>
            ) : (
              <div className="flex flex-col gap-6">
                <div>
                  <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    {ui(kind === 'llm' ? 'ui_provider_section_llm' : 'ui_provider_section_image')}
                  </h3>
                  <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                    {presets.map((preset) => (
                      <div key={preset.id} className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-3 transition hover:border-slate-700">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-950 text-sm font-semibold text-slate-300">
                          {preset.badge}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate text-xs font-semibold text-slate-200">{preset.name}</span>
                            {configured(preset) && (
                              <span aria-label={ui('ui_provider_configured')} className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                            )}
                          </div>
                          <p className="truncate text-[11px] text-slate-500">{preset.host}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setEditing(preset)}
                          className="shrink-0 rounded-lg border border-slate-700 px-2.5 py-1.5 text-[11px] text-slate-300 hover:bg-slate-800"
                        >
                          {ui('ui_provider_configure')}
                        </button>
                      </div>
                    ))}
                    {presets.length === 0 && <p className="text-xs text-slate-500">{ui('ui_provider_no_match')}</p>}
                  </div>
                </div>

                {customForKind.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{ui('ui_provider_section_custom')}</h3>
                    <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                      {customForKind.map((record) => (
                        <div key={record.spec.id} className="flex items-center gap-3 rounded-xl border border-indigo-800/40 bg-slate-900/40 p-3">
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-indigo-700/50 bg-slate-950 text-sm font-semibold text-indigo-300">
                            {(record.spec.name || record.spec.id).slice(0, 1).toUpperCase()}
                          </span>
                          <div className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-semibold text-slate-200">{record.spec.name || record.spec.id}</span>
                            <p className="truncate text-[11px] text-slate-500">{record.spec.endpoint}</p>
                          </div>
                          <button
                            type="button"
                            onClick={async () => {
                              setNotice('');
                              try { await customProviders.remove(record.spec.id); await load(); }
                              catch { setNotice(ui('ui_provider_remove_failed')); }
                            }}
                            aria-label={ui('ui_provider_remove_custom')}
                            className="shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-slate-800 hover:text-rose-400"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-4">
                  <div className="flex items-start gap-2">
                    <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                    <p className="text-[11px] leading-relaxed text-slate-400">{ui('ui_provider_storage_notice')}</p>
                  </div>
                </div>

                {notice && <p role="status" className="text-xs text-indigo-200">{notice}</p>}
              </div>
            )}
          </div>
        </div>
      </div>

      {editing && (
        <ProviderEditor
          kind={kind}
          preset={editing}
          current={catalog.llm}
          onClose={() => setEditing(null)}
          onSaved={async (message) => { setEditing(null); setNotice(message); await load(); }}
          onTesting={setTesting}
          testing={testing}
        />
      )}
    </section>
  );
}

function ProviderEditor({ kind, preset, current, onClose, onSaved, onTesting, testing }: {
  kind: ProviderKind;
  preset: ProviderPreset;
  current: LlmConfig | null;
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
  onTesting: (id: string | null) => void;
  testing: string | null;
}) {
  const ui = useUiText();
  const isCustom = preset.id === 'custom';
  const [name, setName] = useState(preset.name);
  const [baseUrl, setBaseUrl] = useState(preset.baseUrl);
  const [model, setModel] = useState(preset.models[0] ?? '');
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ valid: boolean; message: string } | null>(null);

  const save = async () => {
    setSaving(true);
    setResult(null);
    try {
      if (kind === 'llm') {
        const response = await fetch('/api/v1/agent/llm/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: isCustom ? 'custom' : preset.id,
            model: model.trim(),
            base_url: baseUrl.trim(),
            api_key: apiKey.trim() || undefined,
            temperature: 0.7,
            enabled: true,
          }),
        });
        if (!response.ok) throw new Error('save failed');
      } else {
        await customProviders.save({
          id: isCustom ? `custom-${Date.now().toString(36)}` : `custom-${preset.id}`,
          name: name.trim() || preset.name,
          endpoint: baseUrl.trim(),
          models: model.trim() ? [model.trim()] : preset.models,
          actions: preset.actions.length ? preset.actions : ['txt2img'],
          mode: 'rest',
          source: '',
          body_template: { model: '{{model}}', prompt: '{{prompt}}', size: '{{width}}x{{height}}', n: 1 },
          result_path: 'data.0.url',
          response_format: 'url',
          auth: 'bearer',
          auth_header: 'Authorization',
          request_timeout: 120,
          worker_timeout: 150,
          max_requests: 4,
          requirements: '',
          sdk_allow_credentials: false,
          upload_disclosure: 'Prompts and selected input images are sent to this user-configured platform.',
        }, false);
      }
      await onSaved(ui('ui_provider_saved'));
    } catch {
      setResult({ valid: false, message: ui('ui_provider_save_failed') });
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    onTesting(preset.id);
    setResult(null);
    try {
      const response = await fetch('/api/v1/agent/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: preset.id, model, base_url: baseUrl, api_key: apiKey || undefined, enabled: true }),
      });
      const data = await response.json() as { valid?: boolean; message?: string };
      setResult({ valid: Boolean(data.valid), message: data.message ?? '' });
    } catch {
      setResult({ valid: false, message: ui('ui_provider_test_failed') });
    } finally {
      onTesting(null);
    }
  };

  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-slate-950/80 p-6 backdrop-blur-sm" role="dialog" aria-label={ui('ui_provider_editor')}>
      <div className="flex max-h-full w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
          <h3 className="text-sm font-semibold text-slate-100">
            {isCustom ? ui('ui_provider_add_custom') : preset.name}
          </h3>
          <button type="button" onClick={onClose} aria-label={ui('ui_close_dialog')} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="flex flex-col gap-3 overflow-y-auto px-5 py-4">
          {isCustom && (
            <label className="flex flex-col gap-1 text-xs text-slate-300">
              {ui('ui_provider_name')}
              <input value={name} onChange={(event) => setName(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100" />
            </label>
          )}
          <label className="flex flex-col gap-1 text-xs text-slate-300">
            {ui('ui_provider_base_url')}
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} spellCheck={false} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-300">
            {ui('ui_provider_model')}
            <input value={model} onChange={(event) => setModel(event.target.value)} spellCheck={false} placeholder={ui('ui_provider_model_placeholder')} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-300">
            {ui('ui_provider_key')}
            <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={current?.api_key || 'sk-…'} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100" />
          </label>
          {result && (
            <p className={`rounded-lg px-3 py-2 text-xs ${result.valid ? 'bg-emerald-950/40 text-emerald-300' : 'bg-rose-950/40 text-rose-300'}`}>
              {result.message}
            </p>
          )}
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-slate-800 px-5 py-3">
          <button type="button" onClick={test} disabled={testing === preset.id} className="flex items-center gap-1.5 rounded-xl border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40">
            {testing === preset.id && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {ui('ui_provider_test')}
          </button>
          <button type="button" onClick={save} disabled={saving || !baseUrl.trim()} className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-40">
            {ui('ui_provider_save')}
          </button>
        </footer>
      </div>
    </div>
  );
}
