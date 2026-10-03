import { describe, it, expect, beforeEach } from 'vitest';

const memoryStore: Record<string, string> = {};

const storageMock = {
  getItem: (key: string) => memoryStore[key] || null,
  setItem: (key: string, value: string) => {
    memoryStore[key] = value.toString();
  },
  clear: () => {
    for (const key of Object.keys(memoryStore)) {
      delete memoryStore[key];
    }
  },
  removeItem: (key: string) => {
    delete memoryStore[key];
  },
};

Object.defineProperty(globalThis, 'localStorage', {
  value: storageMock,
  writable: true,
  configurable: true,
});

import { useSettingsStore } from '../stores/useSettingsStore';

describe('useSettingsStore', () => {
  beforeEach(() => {
    localStorage.clear();
    useSettingsStore.getState().resetSettings();
  });

  it('initializes with default exit policy prompt and landing view launcher', () => {
    const state = useSettingsStore.getState();
    expect(state.exitPolicy).toBe('prompt');
    expect(state.defaultLandingView).toBe('launcher');
  });

  it('updates exit policy and persists to localStorage', () => {
    const store = useSettingsStore.getState();
    store.setExitPolicy('close_all');
    expect(useSettingsStore.getState().exitPolicy).toBe('close_all');

    const stored = JSON.parse(localStorage.getItem('berry_ai_studio_settings') || '{}');
    expect(stored.exitPolicy).toBe('close_all');

    store.setExitPolicy('keep_running');
    expect(useSettingsStore.getState().exitPolicy).toBe('keep_running');
  });

  it('updates default landing view and persists to localStorage', () => {
    const store = useSettingsStore.getState();
    store.setDefaultLandingView('canvas');
    expect(useSettingsStore.getState().defaultLandingView).toBe('canvas');

    const stored = JSON.parse(localStorage.getItem('berry_ai_studio_settings') || '{}');
    expect(stored.defaultLandingView).toBe('canvas');
  });

  it('resets settings to default values', () => {
    const store = useSettingsStore.getState();
    store.setExitPolicy('close_all');
    store.setDefaultLandingView('canvas');
    store.setLanguage('ja');

    store.resetSettings();
    expect(useSettingsStore.getState().exitPolicy).toBe('prompt');
    expect(useSettingsStore.getState().defaultLandingView).toBe('launcher');
    expect(useSettingsStore.getState().language).toBe('system');
  });

  it('updates language and persists to localStorage', () => {
    const store = useSettingsStore.getState();
    expect(store.language).toBe('system');

    store.setLanguage('zh-CN');
    expect(useSettingsStore.getState().language).toBe('zh-CN');
    expect(useSettingsStore.getState().getEffectiveLanguage()).toBe('zh-CN');

    const stored = JSON.parse(localStorage.getItem('berry_ai_studio_settings') || '{}');
    expect(stored.language).toBe('zh-CN');

    // Test French
    store.setLanguage('fr');
    expect(useSettingsStore.getState().getEffectiveLanguage()).toBe('fr');
  });

  it('falls back to English when system language is undetectable or unmapped', () => {
    const store = useSettingsStore.getState();
    store.setLanguage('system');

    // Mock navigator.language as unsupported language (e.g., Icelandic)
    Object.defineProperty(globalThis, 'navigator', {
      value: { language: 'is-IS' },
      writable: true,
      configurable: true,
    });

    expect(useSettingsStore.getState().getEffectiveLanguage()).toBe('en');
  });
});
