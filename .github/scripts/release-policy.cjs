// This file is loaded from main by the release preflight, never from a tag.
// The release-identity functions below follow that same rule: they are never read from the tag.
const REQUIRED_JOBS = ['test', 'lint', 'docker', 'secrets', 'dependencies', 'image-smoke', 'browser-e2e', 'CI ready'];
const RELEASE_TAG_RE = /^refs\/tags\/v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;

function describeVersions({tag, packageVersion, imageVersion}) {
  const show = v => (v === undefined ? 'not inspected' : v === '' ? 'missing' : v);
  return `(tag: ${show(tag)}, package: ${show(packageVersion)}, image: ${show(imageVersion)})`;
}

function parseReleaseTag(ref) {
  const match = RELEASE_TAG_RE.exec(ref ?? '');
  if (!match) {
    const suffix = describeVersions({tag: undefined, packageVersion: undefined, imageVersion: undefined});
    throw new Error(`Release rejected: malformed tag "${ref}" ${suffix}`);
  }
  return `${match[1]}.${match[2]}.${match[3]}`;
}

function parseProjectVersion(pyprojectText) {
  const lines = String(pyprojectText ?? '').split('\n');
  const tableStart = lines.indexOf('[project]');
  const versions = [];
  if (tableStart !== -1) {
    for (let i = tableStart + 1; i < lines.length && !lines[i].startsWith('['); i++) {
      const match = /^version\s*=\s*"([^"\\]+)"\s*$/.exec(lines[i]);
      if (match) versions.push(match[1]);
    }
  }
  if (versions.length !== 1) {
    const suffix = describeVersions({tag: undefined, packageVersion: undefined, imageVersion: undefined});
    throw new Error(`Release rejected: package version missing or invalid in pyproject.toml ${suffix}`);
  }
  return versions[0];
}

function validateReleaseIdentity({ref, packageVersion, imageVersion}) {
  const tag = parseReleaseTag(ref);
  const suffix = describeVersions({tag, packageVersion, imageVersion});
  if (packageVersion === undefined || packageVersion === '') {
    throw new Error(`Release rejected: missing package version ${suffix}`);
  }
  if (imageVersion === undefined || imageVersion === '') {
    throw new Error(`Release rejected: missing image version ${suffix}`);
  }
  if (packageVersion !== tag || imageVersion !== tag) {
    throw new Error(`Release rejected: tag, package and image versions disagree ${suffix}`);
  }
  return tag;
}

async function releaseIdentityGate({github, context, core, sha, imageVersion}) {
  if (!/^[a-f0-9]{40}$/.test(sha || '')) throw new Error('Invalid release commit');
  const {owner, repo} = context.repo;
  const {data} = await github.rest.repos.getContent({owner, repo, path: 'pyproject.toml', ref: sha});
  if (!data || Array.isArray(data) || data.encoding !== 'base64' || typeof data.content !== 'string') {
    const suffix = describeVersions({tag: undefined, packageVersion: undefined, imageVersion});
    throw new Error(`Release rejected: package version not readable from pyproject.toml at ${sha} ${suffix}`);
  }
  const pyprojectText = Buffer.from(data.content, 'base64').toString('utf8');
  const packageVersion = parseProjectVersion(pyprojectText);
  const version = validateReleaseIdentity({ref: context.ref, packageVersion, imageVersion});
  core.info(`Release version identity verified: tag, package and audited image all report ${version}`);
  return version;
}

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
  core.setOutput('run_id', String(latest.id));
  core.info(`Release authorized by exact-commit CI: ${verified}, run ${latest.id}`);
}
module.exports = {REQUIRED_JOBS, validateEvidence, preflight, parseReleaseTag, parseProjectVersion, validateReleaseIdentity, releaseIdentityGate};
