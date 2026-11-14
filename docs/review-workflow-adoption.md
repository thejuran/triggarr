# Review workflow adoption guide

Date: 2026-11-14
Status: Reference guide, written after a five-pull-request pilot of this workflow in this repository (Triggarr).
Applies to: other repositories owned by the same person (for example SeedSyncarr). Turning this into one shared, reusable workflow package across repositories, and actually rolling it out to SeedSyncarr, are both future work (FUT-01, FUT-02) that has not been done yet — this document is the reference to use when that work happens.

## Who this is for

Anyone setting up a similar review process on another repository — most likely a solo maintainer or a small team using an AI coding assistant for most of the implementation work, who wants GitHub itself to enforce the basic merge rules (not just a written instruction that an agent might skip), backed up by an independent second AI review of every change.

This guide assumes you already have a GitHub repository with Actions (GitHub's built-in automation runner) available, and a way to run an AI coding assistant against it (this repository uses Buildomator, referred to below as "BM", for planning, implementation, and a first-pass code review).

## The workflow in one page

The target sequence for every real change, once this is fully set up:

1. **Plan.** Work is described and scoped before any code is written.
2. **Implement on a feature branch.** Never commit directly to the default branch.
3. **Classify.** Before review starts, decide what kind of change this is — ordinary documentation, a sensitive change to agent instructions or automation, or application code — because that decision controls how much review happens next (see "Content-based review classification" below).
4. **BM review, plus an independent Codex pass on the exact same commit.** BM's own code review runs first; a separate AI system (Codex) then reviews the identical commit independently, so one reviewer's blind spots aren't the only check.
5. **A risk note, and a vibe-check when risk is high.** Every reviewed commit gets a short, explicit risk assessment (low/moderate/high, with concrete failure scenarios). When risk is assessed high, a heavier review pass ("vibe-check" — see the instruction-enforced section below) is required for that commit, and the record notes that it ran and where its report is. Below high risk it is not run routinely.
6. **A checkpoint record for that exact commit ("head").** One record per reviewed commit, naming the full commit identifier (the "SHA" — a long hexadecimal string that uniquely and permanently identifies one exact snapshot of the code), what was reviewed, and what was found. Earlier records are never edited or deleted, even after the matching GitHub conversation thread is marked resolved.
7. **CI.** GitHub's automated checks (tests, builds, security scans) run and must pass.
8. **Exact-commit owner acceptance.** The human owner explicitly approves that specific commit — not "the PR in general" — before it can merge.
9. **The owner merges.** Approval does not merge anything by itself; merging is a separate, explicit step.

Steps 4-8 repeat on a fresh commit whenever a fix changes the code: evidence from an earlier commit never carries over to a later one.

## GitHub-enforced requirements

These are true because GitHub itself enforces them — it blocks a merge that doesn't satisfy them or, for action pinning, refuses to run a workflow that breaks the rule — not because an instruction file says so. Every item below was read back from this repository's live GitHub configuration rather than copied from an earlier research note: the ruleset, its required checks and the acceptance environment while writing this guide, and all five items again (including the action-pinning setting and the CodeQL setup, which the first pass had not read from GitHub) on 2026-11-14 during review of this guide. The first pass's commands and results are listed in `86-09-SUMMARY.md`, in the same folder as the pilot record named under "What the pilot showed" below.

### A branch protection ruleset

**What it is:** GitHub's modern name for branch protection is a "ruleset" — a named set of rules attached to a branch (usually the default branch) that GitHub enforces on every pull request targeting it, independent of anything an AI agent or a human does.

**How to set it up:** In the repository's Settings, under Rules → Rulesets, create a new branch ruleset targeting the default branch. At minimum, enable: a rule requiring a pull request before any merge (so nobody can push straight to the default branch), a rule blocking deletion of the branch, and a rule blocking non-fast-forward pushes (so history can't be silently rewritten). Add a required-status-checks rule (see the next item) and, if you want an extra human-approval gate beyond PR review comments, a required-deployments rule naming a protected environment (see "A protected acceptance environment" below).

**What it does not prove:** that the checks it requires are actually good checks. A ruleset only guarantees that whatever checks you named must report success; a required check that is a no-op, or that never actually tests the behavior you care about, still reports green and still lets the merge through.

### Required status checks, kept current with the branch

