import { useUiText } from '../../i18n/useUiText';

export interface ModelReadinessEvidence {
  integrity_status: 'structurally-valid' | 'invalid' | 'unverified';
  format_recognized: boolean;
  architecture_status: 'recognized' | 'unverified';
  dependency_status: 'not-assessed' | 'present' | 'missing';
  missing_dependencies: string[];
  engine_compatibility: string[];
  is_ready: boolean;
  content_hash?: string;
  guidance?: string;
}

export function ModelReadiness({ model }: { model: ModelReadinessEvidence }) {
  const ui = useUiText();
  const label = model.integrity_status === 'invalid' ? ui('ui_invalid_file')
    : model.integrity_status !== 'structurally-valid' ? ui('ui_file_unverified')
      : model.architecture_status !== 'recognized' ? ui('ui_architecture_unverified')
        : model.dependency_status === 'missing' ? ui('ui_missing_components')
          : model.is_ready && model.engine_compatibility.length > 0 ? ui('ui_ready')
            : ui('ui_engine_untested');
  const detail = [
    ui('ui_file_format', { file: model.integrity_status, format: model.format_recognized ? ui('ui_recognized') : ui('ui_unverified') }),
    ui('ui_architecture_components', { architecture: model.architecture_status, components: model.dependency_status }),
    model.missing_dependencies.length ? ui('ui_missing_components_list', { components: model.missing_dependencies.join(', ') }) : '',
    ui('ui_engine_tested', { engines: model.engine_compatibility.join(', ') || ui('ui_none') }),
    model.content_hash ? `SHA-256: ${model.content_hash}` : '',
    model.guidance,
  ].filter(Boolean).join('\n');
  const ready = model.integrity_status === 'structurally-valid' && model.architecture_status === 'recognized'
    && model.dependency_status !== 'missing' && model.is_ready && model.engine_compatibility.length > 0;
  return <span className={ready ? 'text-emerald-400' : 'text-amber-400'} title={detail}>{label}</span>;
}
