// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DownloadManagerDrawer } from '../components/hub/DownloadManagerDrawer';
import { FloatingDownloadWidget } from '../components/hub/FloatingDownloadWidget';
import { DOWNLOAD_TRANSLATIONS } from '../i18n/downloadMessages';
import { uiText } from '../i18n/useUiText';
import { type SupportedLanguage } from '../i18n/translations';
import { useDownloadStore, type DownloadTask } from '../stores/useDownloadStore';
import { useSettingsStore } from '../stores/useSettingsStore';

const languages = Object.keys(DOWNLOAD_TRANSLATIONS) as SupportedLanguage[];
const task: DownloadTask = {
  task_id: 'download', model_id: 'model', model_name: 'Model identifier', target_engine: 'comfyui',
  target_path: '/owned/model.safetensors', status: 'downloading', total_bytes: 100,
  downloaded_bytes: 25, progress_pct: 25.5, speed_bps: 10, eta_seconds: 3661,
};
beforeEach(() => useDownloadStore.setState({ isDrawerOpen: true, tasks: [task] }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); useSettingsStore.getState().setLanguage('en'); });

it.each(languages)('renders every download state and action in %s', (language) => {
  useSettingsStore.getState().setLanguage(language);
  const statuses = ['pending', 'downloading', 'paused', 'completed', 'failed', 'cancelled'] as const;
  useDownloadStore.setState({ tasks: statuses.map((status) => ({ ...task, task_id: status, status, error_message: status === 'failed' ? 'HTTP 503 service response' : null })) });
  render(<DownloadManagerDrawer />);
  const catalog = DOWNLOAD_TRANSLATIONS[language];
  expect(Object.keys(catalog).sort()).toEqual(Object.keys(DOWNLOAD_TRANSLATIONS.en).sort());
  expect(screen.getByRole('dialog', { name: catalog.ui_downloads })).toBeTruthy();
  for (const label of [catalog.ui_pause, catalog.ui_resume, catalog.ui_close_downloads, catalog.downloadRemoveHistory]) {
    expect(screen.getByRole('button', { name: label })).toBeTruthy();
  }
  expect(screen.getAllByRole('button', { name: catalog.downloadCancelRemove })).toHaveLength(5);
  for (const label of [catalog.ui_paused, catalog.ui_installed, catalog.ui_failed, catalog.downloadPending, catalog.downloadCancelled, catalog.downloadDetails, catalog.downloadFailedMessage]) {
    expect(screen.getByText(label)).toBeTruthy();
  }
  expect(screen.getByText('HTTP 503 service response')).toBeTruthy();
  expect(screen.getAllByText('Model identifier')).toHaveLength(6);
  expect(screen.getAllByText(/COMFYUI.*\/owned\/model.safetensors/)).toHaveLength(6);
  expect(screen.getByText(uiText('downloadCounts', language, { active: 2, completed: 1 }))).toBeTruthy();
});

it.each(languages)('localizes empty downloads and the floating widget in %s', (language) => {
  useSettingsStore.getState().setLanguage(language);
  useDownloadStore.setState({ tasks: [] });
  const view = render(<DownloadManagerDrawer />);
  expect(screen.getByText(DOWNLOAD_TRANSLATIONS[language].ui_no_download_tasks_yet)).toBeTruthy();
  view.unmount();
  useDownloadStore.setState({ isDrawerOpen: false, tasks: [task] });
  render(<FloatingDownloadWidget />);
  expect(screen.getByRole('button', { name: DOWNLOAD_TRANSLATIONS[language].ui_downloads })).toBeTruthy();
  expect(screen.getByText(uiText('downloadWidgetActive', language, { count: 1 }))).toBeTruthy();
});

it('updates mounted downloads when switching from system language', () => {
  vi.spyOn(navigator, 'language', 'get').mockReturnValue('ja-JP');
  useSettingsStore.getState().setLanguage('system');
  const view = render(<DownloadManagerDrawer />);
  expect(screen.getByRole('dialog', { name: DOWNLOAD_TRANSLATIONS.ja.ui_downloads })).toBeTruthy();
  useSettingsStore.getState().setLanguage('fr');
  view.rerender(<DownloadManagerDrawer />);
  expect(screen.getByRole('dialog', { name: DOWNLOAD_TRANSLATIONS.fr.ui_downloads })).toBeTruthy();
  expect(screen.getByText(/25,5%/)).toBeTruthy();
  vi.restoreAllMocks();
});

it('shows localized pause failures instead of silently ignoring them', async () => {
  useSettingsStore.getState().setLanguage('es');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 409 })));
  render(<DownloadManagerDrawer />);
  fireEvent.click(screen.getByRole('button', { name: DOWNLOAD_TRANSLATIONS.es.ui_pause }));
  expect((await screen.findByRole('alert')).textContent).toBe(DOWNLOAD_TRANSLATIONS.es.downloadActionError);
});
