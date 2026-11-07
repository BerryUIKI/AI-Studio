import { afterEach, expect, it } from 'vitest';
import { formatDownloadDuration } from '../i18n/format';
import { useSettingsStore } from '../stores/useSettingsStore';

afterEach(() => useSettingsStore.getState().setLanguage('en'));
it.each([
  [0, '0h 0m 0s'], [59, '0h 0m 59s'], [60, '0h 1m 0s'],
  [3599, '0h 59m 59s'], [3600, '1h 0m 0s'], [3661, '1h 1m 1s'],
  [90000, '25h 0m 0s'], [59.1, '0h 1m 0s'],
])('formats %s seconds as %s', (seconds, expected) => {
  useSettingsStore.getState().setLanguage('en');
  expect(formatDownloadDuration(seconds)).toBe(expected);
});
it.each([undefined, null, NaN, Infinity, -1, Number.MAX_VALUE])('omits invalid duration %s', (seconds) => {
  expect(formatDownloadDuration(seconds)).toBe('');
});
it('uses locale-specific duration units', () => {
  useSettingsStore.getState().setLanguage('zh-CN');
  expect(formatDownloadDuration(3661)).toBe('1小时 1分钟 1秒');
  useSettingsStore.getState().setLanguage('fr');
  expect(formatDownloadDuration(3661)).toMatch(/1.*h.*1.*min.*1.*s/);
});
