import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';
import { CheckCircle2, Download, Loader2, Minus, X } from 'lucide-react';
import { useUiText, type UiMessageKey } from '../../i18n/useUiText';
import { LANGUAGE_OPTIONS, resolveEffectiveLanguage } from '../../i18n/translations';
import { useSettingsStore } from '../../stores/useSettingsStore';

interface Status { phase: string; details: string; environment_path: string; can_install: boolean; error_code?: string; volume?: string; available_bytes?: number | null; required_bytes?: number | null }
interface Environment { path: string; version: string | null; ready: boolean; reason: string; missing: string[] }
const stages: Record<string, UiMessageKey> = {
  downloading: 'setupDownloading', verifying: 'setupVerifying', installing: 'setupInstalling',
  validating: 'setupValidating', starting: 'setupStarting', ready: 'setupReady',
};
const failureMessages: Record<string, UiMessageKey> = {
  network: 'setupErrorNetwork', proxy: 'setupErrorProxy', proxy_configuration: 'setupErrorProxyConfiguration',
  disk_space: 'setupErrorDiskSpace', permission: 'setupErrorPermission', checksum: 'setupErrorChecksum',
  dependencies: 'setupErrorDependencies', validation: 'setupErrorDependencies', storage: 'setupErrorStorage', service: 'setupErrorService',
};
const button = 'rounded-xl px-5 py-3 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400';

