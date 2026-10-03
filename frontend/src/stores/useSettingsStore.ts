import { create } from 'zustand';

export type ExitPolicy = 'prompt' | 'close_all' | 'keep_running';
export type DefaultLandingView = 'launcher' | 'canvas';

export interface AppSettings {
  exitPolicy: ExitPolicy;
  defaultLandingView: DefaultLandingView;
}

interface SettingsState extends AppSettings {
  setExitPolicy: (policy: ExitPolicy) => void;
  setDefaultLandingView: (view: DefaultLandingView) => void;
  resetSettings: () => void;
}

const STORAGE_KEY = 'berry_ai_studio_settings';

const defaultSettings: AppSettings = {
  exitPolicy: 'prompt',
  defaultLandingView: 'launcher',
};

const loadSettings = (): AppSettings => {
  try {
    if (typeof localStorage !== 'undefined') {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        return {
          exitPolicy: ['prompt', 'close_all', 'keep_running'].includes(parsed.exitPolicy)
            ? parsed.exitPolicy
            : defaultSettings.exitPolicy,
          defaultLandingView: ['launcher', 'canvas'].includes(parsed.defaultLandingView)
            ? parsed.defaultLandingView
            : defaultSettings.defaultLandingView,
        };
      }
    }
  } catch {
    // Fall back to defaults on parse error
  }
  return defaultSettings;
};

const saveSettings = (settings: AppSettings) => {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    }
  } catch (err) {
    console.error('Failed to persist settings:', err);
  }
};

export const useSettingsStore = create<SettingsState>((set, get) => {
  const initial = loadSettings();

  return {
    ...initial,

    setExitPolicy: (policy: ExitPolicy) => {
      set({ exitPolicy: policy });
      saveSettings({
        exitPolicy: policy,
        defaultLandingView: get().defaultLandingView,
      });
    },

    setDefaultLandingView: (view: DefaultLandingView) => {
      set({ defaultLandingView: view });
      saveSettings({
        exitPolicy: get().exitPolicy,
        defaultLandingView: view,
      });
    },

    resetSettings: () => {
      set({ ...defaultSettings });
      saveSettings(defaultSettings);
    },
  };
});
