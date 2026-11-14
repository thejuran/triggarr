#!/usr/bin/env bash
# Self-test for the Phase 86 publication gate (86-01 Task 3).
# Usage, from anywhere: bash <this file> <path to 86-publication-gate.sh>
# Builds throwaway git repositories under mktemp and checks clean, matching,
# unreadable-file and empty-list cases, the credential-shape hand-review entry
# rules (exact path, dedicated section, accepted disposition only), a staged
# match hidden by an unstaged redaction, plus invocation from zsh.
gate=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
[ -f "$gate" ] || { echo "selftest: gate script not found: $1" >&2; exit 2; }
p=.planning/phases/86-pilot-reference-record
pass=0; bad=0; dirs=()
trap 'chmod -R u+rw "${dirs[@]}" 2>/dev/null; rm -rf "${dirs[@]}"' EXIT
check() { name=$1; want=$2; reason=$3; shift 3
  out=$( cd "$r" && "$@" 2>&1 >/dev/null ); got=$?
  if [ "$want" = pass ] && [ "$got" -eq 0 ]; then ok=1
  elif [ "$want" = block ] && [ "$got" -ne 0 ] && printf '%s' "$out" | grep -qF -e "$reason"; then ok=1
  else ok=0; fi
  if [ "$ok" -eq 1 ]; then echo "ok   $name"; pass=$((pass+1))
  else echo "FAIL $name (wanted $want '$reason', exit $got: $out)"; bad=$((bad+1)); fi; }
expect() { check "$1" "$2" "$3" bash "$gate" "$p"; }
fresh() { r=$(mktemp -d) || exit 2; dirs+=("$r")
  ( cd "$r" && git init -q && mkdir -p "$p/codex" "$p/vibe-check" \
    && echo "clean codex output" > "$p/codex/a1.txt" && echo "clean vibe report" > "$p/vibe-check/v.md" \
    && printf '# Evidence\n\n## Credential-shape hand review\n\nnone\n' > "$p/86-REVIEW-EVIDENCE.md" \
    && echo "# Record" > "$p/86-PILOT-RECORD.md" && git add -A ) || exit 2; }
fresh; expect "clean set passes" pass ""
fresh; check "clean set passes when invoked from zsh" pass "" zsh -c "bash '$gate' '$p'"
fresh; echo "see /home/someone/x" >> "$r/$p/vibe-check/v.md"; expect "local path blocks" block "public-infrastructure check: matching"
fresh; check "local path blocks when invoked from zsh" block "public-infrastructure check: matching" \
  zsh -c "echo 'box.ts.net' >> '$p/86-PILOT-RECORD.md' && bash '$gate' '$p'"
fresh; whoami >> "$r/$p/codex/a1.txt"; expect "user name blocks" block "local user name check: matching"
fresh; hostname -s >> "$r/$p/codex/a1.txt"; expect "host name blocks" block "local host name check: matching"
hit() { fresh; printf 'id %s\n' "$(printf '%032d' 0 | tr 0 a)" >> "$r/$p/codex/a1.txt"; }
ev() { printf -- "$1\n" >> "$r/$p/86-REVIEW-EVIDENCE.md"; }
A="\`$p/codex/a1.txt\`"; NO="no accepted Credential-shape hand review entry"
hit; expect "unreviewed 32-hex hit blocks" block "$NO"
ev "- $A: not a credential -- test fixture id, not an API key"; ( cd "$r" && git add -A )
expect "accepted entry for the exact path passes" pass ""
hit; ev "Codex output in $p/codex/a1.txt and a1.txt was read."
ev "## Refresh-counts PR"; ev "See $A for the transcript."; expect "ordinary citation of the path blocks" block "$NO"
hit; ev "## Withheld files"; ev "- $A: not a credential -- wrong section"; expect "accepted entry outside the section blocks" block "$NO"
hit; ev "- $A: credential -- withheld, owner told to rotate"; expect "rejected entry blocks" block "$NO"
hit; ev "- $A: pending hand review"; expect "unreviewed (pending) entry blocks" block "$NO"
hit; ev "- $A: not a credential -- fixture"; ev "- $A: credential -- second look"; expect "accepted plus rejected entry blocks" block "$NO"
hit; ev "- $A: not a credential -- "; expect "accepted entry with no reason blocks" block "$NO"
hit; ev "- \`$p/vibe-check/a1.txt\`: not a credential -- other file"; expect "same-basename different-file entry blocks" block "$NO"
hit; ev "- \`a1.txt\`: not a credential -- basename only"; expect "basename-only entry blocks" block "$NO"
hit; ev "- $A: not a credential -- fixture"; ev "## Credential-shape hand review"; expect "duplicate hand-review section blocks" block "exactly one"
fresh; printf 'token = "%s%s"\n' "gh""p_" "x7Qp2LmZ9sKt4VwR8yB3nC6dF1gH5jA0eU2i" >> "$r/$p/codex/a1.txt"
expect "gitleaks finding blocks" block "gitleaks exit 1"
fresh; chmod 000 "$r/$p/vibe-check/v.md"; expect "unreadable file blocks (grep exit 2)" block "grep error (exit 2)"
fresh; rm "$r/$p/codex/a1.txt"; expect "tracked file missing from worktree blocks" block "grep error (exit 2)"
r=$(mktemp -d); dirs+=("$r"); ( cd "$r" && git init -q ); expect "empty file list blocks" block "no tracked review artifacts"
fresh; ( cd "$r" && git mv "$p/vibe-check/v.md" "$p/vibe-check/v two.md" ); expect "file name with a space passes" pass ""
echo "see /Users/x" >> "$r/$p/vibe-check/v two.md"; expect "file name with a space blocks" block "public-infrastructure check: matching"
fresh; echo "see /home/someone/x" >> "$r/$p/vibe-check/v.md"; ( cd "$r" && git add -A ); echo "clean vibe report" > "$r/$p/vibe-check/v.md"
expect "staged match with a redacted working copy blocks" block "index and working tree differ"
( cd "$r" && git add -A ); expect "passes once the redacted copy is staged" pass ""
echo "selftest: $pass passed, $bad failed"; [ "$bad" -eq 0 ]