/** This page is bundled with the desktop app and works before Python is available. */
export function StartupScreen() {
  const t = useUiText();
  const language = useSettingsStore((state) => state.language);
  const setLanguage = useSettingsStore((state) => state.setLanguage);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [selected, setSelected] = useState('');
  const [searched, setSearched] = useState(false);
  const [notice, setNotice] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const cancelRequested = useRef(false);
  const current = environments.find((item) => item.path === selected);

  useEffect(() => { document.documentElement.lang = resolveEffectiveLanguage(language); }, [language]);

  useEffect(() => {
    let disposed = false;
    const refresh = () => void invoke<Status>('startup_status').then((value) => {
      if (!disposed) setStatus(value);
    }).catch(() => { if (!disposed) setNotice(true); });
    refresh();
    const timer = window.setInterval(refresh, 750);
    return () => { disposed = true; window.clearInterval(timer); };
  }, []);

  const prepare = async (action: 'install' | 'existing' | 'retry') => {
    cancelRequested.current = false;
    setBusy(true); setNotice(false); setCancelling(false);
    try {
      await invoke('prepare_environment', { action, path: action === 'existing' ? selected : null, language });
    } catch { if (!cancelRequested.current) setNotice(true); }
    finally { setBusy(false); setCancelling(false); }
  };
  const discover = async () => {
    setDiscovering(true); setNotice(false);
    try { setEnvironments(await invoke<Environment[]>('discover_environments')); setSearched(true); setSelected(''); }
    catch { setNotice(true); }
    finally { setDiscovering(false); }
  };
  const browse = async () => {
    try {
      const path = await open({ multiple: false, directory: false, title: t('setupChoosePython') });
      if (typeof path !== 'string') return;
      setDiscovering(true);
      const value = await invoke<Environment>('inspect_environment', { path });
      setEnvironments((items) => [...items.filter((item) => item.path !== value.path), value]);
      setSelected(value.path);
    } catch { setNotice(true); }
    finally { setDiscovering(false); }
  };
  const cancel = async () => {
    cancelRequested.current = true;
    setCancelling(true);
    try { await invoke('cancel_environment_setup'); }
    catch { setNotice(true); setCancelling(false); }
  };
  const failed = status?.phase === 'failed';
  const cancelled = status?.phase === 'cancelled';
  const formatSpace = (bytes: number | null | undefined) => bytes == null ? '—'
    : new Intl.NumberFormat(resolveEffectiveLanguage(language), { maximumFractionDigits: 2 }).format(bytes / 1024 ** 3);
  const failure = t(failed ? failureMessages[status?.error_code ?? ''] ?? 'setupFailed' : 'setupFailed', {
    volume: status?.volume || status?.environment_path || '—',
    available: formatSpace(status?.available_bytes), required: formatSpace(status?.required_bytes),
  });

  return <div className="flex h-full flex-col bg-slate-950 text-slate-100">
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 pl-5" data-tauri-drag-region>
      <span className="text-sm font-semibold" data-tauri-drag-region>{t('ui_berry_ai_studio')}</span>
      <div className="flex">
        <button className="p-4 hover:bg-slate-800" aria-label={t('setupMinimize')} onClick={() => void invoke('minimize_app').catch(() => setNotice(true))}><Minus size={16} /></button>
        <button className="p-4 hover:bg-red-600" aria-label={t('setupExit')} onClick={() => void invoke('close_app').catch(() => setNotice(true))}><X size={16} /></button>
      </div>
    </header>
    <main className="flex-1 overflow-y-auto px-6 py-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex justify-end">
          <label className="flex items-center gap-3 text-sm text-slate-400">{t('setupLanguage')}
            <select aria-label={t('setupLanguage')} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100" value={language} onChange={(event) => {
              const value = event.target.value;
              const option = LANGUAGE_OPTIONS.find((item) => item.id === value);
              if (option) setLanguage(option.id);
            }}>
              {LANGUAGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.id === 'system' ? t('setupSystemLanguage') : option.nativeLabel}</option>)}
            </select>
          </label>
        </div>
        <section className="rounded-3xl border border-slate-700 bg-slate-900 p-8 shadow-xl">
          <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/15 text-violet-300"><Download size={25} /></div>
          <h1 className="text-2xl font-semibold">{t('setupTitle')}</h1>
          <p className="mt-3 leading-7 text-slate-400">{t('setupIntro')}</p>
          <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-800/50 p-5">
            <div className="flex items-center justify-between gap-3"><h2 className="font-medium">{t('setupBasic')}</h2><span className="rounded-full bg-violet-500/15 px-3 py-1 text-xs text-violet-300">{t('setupRequired')}</span></div>
            <p className="mt-2 text-sm leading-6 text-slate-400">{t('setupIsolation')}</p>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-400">{t('setupOptional')}</p>
          <div className="mt-6" role="status" aria-live="polite">
            {busy && <p className="flex items-center gap-3 text-violet-300"><Loader2 size={18} className="animate-spin" />{cancelling ? t('setupCancelling') : t(stages[status?.phase ?? ''] ?? 'setupValidating')}</p>}
            {!busy && (notice || failed) && <p className="text-amber-300">{failure}</p>}
            {!busy && cancelled && <p className="text-slate-300">{t('setupCancelled')}</p>}
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            {busy ? <button className={`${button} bg-slate-700 hover:bg-slate-600`} disabled={cancelling} onClick={() => void cancel()}>{t('setupCancel')}</button> : <>
              <button className={`${button} bg-violet-600 hover:bg-violet-500`} disabled={!status?.can_install || discovering} onClick={() => void prepare('install')}>{t(failed || cancelled ? 'setupRetryInstall' : 'setupInstall')}</button>
              <button className={`${button} bg-slate-800 hover:bg-slate-700`} disabled={!status || discovering} onClick={() => void prepare('retry')}>{t('setupRetryStartup')}</button>
            </>}
          </div>
          {status && !status.can_install && <p className="mt-3 text-sm text-amber-300">{t('setupUnsupported')}</p>}
          <details className="mt-7 border-t border-slate-700 pt-5">
            <summary className="cursor-pointer text-sm text-slate-300">{t('setupExisting')}</summary>
            <p className="my-4 text-sm leading-6 text-slate-400">{t('setupExistingHelp')}</p>
            <div className="flex flex-wrap gap-3">
              <button className={`${button} bg-slate-800 hover:bg-slate-700`} disabled={busy || discovering} onClick={() => void discover()}>{t(discovering ? 'setupDetecting' : 'setupDetect')}</button>
              <button className={`${button} bg-slate-800 hover:bg-slate-700`} disabled={busy || discovering} onClick={() => void browse()}>{t('setupBrowse')}</button>
            </div>
            {searched && !discovering && environments.length === 0 && <p className="mt-3 text-sm text-slate-400" role="status">{t('setupNotFound')}</p>}
            {environments.length > 0 && <label className="mt-4 block text-sm text-slate-300">{t('setupChoosePython')}
              <select className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 p-3" value={selected} disabled={busy || discovering} onChange={(event) => setSelected(event.target.value)}>
                <option value="">{t('setupSelect')}</option>
                {environments.map((item) => <option key={item.path} value={item.path}>{t('setupPythonVersion', { version: item.version ?? '—', path: item.path })}</option>)}
              </select>
            </label>}
            {current && <p className={`mt-3 flex items-start gap-2 text-sm ${current.ready ? 'text-emerald-300' : 'text-amber-300'}`}>
              {current.ready && <CheckCircle2 size={18} className="shrink-0" />}{t(current.ready ? 'setupCompatible' : current.reason === 'version' ? 'setupVersion' : current.reason === 'invalid' ? 'setupInvalid' : 'setupDependencies')}
            </p>}
            <button className={`${button} mt-4 bg-slate-700 hover:bg-slate-600`} disabled={!current?.ready || busy || discovering} onClick={() => void prepare('existing')}>{t('setupUseExisting')}</button>
          </details>
          <details className="mt-5 text-xs text-slate-500">
            <summary className="cursor-pointer">{t('setupDetails')}</summary>
            <p className="mt-2 break-all">{t('setupLocation')}: {status?.environment_path || '—'}</p>
            {status?.details && <pre className="mt-2 select-text whitespace-pre-wrap break-words">{status.details}</pre>}
          </details>
        </section>
      </div>
    </main>
  </div>;
}
