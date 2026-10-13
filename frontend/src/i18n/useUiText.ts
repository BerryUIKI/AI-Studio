import { useCallback } from 'react';
import { useSettingsStore } from '../stores/useSettingsStore';
import { resolveEffectiveLanguage, t, type SupportedLanguage } from './translations';
import { UI_ENGLISH } from './uiMessages';

export type UiMessageKey = keyof typeof UI_ENGLISH;
export type MessageValues = Record<string, string | number | null | undefined>;

export function uiText(key: UiMessageKey, language: SupportedLanguage, values: MessageValues = {}): string {
  return t(key, language).replace(/\{(\w+)\}/g, (token, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name] ?? '') : token);
}

/** Subscribe only to the locale; changing language updates already-mounted UI. */
export function useUiText() {
  const setting = useSettingsStore((state) => state.language);
  const language = resolveEffectiveLanguage(setting);
  return useCallback((key: UiMessageKey, values?: MessageValues) => uiText(key, language, values), [language]);
}
