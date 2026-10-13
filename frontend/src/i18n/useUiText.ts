import { useCallback, useMemo } from 'react';
import { useSettingsStore } from '../stores/useSettingsStore';
import { resolveEffectiveLanguage, t, type SupportedLanguage } from './translations';
import { UI_ENGLISH } from './uiMessages';

export type UiMessageKey = keyof typeof UI_ENGLISH;
export type MessageValues = Record<string, string | number | null | undefined>;
const catalogKeys = new Map(Object.entries(UI_ENGLISH).map(([key, value]) => [value as string, key as UiMessageKey]));

export function uiText(key: UiMessageKey, language: SupportedLanguage, values: MessageValues = {}): string {
  return t(key, language).replace(/\{(\w+)\}/g, (token, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name] ?? '') : token);
}

/** Subscribe only to the locale; changing language updates already-mounted UI. */
export function useUiText() {
  const setting = useSettingsStore((state) => state.language);
  const language = resolveEffectiveLanguage(setting);
  const text = useCallback((key: UiMessageKey, values?: MessageValues) => uiText(key, language, values), [language]);
  return useMemo(() => Object.assign(text, {
    // Static catalog metadata is localized only when rendered, never before dispatch.
    lookup: (message: string) => {
      const key = catalogKeys.get(message);
      return key ? text(key) : message;
    },
  }), [text]);
}
