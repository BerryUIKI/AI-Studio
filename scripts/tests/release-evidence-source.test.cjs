const { test } = require('node:test');
const assert = require('node:assert/strict');
const { resolveReference, validateSource } = require('../release-evidence-source.cjs');

test('requires a single valid external artifact reference', () => {
  const marker = '<!-- berry-acceptance {"run_id":123,"artifact":"live-acceptance"} -->';
  assert.deepEqual(resolveReference(marker), { run_id: 123, artifact: 'live-acceptance' });
  for (const body of ['', marker + marker, '<!-- berry-acceptance {} -->',
    '<!-- berry-acceptance {"run_id":123,"artifact":"../../secret"} -->',
    '<!-- berry-acceptance {"run_id":"123; echo injected","artifact":"ok"} -->']) {
    assert.throws(() => resolveReference(body));
  }
});

test('rejects historical, fork and incomplete source runs', () => {
  const commit = 'a'.repeat(40), repository = 'BerryUIKI/AI-Studio';
  const run = { head_sha: commit, status: 'completed', conclusion: 'success', head_repository: { full_name: repository } };
  assert.doesNotThrow(() => validateSource(run, commit, repository));
  for (const change of [{ head_sha: 'b'.repeat(40) }, { status: 'in_progress' },
    { conclusion: 'failure' }, { head_repository: { full_name: 'another/repo' } }]) {
    assert.throws(() => validateSource({ ...run, ...change }, commit, repository));
  }
});
