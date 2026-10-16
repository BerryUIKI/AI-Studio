import { ReactNode, useEffect, useState } from 'react';
import { AdapterMode, CustomProviderRecord, CustomProviderSpec, ImageAction, Json, STARTER_SOURCE, customProviders, newCustomProvider } from '../../api/customProviders';
import { UiMessageKey, useUiText } from '../../i18n/useUiText';

const control = 'w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100';
const button = 'rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-200 disabled:opacity-40 hover:bg-slate-800';
const actionLabels: Record<ImageAction, UiMessageKey> = { txt2img: 'ui_custom_txt2img', img2img: 'ui_custom_img2img', inpaint: 'ui_custom_inpaint', upscale: 'ui_custom_upscale' };

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="flex min-w-0 flex-col gap-1 text-xs text-slate-300">{label}{children}</label>;
}

function jsonObject(text: string): Record<string, Json> {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected JSON object');
  return value as Record<string, Json>;
}

export function CustomPlatformSettings({ onChanged }: { onChanged: () => Promise<void> }) {
  const ui = useUiText();
  const [records, setRecords] = useState<CustomProviderRecord[]>([]);
  const [spec, setSpec] = useState<CustomProviderSpec | null>(null);
  const [saved, setSaved] = useState<CustomProviderRecord | null>(null);
  const [models, setModels] = useState('');
  const [template, setTemplate] = useState('{}');
  const [sources, setSources] = useState<Partial<Record<AdapterMode, string>>>({});
  const [dirty, setDirty] = useState(false);
  const [approve, setApprove] = useState(false);
  const [pending, setPending] = useState(false);
  const [remove, setRemove] = useState(false);
  const [message, setMessage] = useState('');
  const [fixtureInputs, setFixtureInputs] = useState('{}');
  const [fixtureResponse, setFixtureResponse] = useState('{"data":[{"url":"https://fixture.invalid/image.jpg"}]}');

  useEffect(() => { void customProviders.list().then(setRecords).catch(() => setMessage(ui('ui_custom_failed'))); }, [ui]);

  const open = (record?: CustomProviderRecord) => {
    const value = record?.spec || newCustomProvider();
    setSpec(value); setSaved(record || null); setModels(value.models.join('\n'));
    setTemplate(JSON.stringify(value.body_template, null, 2)); setSources({ [value.mode]: value.source });
    setApprove(false); setDirty(!record); setRemove(false); setMessage('');
  };
  const update = (patch: Partial<CustomProviderSpec>) => {
    setSpec((current) => current ? { ...current, ...patch } : null);
    setDirty(true); setApprove(false); setMessage('');
  };
  const changed = () => { setDirty(true); setApprove(false); setMessage(''); };
  const refresh = async () => { setRecords(await customProviders.list()); await onChanged(); };
  const save = async () => {
    if (!spec) return;
    setPending(true); setMessage('');
    try {
      const value = { ...spec, models: models.split('\n').map((item) => item.trim()).filter(Boolean), body_template: jsonObject(template) };
      if (!value.name.trim() || !value.models.length || !value.actions.length || (!saved && records.some((item) => item.spec.id === spec.id))) throw new Error('Invalid fields');
      const record = await customProviders.save(value, approve);
      setSpec(record.spec); setSaved(record); setDirty(false); setApprove(false);
      await refresh(); setMessage(ui('ui_custom_saved'));
    } catch { setMessage(ui('ui_custom_invalid')); }
    finally { setPending(false); }
  };
  const perform = async (operation: 'fixture' | 'prepare' | 'remove') => {
    if (!saved || dirty) return;
    setPending(true); setMessage('');
    try {
      if (operation === 'fixture') {
        const result = await customProviders.fixture(saved.spec.id, jsonObject(fixtureInputs), JSON.parse(fixtureResponse) as Json);
        setMessage(ui('ui_custom_fixture_passed', { type: result.output.type, count: result.broker_requests }));
      } else if (operation === 'prepare') {
        await customProviders.prepare(saved.spec.id); await refresh(); setMessage(ui('ui_custom_prepared'));
      } else {
        await customProviders.remove(saved.spec.id); setSpec(null); setSaved(null); await refresh();
      }
    } catch { setMessage(ui('ui_custom_failed')); }
    finally { setPending(false); }
  };

  return <section aria-label={ui('ui_custom_platforms')} className="flex flex-col gap-3 rounded-xl border border-indigo-800/50 bg-slate-950 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-sm font-semibold text-slate-100">{ui('ui_custom_platforms')}</h3>
      <button type="button" disabled={pending} className={button} onClick={() => open()}>{ui('ui_custom_add')}</button>
    </div>
    <div className="flex flex-wrap gap-2">{records.map((record) => <button type="button" disabled={pending} key={record.spec.id} className={button} onClick={() => open(record)}>{ui('ui_custom_edit', { name: record.spec.name })}</button>)}</div>
    {spec && <form onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <fieldset disabled={pending} className="flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label={ui('ui_custom_id')}><input className={control} value={spec.id} disabled={Boolean(saved)} onChange={(event) => update({ id: event.target.value })} required pattern="custom-[a-z0-9][a-z0-9-]{0,62}" /></Field>
          <Field label={ui('ui_custom_name')}><input className={control} value={spec.name} maxLength={80} onChange={(event) => update({ name: event.target.value })} required /></Field>
        </div>
        <Field label={ui('ui_custom_endpoint')}><input className={control} value={spec.endpoint} type="url" maxLength={2048} onChange={(event) => update({ endpoint: event.target.value })} required /></Field>
        <Field label={ui('ui_custom_models')}><textarea className={control} rows={3} value={models} onChange={(event) => { setModels(event.target.value); changed(); }} required /></Field>
        <fieldset className="flex flex-wrap gap-3 text-xs text-slate-300"><legend className="mb-1">{ui('ui_custom_actions')}</legend>
          {(Object.keys(actionLabels) as ImageAction[]).map((action) => <label key={action} className="flex items-center gap-1"><input type="checkbox" checked={spec.actions.includes(action)} onChange={(event) => update({ actions: event.target.checked ? [...spec.actions, action] : spec.actions.filter((item) => item !== action) })} />{ui(actionLabels[action])}</label>)}
        </fieldset>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label={ui('ui_custom_mode')}><select className={control} value={spec.mode} onChange={(event) => {
            const mode = event.target.value as AdapterMode;
            setSources((current) => ({ ...current, [spec.mode]: spec.source }));
            update({ mode, source: mode === 'rest' ? '' : sources[mode] ?? STARTER_SOURCE[mode] });
          }}>{(['rest', 'javascript', 'python', 'python_sdk'] as const).map((mode) => <option key={mode} value={mode}>{ui(`ui_custom_${mode}`)}</option>)}</select></Field>
          <Field label={ui('ui_custom_auth')}><select className={control} value={spec.auth} onChange={(event) => update({ auth: event.target.value as CustomProviderSpec['auth'] })}>
            <option value="bearer">{ui('ui_custom_bearer')}</option><option value="header">{ui('ui_custom_header')}</option><option value="none">{ui('ui_custom_no_auth')}</option>
          </select></Field>
        </div>
        {spec.auth === 'header' && <Field label={ui('ui_custom_auth_header')}><input className={control} value={spec.auth_header} onChange={(event) => update({ auth_header: event.target.value })} required /></Field>}
        {spec.mode === 'rest' ? <>
          <p className="text-xs text-slate-400">{ui('ui_custom_template_help')}</p>
          <Field label={ui('ui_custom_body')}><textarea className={`${control} font-mono`} rows={7} value={template} onChange={(event) => { setTemplate(event.target.value); changed(); }} required /></Field>
          <Field label={ui('ui_custom_result_path')}><input className={control} value={spec.result_path} onChange={(event) => update({ result_path: event.target.value })} required /></Field>
          <Field label={ui('ui_custom_response_format')}><select className={control} value={spec.response_format} onChange={(event) => update({ response_format: event.target.value as CustomProviderSpec['response_format'] })}><option value="url">{ui('ui_custom_url')}</option><option value="b64_json">{ui('ui_custom_base64')}</option></select></Field>
        </> : <>
          <p className="text-xs text-amber-200">{ui(spec.mode === 'javascript' ? 'ui_custom_js_privileges' : 'ui_custom_python_privileges')}</p>
          <p className="text-xs text-slate-400">{ui('ui_custom_protocol')}</p>
          <Field label={ui('ui_custom_source')}><textarea className={`${control} font-mono`} rows={10} value={spec.source} spellCheck={false} maxLength={131072} onChange={(event) => update({ source: event.target.value })} required /></Field>
          {spec.mode === 'python_sdk' && <>
            <Field label={ui('ui_custom_requirements')}><textarea className={`${control} font-mono`} rows={4} value={spec.requirements} maxLength={16384} onChange={(event) => update({ requirements: event.target.value })} /></Field>
            <p className="text-xs text-slate-400">{ui('ui_custom_requirements_help')}</p>
            <label className="flex items-start gap-2 text-xs text-amber-200"><input type="checkbox" checked={spec.sdk_allow_credentials} onChange={(event) => update({ sdk_allow_credentials: event.target.checked })} />{ui('ui_custom_sdk_key')}</label>
          </>}
          <label className="flex items-start gap-2 text-xs text-amber-200"><input type="checkbox" checked={approve} onChange={(event) => setApprove(event.target.checked)} />{ui('ui_custom_approve')}</label>
          {saved && <p className="text-xs text-slate-400">{ui(saved.execution_trusted && !dirty ? 'ui_custom_trusted' : 'ui_custom_untrusted')}</p>}
        </>}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label={ui('ui_custom_request_timeout')}><input className={control} type="number" min={1} max={180} value={spec.request_timeout} onChange={(event) => update({ request_timeout: Number(event.target.value) })} required /></Field>
          <Field label={ui('ui_custom_worker_timeout')}><input className={control} type="number" min={1} max={180} value={spec.worker_timeout} onChange={(event) => update({ worker_timeout: Number(event.target.value) })} required /></Field>
          <Field label={ui('ui_custom_max_requests')}><input className={control} type="number" min={1} max={16} value={spec.max_requests} onChange={(event) => update({ max_requests: Number(event.target.value) })} required /></Field>
        </div>
        <Field label={ui('ui_custom_disclosure')}><textarea className={control} rows={2} value={spec.upload_disclosure} maxLength={1000} onChange={(event) => update({ upload_disclosure: event.target.value })} required /></Field>
        <div className="flex flex-wrap gap-2"><button type="submit" className={button}>{ui('ui_custom_save')}</button><button type="button" className={button} onClick={() => setSpec(null)}>{ui('ui_custom_close_editor')}</button></div>
        <p className="text-xs text-slate-400">{ui('ui_custom_fixture_notice')}</p>
        <Field label={ui('ui_custom_fixture_inputs')}><textarea className={`${control} font-mono`} rows={2} value={fixtureInputs} onChange={(event) => setFixtureInputs(event.target.value)} /></Field>
        <Field label={ui('ui_custom_fixture_response')}><textarea className={`${control} font-mono`} rows={3} value={fixtureResponse} onChange={(event) => setFixtureResponse(event.target.value)} /></Field>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={!saved || dirty || spec.mode !== 'rest' && !saved.execution_trusted} className={button} onClick={() => void perform('fixture')}>{ui('ui_custom_fixture')}</button>
          {spec.mode === 'python_sdk' && <button type="button" disabled={!saved?.execution_trusted || dirty} className={button} onClick={() => void perform('prepare')}>{ui('ui_custom_prepare')}</button>}
          {saved && <button type="button" disabled={dirty} className={button} onClick={() => setRemove(true)}>{ui('ui_custom_remove')}</button>}
        </div>
        {remove && <div className="flex flex-col gap-2 text-xs text-rose-200"><p>{ui('ui_custom_remove_notice')}</p><div className="flex gap-2"><button type="button" className={button} onClick={() => void perform('remove')}>{ui('ui_custom_confirm_remove')}</button><button type="button" className={button} onClick={() => setRemove(false)}>{ui('ui_cancel')}</button></div></div>}
      </fieldset>
    </form>}
    {message && <p role="status" className="text-xs text-indigo-200">{message}</p>}
  </section>;
}
