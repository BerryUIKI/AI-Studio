import { useSettingsStore } from '../stores/useSettingsStore';

export function formatDateTime(value: string, timeOnly = false): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return 'Date unavailable';
  return new Intl.DateTimeFormat(useSettingsStore.getState().getEffectiveLanguage(), timeOnly
    ? { hour: '2-digit', minute: '2-digit' }
    : { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

export function formatNumber(value: number, digits = 1): string {
  return new Intl.NumberFormat(useSettingsStore.getState().getEffectiveLanguage(), { maximumFractionDigits: digits }).format(value);
}