**What it is:** a list of named checks that must report success on a PR's current commit before the ruleset lets it merge. This repository's live ruleset requires three: "CI ready" (this repository's own aggregate test/build/lint gate, reported by its GitHub Actions workflow), "CodeQL" (see below), and "Review acceptance" (this repository's own gate, described next). The ruleset also has "strict" status checks turned on, meaning a check result only counts if it ran against a branch that was up to date with the default branch at the time — a check that passed against a stale, out-of-date version of the branch does not count.

**How to set it up:** each check must already exist as something GitHub actually reports (a workflow job name, or GitHub's own code-scanning integration) before you can require it. Add it to the ruleset's required-status-checks list by its exact reported name, and turn on the "require branches to be up to date" option.

**What it does not prove:** that the named check measures the right thing, or that it can't be satisfied by a shallow or disabled implementation. Naming a check as required only stops a merge when that check is missing or failing — it says nothing about what the check actually verifies.

### A protected acceptance environment

**What it is:** GitHub Environments (Settings → Environments) can require one or more specific people to explicitly approve a "deployment" to that environment before a workflow job targeting it is allowed to proceed. This repository created an environment that a workflow job requests a deployment to on every PR, with a named required reviewer and "administrators can bypass" turned off; a required-deployments rule in the branch ruleset then makes that environment's approval a precondition for merging. In effect, this makes "the named approver's account approved this workflow run for this exact commit" a GitHub-enforced fact, not just a social expectation.

**How to set it up:** create the environment, turn on "required reviewers" and add the real approver(s), then add a required-deployments rule to the branch ruleset naming that environment, and have a workflow job in your CI actually request a deployment to it (so there's something for the reviewer to approve).

**What it does not prove:** that the reviewer actually read or understood what they approved — GitHub records that an approval event happened, from that person's account, for that exact commit; it has no way to verify the reviewer was informed. Nor does it prove that a person made the decision: if an AI agent can act with the approver's credentials, as it can here when relaying the owner's explicit approval, GitHub cannot tell the agent's submission from the person's own click. That a human actually decided is instruction-enforced (item 7 in the next section). (See "solo-maintainer self-approval," below, for why this matters more on some repositories than others.)

### Full-SHA action pinning

**What it is:** every third-party step in a GitHub Actions workflow (`uses: owner/action@something`) can be pinned to a mutable tag like `@v4`, which can later be moved by the action's maintainer (or an attacker who compromises their account) to point at different code without your workflow file changing at all — or pinned to a full 40-character commit hash, which cannot be moved. This repository pins every third-party action to its full commit hash, with a version number in a trailing comment purely for a human reader's convenience.

**How to set it up:** in the repository's Settings, under Actions → General, turn on "Require actions to be pinned to a full-length commit SHA". GitHub then refuses to run a workflow that uses an unpinned action; this repository has the setting on. A test that fails if any `uses:` line in a workflow file isn't a 40-character hex string is a useful second check, because it reports the problem in review rather than when the workflow fails to start.

**What it does not prove:** that the pinned commit's code is itself safe — only that the code you reviewed when you pinned it can't silently change under you afterward. The setting stops the workflow run, not the merge directly, and anyone with administrator access to the repository's settings can turn it off.

### CodeQL

**What it is:** GitHub's own built-in static-analysis scanner (it reads code looking for patterns, without running it) for common categories of security bugs — things like injection flaws or unsafe deserialization. It is free for public repositories and needs no project-specific rules to start finding things.

**How to set it up:** turn it on under Settings → Code security → Code scanning and choose default setup, which is what this repository uses; GitHub then runs the scan itself, with no workflow file to add or maintain, and reports a "CodeQL" check you can then add to your required-status-checks list.

**What it does not prove:** that your application's specific business logic is correct. CodeQL finds generic code-pattern bugs; it has no idea what your feature is supposed to do, so a logic error that doesn't match one of its known bug patterns will not be flagged.

## Instruction-enforced requirements

These are true only because a written instruction file (in this repository, `CLAUDE.md` and the linked `docs/` files it points to) tells the AI agent to do them. Nothing on GitHub blocks an agent — or a future maintainer — from skipping any of these; they depend entirely on the instructions being followed.

1. **BM's own code review is turned on, at a chosen depth.** BM has a built-in code-review feature with a configurable depth (quick/standard/deep) that must be explicitly enabled through its own settings. What breaks if skipped: BM's first-pass review simply doesn't run, and the independent Codex pass below (which is defined to follow every BM code-review run) has nothing to pair itself against.

2. **An independent Codex pass is paired with every BM code-review run.** After BM's own review, a completely separate AI system (Codex) independently re-reviews the identical commit, read-only, with its own fixed prompt and a required structured report (inspected commit, what it covered, what it excluded, every command it actually ran, and each finding with evidence). What breaks if skipped: GitHub cannot tell the difference between "two independent reviewers looked at this" and "only one reviewer looked at this" — the pairing exists purely because the instruction file says to run it every time, and because missing, stale, or wrong-commit Codex evidence is written down as incomplete rather than quietly treated as "fine."

3. **Content-based review classification.** Before review starts, each reviewed commit is classified by what it actually changes, not by file extension: a markdown file that edits agent instructions, a CI workflow, or acceptance policy is treated as sensitive and gets a full risk assessment and technical review, even though it's "just a text file." Ordinary documentation and planning notes get a lighter, focused consistency check instead. What breaks if skipped: a change to the rules that govern review and acceptance itself could slip through as if it were a harmless typo fix, because nothing on GitHub distinguishes a README edit from an edit to the acceptance workflow.

4. **A durable, per-commit checkpoint record.** Every reviewed commit gets its own permanent record (in this repository, one PR comment per commit, plus a backup copy saved in the repository) naming what was reviewed and what was found. Earlier records for superseded commits are never edited or deleted. What breaks if skipped: there would be no way to tell, after the fact, exactly what evidence applied to which commit — especially once GitHub's own bots mark review conversation threads "resolved," which proves nothing about whether the underlying issue was actually fixed.

5. **Proof-based triage of findings.** A finding from any reviewer only counts as a confirmed, real defect once a failing test or a concrete reproduction demonstrates it. Everything else gets recorded honestly as a false positive (with the evidence) or as nonblocking debt (with the reason) — never silently assumed to be either. (The pilot's scorecards label that last group "unproven"; it is the same category.) What breaks if skipped: review output turns into noise, because nobody can tell which flagged items are real problems worth fixing and which are guesses.

6. **A scoped vibe-check policy, with an unchanged fallback.** "Vibe-check" here means a separate, heavier multi-specialist AI review pass, beyond BM and Codex. After this pilot, this repository's rule is: vibe-check is required when a checkpoint's risk is assessed high; it is not run routinely below high risk. At high risk there is one vibe-check for that commit, and the checkpoint record notes that it ran and where its report is. One thing is unchanged by that decision: whenever the independent Codex pass still cannot complete after its one retry, on any pull request, the owner may approve a vibe-check (or another independent reviewer) as the recorded stand-in for that exact commit. Bot and fork pull requests are the standing case where this is expected. What breaks if skipped: without the high-risk rule, the riskiest changes lose the reviewer that, in this pilot, caught problems the paired review missed; without the fallback, a pull request whose automated review genuinely cannot finish — for example because it's simply too large for one pass — would have no safety net left at all.

7. **A narrow, written procedure for relaying the owner's approval through the AI agent.** When the human owner wants to approve a specific commit by typing their decision in a chat session rather than clicking a button on GitHub, a written procedure defines exactly how that gets relayed: the agent must present the exact commit identifier and the completed review evidence first, never infer approval from "looks good" or "continue," and never reuse an approval for a different commit. What breaks if skipped: an AI agent could plausibly treat routine encouragement as if it were the specific approval decision, and GitHub would record the resulting approval from the owner's account exactly as if the owner had made it. GitHub enforces that the named account approved; only this procedure makes that approval the person's own decision.

8. **One branch and one pull request per unit of work, with no documentation-only pull requests.** Related planning, implementation, and evidence commits ride together inside one pull request rather than being split into several smaller ones. What breaks if skipped: more pull requests means more pushes, and pushes are the thing that consumes a limited budget of third-party review credits (see "Greptile's free-tier posture" under "What not to copy blindly" below) — unnecessary pull requests burn that budget for no benefit.

9. **Batched pushes.** Fixes from a review round are pushed together as one checkpoint rather than one commit at a time, and routine tracking or documentation commits are held locally until the next substantive push. What breaks if skipped: every push can trigger a fresh round of the same limited-budget review tooling and adds another checkpoint record to track, multiplying cost for no extra safety.

## What the pilot showed

This repository scored five real, already-authorized pull requests against the process above — no invented test cases; three were already merged and were scored afterwards from their committed review evidence, and two were run fresh — specifically to find out whether it actually works and whether the heavier "vibe-check" pass was still earning its cost. The full evidence, scorecards, and the owner's recorded decisions are in `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` (not reproduced here in full; this section only states the results in plain terms). That path is inside the current milestone's phase folder; when the milestone is archived the folder may move under `.planning/milestones/`, so look there if the path no longer resolves.

The five pull requests covered: a small fix, a larger security-sensitive change, another larger change (which turned out to be the pilot's most informative case, below), a state/error-handling logic fix, and a user-interface template change with no visible difference to end users.

**A controlled, fair comparison.** On one pull request's very first reviewed commit, vibe-check and the paired BM-plus-Codex review were both run independently, before either saw the other's output, specifically to compare what each one caught. Both found the exact same one real problem — neither missed something the other caught — but vibe-check took longer and ran roughly nine separate AI reviewer passes to the paired review's two, for the same result.

**Where vibe-check actually mattered.** On a different, much larger pull request (195 changed files), the independent Codex pass could not finish — twice — because the amount of changed code was too much for one review pass to get through. The owner approved a vibe-check as a stand-in for that pull request's review, and it found two real problems that neither BM's eight review rounds nor Codex's two incomplete attempts on that same pull request ever flagged. Both were traps in the repository's own automated checks rather than bugs users would see: a routine automated dependency update would have made required tests fail, which blocks every merge until someone fixes it, and one test read tool versions from a planning file that archiving the milestone would later have deleted. Neither was reproduced at the time; both were confirmed by reproduction when they were fixed in a follow-up pull request.

**On the other three pull requests,** vibe-check added nothing unique. On the security-sensitive change it ran once, on the final commit, and its one reported finding was a false positive. On the user-interface change it found nothing beyond a test-coverage observation that BM also made. It did not run on the small fix, which was assessed as moderate risk.

**Nobody's review ever silently passed an incomplete result.** On the one pilot pull request where Codex could not finish, the process caught that and routed to an owner-approved fallback review instead of reporting the pull request as cleanly reviewed.

**The owner's decisions (2026-11-14, recorded in the pilot record named above: its PILOT-03 decision lines and owner decisions log, plus its dated Corrections section):**

1. Running vibe-check automatically on every "code"-class change is retired. Vibe-check is required when a checkpoint's risk is assessed high; it is not run routinely below high risk. High risk is the one place this pilot actually showed it catching something the paired review missed. The fallback for a Codex pass that cannot complete (item 6 above) stays exactly as it was.
2. Checking that the independent reviewer's report actually arrived, is current, and covers the right commit stays a manual item on the human owner's acceptance checklist, rather than becoming something GitHub itself mechanically blocks on. The one time in this pilot that a report was genuinely incomplete, the existing manual checklist caught it — it was not missed — so there was no pilot evidence that this manual step needed to become an automated gate.

## What not to copy blindly

Everything below is specific to this repository, this moment, or this set of tools. Copy the pattern each item represents; do not copy the exact value.

- **This repository's exact ruleset ID and app IDs.** The branch ruleset above is a specific numbered object (its ID is particular to this repository's GitHub instance) and the required checks are tied to specific installed-app integration IDs. Another repository's equivalent ruleset and checks will have entirely different numeric IDs even when the setup is otherwise identical — set these up fresh per repository rather than reusing a number from here.
- **Greptile's free-tier posture.** This repository uses Greptile (a third-party automated-review GitHub app) on its free open-source tier, which has a limited number of reviews per billing period, and the owner's explicit decision not to buy paid credits when that runs out. Because of that limit, Greptile is treated as optional here — not a required check — and push batching exists partly to conserve that budget. Another repository might have no such tool, a different tool, a paid tier with no such limit, or a decision to make it a required check; decide this fresh rather than assuming "optional, free tier" applies elsewhere.
- **Solo-maintainer self-approval in the protected environment.** The protected acceptance environment's required reviewer is allowed to approve their own commits, because this repository currently has exactly one maintainer. On a repository with more than one contributor with write access, self-approval of your own change defeats the point of the gate; that repository should require a reviewer other than the change's author.
- **This repository's specific Codex model and tool-version pins, and its bot/fork limitation.** The independent Codex pass here is pinned to specific template, schema, and container-image versions, and its handling of untrusted (bot or fork) pull requests currently depends on a documented limitation — the default Codex model this repository uses is code-mode-only, which made one live review on an untrusted pull request come back incomplete, and the owner chose to keep the manual-fallback review rather than force a different model. Check the current state of whatever AI review tool you adopt at adoption time; do not assume the same limitation, or the same version pins, still apply.
- **This repository's own classification worked examples.** The content-based classification policy (the general idea of classifying by content, not file extension) is reusable; the specific worked examples and file-path lists in this repository's policy document (which files count as "sensitive" here, named by this repository's own paths) are particular to this codebase's layout and should be rewritten for the target repository's own file structure.
- **The pilot's one-PR-per-fix exception.** During this specific pilot, each new pilot fix shipped as its own separate pull request from the default branch, as a deliberate, recorded exception to this repository's normal one-PR-per-unit-of-work rule — done only so each small fix could get a clean, independently measurable scorecard. Do not adopt "one PR per fix" as a normal operating rule; it was a measurement-only exception for this one pilot.
- **This repository's specific required-check names and CI job structure.** "CI ready," "CodeQL," and "Review acceptance" are the names this repository's own workflows happen to report. Another repository's required-check list should reflect its own actual test/build/security jobs, named however that repository's workflows name them — don't require a check by a name that doesn't exist in the new repository.

## Adoption checklist

- [ ] Inventory the target repository first: language/stack, build and test commands, deployment target, current branch protections, and who actually has merge/approval authority.
- [ ] Turn on the AI assistant's own code review and choose a depth, then confirm with that tool's own version/status command that the setting actually took effect (don't assume enabling a setting alone proves every code path runs review).
- [ ] Write (or adapt, never blindly copy) a fixed, read-only review contract for an independent second AI reviewer: exact-commit scope, a required structured findings report, and a rule that a skipped, failed, or wrong-commit run is recorded as incomplete, never as clean.
- [ ] Wire that independent pass to run automatically after every first-pass code review, through supported configuration and written instructions — not a new custom orchestrator or a fork of the AI tool.
- [ ] Write a content-based classification policy for the target repository: what counts as ordinary documentation, what counts as a sensitive instruction/workflow/policy change (even in Markdown), and what counts as application code — using that repository's own file layout, not this one's.
- [ ] Create a GitHub branch-protection ruleset on the default branch: require pull requests, require the repository's own real status checks, and require branches to be up to date before merging.
- [ ] Create a protected GitHub Environment for final acceptance, with the actual human approver(s) set as required reviewers, a workflow job that requests a deployment to it, and a required-deployments rule in the ruleset naming it.
- [ ] Turn on CodeQL (or an equivalent static-analysis scanner for the target language) and add it to the required-status-checks list.
- [ ] Pin every third-party GitHub Action used in the repository's workflows to a full commit SHA, never a movable tag; turn on the repository's "Require actions to be pinned to a full-length commit SHA" Actions setting so GitHub enforces it; and consider a test that fails if a new unpinned action is ever added.
- [ ] Decide — and write down — whether a third-party review bot is in scope for this repository, on what tier, and whether it's a required check or disclosed-but-optional.
- [ ] Define a per-commit checkpoint-record template and where it lives (a PR comment plus a durable local copy, or a local evidence file before a PR exists), with a rule that earlier records are never edited or deleted.
- [ ] Define proof-based triage rules: a finding counts as confirmed only with a failing test or a reproduction; everything else is recorded as a false positive or as nonblocking debt, with the reason given.
- [ ] Decide the heavier-review (vibe-check-equivalent) policy for this repository from its own evidence; do not assume this repository's "required at high risk, not routine below it" outcome is the right starting point without running your own comparison first.
- [ ] If an AI agent will ever relay a human's spoken/typed approval to GitHub on their behalf, write a narrow transport procedure with the same safeguards used here: present the exact commit and evidence first, never infer approval, never reuse it for a different commit, and re-verify immediately before submitting.
- [ ] Run a small pilot — three to five real pull requests already authorized for other reasons, not invented test cases — before trusting the new process, and record what each reviewer actually caught, missed, and cost.
- [ ] Demonstrate at least one negative case during the pilot: a genuinely missing, stale, or wrong-commit piece of review evidence should visibly block acceptance, not pass silently as "clean."
