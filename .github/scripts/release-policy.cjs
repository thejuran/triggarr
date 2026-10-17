// This file is loaded from main by the release preflight, never from a tag.
const REQUIRED_JOBS = ['test', 'lint', 'docker', 'secrets', 'dependencies', 'CI ready'];

function validateEvidence({sha, mainSha, ancestry, runs, jobs, tag}) {
  if (!/^[a-f0-9]{40}$/.test(sha || '')) throw new Error('Invalid release commit');
  if (!tag && sha !== mainSha) throw new Error('Superseded main build; refusing to republish old main');
  if (!['identical', 'behind'].includes(ancestry)) throw new Error('Release commit is not on main');
  const matching = runs.filter(r => r.head_sha === sha && r.event === 'push' && r.head_branch === 'main');
  matching.sort((a, b) => b.id - a.id);
  const run = matching[0];
  if (!run || run.status !== 'completed' || run.conclusion !== 'success') {
    throw new Error('Latest push CI for this exact commit has not succeeded');
  }
  for (const name of REQUIRED_JOBS) {
    const job = jobs.find(j => j.name === name && j.run_id === run.id);
    if (!job || job.status !== 'completed' || job.conclusion !== 'success') {
      throw new Error(`Required CI job missing or unsuccessful: ${name}`);
    }
  }
  return sha;
}

async function preflight({github, context, core}) {
  const {owner, repo} = context.repo;
  const tag = context.eventName === 'push' && context.ref.startsWith('refs/tags/v');
  const source = context.payload.workflow_run;
  if (!tag && !(context.eventName === 'workflow_run' && source?.event === 'push' &&
      source?.head_branch === 'main' && source?.conclusion === 'success' && source?.head_repository?.full_name === `${owner}/${repo}`)) {
    throw new Error('Untrusted release trigger');
  }
  const sha = tag ? context.sha : source.head_sha;
  const {data: main} = await github.rest.repos.getBranch({owner, repo, branch: 'main'});
  const {data: comparison} = await github.rest.repos.compareCommitsWithBasehead({owner, repo, basehead: `main...${sha}`});
  const runs = await github.paginate(github.rest.actions.listWorkflowRuns, {
    owner, repo, workflow_id: 'ci.yml', event: 'push', branch: 'main', head_sha: sha, per_page: 100
  });
  const latest = runs.filter(r => r.head_sha === sha && r.event === 'push' && r.head_branch === 'main')
    .sort((a,b) => b.id - a.id)[0];
  const jobs = latest ? await github.paginate(github.rest.actions.listJobsForWorkflowRun, {
    owner, repo, run_id: latest.id, filter: 'latest', per_page: 100
  }) : [];
  const verified = validateEvidence({sha, mainSha: main.commit.sha, ancestry: comparison.status, runs, jobs, tag});
  core.setOutput('sha', verified);
  core.info(`Release authorized by exact-commit CI: ${verified}, run ${latest.id}`);
}
module.exports = {REQUIRED_JOBS, validateEvidence, preflight};
