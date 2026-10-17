// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StartupScreen } from '../components/startup/StartupScreen';
import { useSettingsStore } from '../stores/useSettingsStore';
import { LANGUAGE_OPTIONS, TRANSLATIONS } from '../i18n/translations';
import { UI_ENGLISH } from '../i18n/uiMessages';

const mocks = vi.hoisted(() => ({ invoke: vi.fn(), open: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke: mocks.invoke }));
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: mocks.open }));
const compatible = { path: 'C:/Python/python.exe', version: '3.12.14', ready: true, reason: 'ready', missing: [] };
let finish: (() => void) | undefined;
beforeEach(() => {
  useSettingsStore.setState({ language: 'en' });
  mocks.invoke.mockReset(); mocks.open.mockReset(); finish = undefined;
  mocks.invoke.mockImplementation((command: string) => {
    if (command === 'startup_status') return Promise.resolve({ phase: 'needs_environment', details: '', environment_path: 'app/runtime/core', can_install: true });
    if (command === 'discover_environments') return Promise.resolve([compatible]);
    if (command === 'prepare_environment') return new Promise<void>((resolve) => { finish = resolve; });
    return Promise.resolve();
  });
});
afterEach(() => { finish?.(); cleanup(); });

it('waits for explicit installation consent and switches the entire onboarding language', async () => {
  render(<StartupScreen />);
  await waitFor(() => expect((screen.getByText('Install and continue') as HTMLButtonElement).disabled).toBe(false));
  expect(mocks.invoke).not.toHaveBeenCalledWith('prepare_environment', expect.anything());
  fireEvent.change(screen.getByLabelText('Language'), { target: { value: 'zh-CN' } });
  expect(screen.getByText('自动安装并继续')).toBeTruthy();
  expect(screen.queryByText('Install and continue')).toBeNull();
  fireEvent.click(screen.getByText('自动安装并继续'));
  expect(mocks.invoke).toHaveBeenCalledWith('prepare_environment', { action: 'install', path: null, language: 'zh-CN' });
  fireEvent.click(screen.getByText('取消'));
  await waitFor(() => expect(mocks.invoke).toHaveBeenCalledWith('cancel_environment_setup'));
});

it('lets a user select a validated existing environment without installing packages', async () => {
  render(<StartupScreen />);
  fireEvent.click(screen.getByText('Find environments'));
  await screen.findByText(/Python 3.12.14/);
  fireEvent.change(screen.getByLabelText('Python environment'), { target: { value: compatible.path } });
  expect(screen.getByText('Compatible. Ready to use.')).toBeTruthy();
  fireEvent.click(screen.getByText('Use this environment and continue'));
  expect(mocks.invoke).toHaveBeenCalledWith('prepare_environment', { action: 'existing', path: compatible.path, language: 'en' });
});

it('rejects incomplete manually chosen environments and keeps automatic installation available', async () => {
  mocks.open.mockResolvedValue(compatible.path);
  mocks.invoke.mockImplementation((command: string) => Promise.resolve(command === 'startup_status'
    ? { phase: 'failed', details: 'Fixed technical diagnostic', can_install: true, environment_path: 'app/runtime/core' }
    : { ...compatible, ready: false, reason: 'dependencies', missing: ['fastapi'] }));
  render(<StartupScreen />);
  fireEvent.click(screen.getByText('Choose a file…'));
  await screen.findByText(/This environment needs additional/);
  expect((screen.getByText('Use this environment and continue') as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByText('Retry installation') as HTMLButtonElement).disabled).toBe(false);
  expect(mocks.invoke).not.toHaveBeenCalledWith('prepare_environment', expect.anything());
});

it('keeps the chooser usable after a discovery failure', async () => {
  mocks.invoke.mockImplementation((command: string) => command === 'discover_environments' ? Promise.reject(new Error('failed'))
    : Promise.resolve({ phase: 'needs_environment', details: '', can_install: true }));
  render(<StartupScreen />);
  fireEvent.click(screen.getByText('Find environments'));
  await screen.findByText(/We couldn’t complete setup/);
  expect((screen.getByText('Choose a file…') as HTMLButtonElement).disabled).toBe(false);
});

it.each(LANGUAGE_OPTIONS.filter((option) => option.id !== 'system'))('renders a complete onboarding catalog for $nativeLabel', async (option) => {
  if (option.id === 'system') return;
  const language = option.id;
  const keys = Object.keys(UI_ENGLISH).filter((key) => key.startsWith('setup'));
  for (const key of keys) expect(TRANSLATIONS[language][key], `${language}: ${key}`).toBeTruthy();
  useSettingsStore.setState({ language });
  render(<StartupScreen />);
  expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(TRANSLATIONS[language].setupTitle);
  expect(document.documentElement.lang).toBe(language);
  const select = screen.getByLabelText(TRANSLATIONS[language].setupLanguage);
  expect((select as HTMLSelectElement).options).toHaveLength(LANGUAGE_OPTIONS.length);
  await waitFor(() => expect((screen.getByText(TRANSLATIONS[language].setupInstall) as HTMLButtonElement).disabled).toBe(false));
});

it('follows a supported system language before any selection', async () => {
  const previous = Object.getOwnPropertyDescriptor(navigator, 'language');
  Object.defineProperty(navigator, 'language', { configurable: true, value: 'fr-FR' });
  useSettingsStore.setState({ language: 'system' });
  try {
    render(<StartupScreen />);
    expect(screen.getByText('Préparons Berry')).toBeTruthy();
    await waitFor(() => expect((screen.getByText('Installer et continuer') as HTMLButtonElement).disabled).toBe(false));
  } finally {
    if (previous) Object.defineProperty(navigator, 'language', previous);
    else Reflect.deleteProperty(navigator, 'language');
  }
});
