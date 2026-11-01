import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ModelReadiness, type ModelReadinessEvidence } from './ModelReadiness';

const base: ModelReadinessEvidence = {
  integrity_status: 'structurally-valid', format_recognized: true,
  architecture_status: 'recognized', dependency_status: 'present',
  missing_dependencies: [], engine_compatibility: [], is_ready: false,
};

describe('model readiness evidence', () => {
  const cases: [Partial<ModelReadinessEvidence>, string][] = [
    [{ integrity_status: 'invalid' }, 'Invalid file'],
    [{ integrity_status: 'unverified' }, 'File unverified'],
    [{ architecture_status: 'unverified' }, 'Architecture unverified'],
    [{ dependency_status: 'missing', missing_dependencies: ['t5xxl'] }, 'Missing components'],
    [{ is_ready: true }, 'Engine untested'],
    [{ is_ready: true, engine_compatibility: ['comfyui'] }, 'Ready'],
  ];
  it.each(cases)('renders %s as %s', (override, label) => {
    const markup = renderToStaticMarkup(<ModelReadiness model={{ ...base, ...override }} />);
    expect(markup).toContain(`>${label}</span>`);
  });
});
