import { useSettingsStore } from '../stores/useSettingsStore';
import { t } from './translations';

export function formatDateTime(value: string, timeOnly = false): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return t('ui_date_unavailable', useSettingsStore.getState().getEffectiveLanguage(), 'Date unavailable');
  return new Intl.DateTimeFormat(useSettingsStore.getState().getEffectiveLanguage(), timeOnly
    ? { hour: '2-digit', minute: '2-digit' }
    : { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

export function formatNumber(value: number, digits = 1, minimumDigits = 0): string {
  return new Intl.NumberFormat(useSettingsStore.getState().getEffectiveLanguage(), {
    maximumFractionDigits: digits, minimumFractionDigits: minimumDigits,
  }).format(value);
}


/** Remaining durations always include hours; round up partial seconds. */
export function formatDownloadDuration(seconds?: number | null): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return '';
  const rounded = Math.ceil(seconds);
  if (!Number.isSafeInteger(rounded)) return '';
  const language = useSettingsStore.getState().getEffectiveLanguage();
  const values = [Math.floor(rounded / 3600), Math.floor(rounded % 3600 / 60), rounded % 60];
  const units = ['hour', 'minute', 'second'] as const;
  return units.map((unit, index) => new Intl.NumberFormat(language, {
    style: 'unit', unit, unitDisplay: 'narrow', maximumFractionDigits: 0,
  }).format(values[index])).join(' ');
}
