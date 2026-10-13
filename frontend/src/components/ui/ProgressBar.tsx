import { useUiText } from '../../i18n/useUiText';
interface ProgressBarProps {
  value?: number;
  label: string;
  className?: string;
}

export function ProgressBar({ value, label, className = 'text-indigo-500' }: ProgressBarProps) {
  const ui = useUiText();
  const bounded = value === undefined ? undefined : Math.max(0, Math.min(100, value));
  return <svg role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={bounded}
    aria-valuetext={bounded === undefined ? ui("ui_waiting_for_observed_progress") : undefined}
    viewBox="0 0 100 1" preserveAspectRatio="none" className={`h-full w-full ${className}`}>
    <rect width={bounded ?? 100} height={1} className={bounded === undefined ? 'fill-current animate-pulse motion-reduce:animate-none opacity-40' : 'fill-current'} />
  </svg>;
}
