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
  const label = model.integrity_status === 'invalid' ? 'Invalid file'
    : model.integrity_status !== 'structurally-valid' ? 'File unverified'
      : model.architecture_status !== 'recognized' ? 'Architecture unverified'
        : model.dependency_status === 'missing' ? 'Missing components'
          : model.is_ready && model.engine_compatibility.length > 0 ? 'Ready'
            : 'Engine untested';
  const detail = [
    `File: ${model.integrity_status}; format: ${model.format_recognized ? 'recognized' : 'unverified'}`,
    `Architecture: ${model.architecture_status}; components: ${model.dependency_status}`,
    model.missing_dependencies.length ? `Missing: ${model.missing_dependencies.join(', ')}` : '',
    `Engine tested: ${model.engine_compatibility.join(', ') || 'none'}`,
    model.content_hash ? `SHA-256: ${model.content_hash}` : '',
    model.guidance,
  ].filter(Boolean).join('\n');
  return <span className={label === 'Ready' ? 'text-emerald-400' : 'text-amber-400'} title={detail}>{label}</span>;
}
