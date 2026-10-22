// No PR code is executed. GitHub stores the dispositions outside the branch.
function assess({head, currentHead, checks, comments, dispositions, blockers}) {
  if (!/^[0-9a-f]{40}$/.test(head || '') || currentHead !== head) throw Error('PR head changed; approval is stale');
  if (!blockers || blockers.schema !== 1 || !Array.isArray(blockers.open)) throw Error('Missing blocker register');
  if (blockers.open.length) throw Error(`Open accepted blockers: ${blockers.open.join(', ')}`);
  if (!dispositions || dispositions.schema !== 1 || typeof dispositions.items !== 'object' || dispositions.items === null) {
    throw Error('Missing finding dispositions');
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
    const d = dispositions.items[String(comment.id)];
    if (!d || d.head !== head || !['fixed','false_positive'].includes(d.decision) ||
        typeof d.evidence !== 'string' || d.evidence.trim().length < 20) {
      throw Error(`Finding ${comment.id} needs current-commit verification evidence; thread resolution is not sufficient`);
    }
  }
  return {findings: findings.length, greptile: latest ? 'success' : 'none'};
}
module.exports = {assess};
