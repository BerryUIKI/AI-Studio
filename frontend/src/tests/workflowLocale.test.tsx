// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { CreationSetup } from '../components/canvas/CreationSetup';
import { useUiText, uiText } from '../i18n/useUiText';
import { UI_ENGLISH } from '../i18n/uiMessages';
import { TRANSLATIONS, VERIFIED_UI_LANGUAGES } from '../i18n/translations';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useEngineStore, defaultBuiltinInstances } from '../stores/useEngineStore';

afterEach(() => { cleanup(); useSettingsStore.getState().setLanguage('en'); });

it('updates mounted presentation when the locale changes and falls back to English', () => {
  function Label() { const ui = useUiText(); return <p>{ui('ui_generate_image')}</p>; }
  useSettingsStore.getState().setLanguage('en');
  TRANSLATIONS.ja.ui_generate_image = '画像を生成';
  try {
    render(<Label />);
    expect(screen.getByText('Generate Image')).toBeTruthy();
    act(() => useSettingsStore.getState().setLanguage('ja'));
    expect(screen.getByText('画像を生成')).toBeTruthy();
    expect(uiText('ui_generate_image', 'fr')).toBe('Generate Image');
    expect(VERIFIED_UI_LANGUAGES).toEqual(['en']);
  } finally { delete TRANSLATIONS.ja.ui_generate_image; }
});

it('keeps execution identities separate from translated engine labels', () => {
  useEngineStore.setState({ instances: defaultBuiltinInstances });
  TRANSLATIONS.ja.ui_comfyui = 'translated-id-must-not-route';
  try {
    useSettingsStore.getState().setLanguage('ja');
    render(<CreationSetup onCloudSetup={() => undefined} onLocalSetup={() => undefined} />);
    const select = screen.getByLabelText('Create with') as HTMLSelectElement;
    expect([...select.options].some((option) => option.value === 'comfyui-managed')).toBe(true);
  } finally { delete TRANSLATIONS.ja.ui_comfyui; }
});

it('resolves every primary catalog key without leaking translation identifiers', () => {
  for (const key of Object.keys(UI_ENGLISH) as Array<keyof typeof UI_ENGLISH>) {
    expect(uiText(key, 'en')).toBe(UI_ENGLISH[key]);
    expect(uiText(key, 'ru')).toBeTruthy();
  }
});
