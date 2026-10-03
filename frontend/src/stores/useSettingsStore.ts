import { create } from 'zustand';
import { LanguageSetting, SupportedLanguage, resolveEffectiveLanguage } from '../i18n/translations';

export type ExitPolicy = 'prompt' | 'close_all' | 'keep_running';
export type DefaultLandingView = 'launcher' | 'canvas';

export interface AppSettings {
  exitPolicy: ExitPolicy;
  defaultLandingView: DefaultLandingView;
  language: LanguageSetting;
}

interface SettingsState extends AppSettings {
  setExitPolicy: (policy: ExitPolicy) => void;
  setDefaultLandingView: (view: DefaultLandingView) => void;
  setLanguage: (lang: LanguageSetting) => void;
  getEffectiveLanguage: () => SupportedLanguage;
  resetSettings: () => void;
}

const STORAGE_KEY = 'berry_ai_studio_settings';

const defaultSettings: AppSettings = {
  exitPolicy: 'prompt',
  defaultLandingView: 'launcher',
  language: 'system',
};

const validLanguages: LanguageSetting[] = [
  'system',
  'en',
  'zh-CN',
  'ja',
  'ko',
  'fr',
  'de',
  'es',
  'ru',
];

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
          language: validLanguages.includes(parsed.language)
            ? parsed.language
            : defaultSettings.language,
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
        language: get().language,
      });
    },

    setDefaultLandingView: (view: DefaultLandingView) => {
      set({ defaultLandingView: view });
      saveSettings({
        exitPolicy: get().exitPolicy,
        defaultLandingView: view,
        language: get().language,
      });
    },

    setLanguage: (lang: LanguageSetting) => {
      set({ language: lang });
      saveSettings({
        exitPolicy: get().exitPolicy,
        defaultLandingView: get().defaultLandingView,
        language: lang,
      });
    },

    getEffectiveLanguage: () => {
      return resolveEffectiveLanguage(get().language);
    },

    resetSettings: () => {
      set({ ...defaultSettings });
      saveSettings(defaultSettings);
    },
  };
});
