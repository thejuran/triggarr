// No PR code is executed. GitHub stores the dispositions outside the branch.
function registerKey(prNumber, head) {
  return `${prNumber}:${head}`;
}

function assess({prNumber, head, currentHead, draft, checks, comments, dispositions, blockers}) {
  if (!/^[0-9a-f]{40}$/.test(head || '') || currentHead !== head) throw Error('PR head changed; approval is stale');
  if (!Number.isSafeInteger(prNumber) || prNumber <= 0) throw Error('Invalid PR number');
  if (draft !== false) throw Error('PR is still a draft; mark it ready for review before acceptance');
  if (blockers?.schema === 1 || dispositions?.schema === 1) {
    throw Error('Register schema 1 is retired; migrate to schema 2 keyed by PR and head (docs/buildomator-greptile-pilot.md)');
  }
  if (!blockers || blockers.schema !== 2 || !Array.isArray(blockers.global_open) ||
      typeof blockers.by_pr_head !== 'object' || blockers.by_pr_head === null) {
    throw Error('Missing blocker register');
  }
  if (blockers.global_open.length) throw Error(`Open accepted blockers: ${blockers.global_open.join(', ')}`);
  const key = registerKey(prNumber, head);
  const blockerSlice = Object.hasOwn(blockers.by_pr_head, key) ? blockers.by_pr_head[key] : undefined;
  if (!blockerSlice || !Array.isArray(blockerSlice.open)) {
    throw Error(`No blocker register entry for PR ${prNumber} at ${head}`);
  }
  if (blockerSlice.open.length) throw Error(`Open accepted blockers: ${blockerSlice.open.join(', ')}`);
  if (!dispositions || dispositions.schema !== 2 || typeof dispositions.by_pr_head !== 'object' || dispositions.by_pr_head === null) {
    throw Error('Missing finding dispositions');
  }
  const dispositionSlice = Object.hasOwn(dispositions.by_pr_head, key) ? dispositions.by_pr_head[key] : undefined;
  if (!dispositionSlice || typeof dispositionSlice.items !== 'object' || dispositionSlice.items === null) {
    throw Error(`No disposition register entry for PR ${prNumber} at ${head}`);
  }
  // Greptile is optional (owner decision 2026-10-22): a head with no Greptile review may be accepted, but a
  // review that exists for this head must have completed successfully -- a running or failed one blocks.
  const latest = checks.filter(c => c.head_sha === head && c.name === 'Greptile Review' && c.app?.id === 867647)
    .sort((a,b) => b.id-a.id)[0];
  if (latest && (latest.status !== 'completed' || latest.conclusion !== 'success')) {
    throw Error('Current Greptile review is still running or unsuccessful');
  }
  const findings = comments.filter(c => c.user?.login === 'greptile-apps[bot]');
  for (const comment of findings) {
    const commentKey = String(comment.id);
    const d = Object.hasOwn(dispositionSlice.items, commentKey) ? dispositionSlice.items[commentKey] : undefined;
    if (!d || d.head !== head || !['fixed','false_positive'].includes(d.decision) ||
        typeof d.evidence !== 'string' || d.evidence.trim().length < 20) {
      throw Error(`Finding ${comment.id} needs current-commit verification evidence; thread resolution is not sufficient`);
    }
  }
  return {findings: findings.length, greptile: latest ? 'success' : 'none'};
}
module.exports = {assess, registerKey};
