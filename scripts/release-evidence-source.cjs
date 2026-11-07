// Parse external evidence references without evaluating PR-supplied content.
function resolveReference(body) {
  const matches = [...body.matchAll(/<!--\s*berry-acceptance\s+(\{[^\n]*\})\s*-->/g)];
  if (matches.length !== 1) throw new Error('Release PR requires exactly one berry-acceptance artifact reference.');
  const reference = JSON.parse(matches[0][1]);
  if (!Number.isSafeInteger(reference.run_id) || reference.run_id < 1 ||
      typeof reference.artifact !== 'string' || !/^[A-Za-z0-9_.-]{1,100}$/.test(reference.artifact)) {
    throw new Error('Invalid acceptance artifact run_id or name.');
  }
  return reference;
}

function validateSource(run, commit, repository) {
  if (!/^[0-9a-f]{40}$/.test(commit) || run.head_sha !== commit ||
      run.status !== 'completed' || run.conclusion !== 'success' ||
      run.head_repository?.full_name !== repository) {
    throw new Error('Evidence requires a successful same-repository run on the exact release PR head.');
  }
}

module.exports = { resolveReference, validateSource };
