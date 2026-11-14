#!/usr/bin/env bash
# Phase 86 evidence publication gate re-check (86-01 Task 3).
# Run from the repository root, always through bash: bash <this file> [phase-dir]
# Exit 0 only when every tracked review artifact passes. Any match, read error,
# tool error, empty file list or staged content that differs from the scanned
# working copy exits non-zero (fails closed). Two checks accept a written hand
# review from 86-REVIEW-EVIDENCE.md: the public-infrastructure check (entry bound
# to the file's exact path and current SHA-256) and the 32-hex check (exact path).
# The local user name and local host name checks have no exception.
d=${1:-.planning/phases/86-pilot-reference-record}
fail() { echo "publication gate BLOCKED: $*" >&2; exit 1; }
command -v gitleaks >/dev/null 2>&1 || fail "gitleaks not installed"
t=$(mktemp -d) || fail "mktemp failed"
trap 'rm -rf "$t"' EXIT
git ls-files -z -- "$d/codex" "$d/vibe-check" "$d/86-REVIEW-*.md" "$d/86-PILOT-RECORD.md" > "$t/list" \
  || fail "git ls-files failed"
F=()
while IFS= read -r -d '' f; do F+=("$f"); done < "$t/list"
[ "${#F[@]}" -gt 0 ] || fail "no tracked review artifacts under $d"
# grep exit codes: 0 = match (block), 1 = no match (pass), 2+ = error such as an unreadable file (block)
nohit() { label=$1; shift; grep -l "$@" -- "${F[@]}"; r=$?
  [ "$r" -eq 1 ] && return 0
  [ "$r" -eq 0 ] && fail "$label: matching files listed above"
  fail "$label: grep error (exit $r)"; }
u=$(whoami) && [ -n "$u" ] || fail "whoami failed"
h=$(hostname -s) && [ -n "$h" ] || fail "hostname failed"
# Hand-review exceptions (public-infrastructure and 32-hex hits only). A hit passes only
# with an accepted entry for its exact repository-relative path inside the one matching
# section of 86-REVIEW-EVIDENCE.md:
#   ## Public-infrastructure hand review
#   - `<path>` sha256 `<64-hex of the file as scanned>`: not private infrastructure -- <reason>
#   ## Credential-shape hand review
#   - `<path>`: not a credential -- <reason>
# Any other line in that section starting with the same path (rejected, pending) blocks.
ev="$d/86-REVIEW-EVIDENCE.md"
reviewed() { X=$1 S=$2 M=$3 awk '
  BEGIN { k = "- `" ENVIRON["X"] "`"; p = k ENVIRON["M"] }
  /^## / { ins = ($0 == "## " ENVIRON["S"]); n += ins; next }
  ins && substr($0, 1, length(p)) == p && substr($0, length(p) + 1) ~ /[^[:space:]]/ { ok = 1; next }
  ins && substr($0, 1, length(k)) == k { bad = 1 }
  END { if (n != 1) exit 3; exit (ok && !bad) ? 0 : 1 }' "$ev"; }
sha() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 < "$1"
  elif command -v sha256sum >/dev/null 2>&1; then sha256sum < "$1"; fi | cut -d' ' -f1; }
px=$(grep -lE '/Users/|/home/|\.ts\.net|tailnet|tailscale' -- "${F[@]}"); r=$?
[ -z "$px" ] || printf '%s\n' "$px"
[ "$r" -le 1 ] || fail "public-infrastructure check: grep error (exit $r)"
nb=0; ps="Public-infrastructure hand review"
while IFS= read -r x; do
  [ -n "$x" ] || continue
  s=$(sha "$x"); [[ "$s" =~ ^[0-9a-f]{64}$ ]] || fail "public-infrastructure hit: cannot hash (needs shasum or sha256sum): $x"
  reviewed "$x" "$ps" " sha256 \`$s\`: not private infrastructure -- "; r=$?
  [ "$r" -eq 0 ] && continue
  nb=1
  if [ "$r" -eq 3 ]; then echo "public-infrastructure hit, but 86-REVIEW-EVIDENCE.md needs exactly one '## $ps' section: $x" >&2
  elif [ "$r" -eq 1 ]; then echo "public-infrastructure hit has no accepted $ps entry: $x" >&2
  else fail "public-infrastructure hit: cannot read $ev (exit $r): $x"; fi
done <<< "$px"
[ "$nb" -eq 0 ] || fail "public-infrastructure check: matching files listed above lack an accepted, hash-matching hand review entry"
nohit "local user name check" -F -e "$u"
nohit "local host name check" -F -e "$h"
hx=$(grep -lE '(^|[^0-9a-f])[0-9a-f]{32}([^0-9a-f]|$)' -- "${F[@]}"); r=$?
[ "$r" -le 1 ] || fail "32-hex scan: grep error (exit $r)"
while IFS= read -r x; do
  [ -n "$x" ] || continue
  reviewed "$x" "Credential-shape hand review" ": not a credential -- "; r=$?
  [ "$r" -eq 0 ] && continue
  [ "$r" -eq 3 ] && fail "32-hex hit, but 86-REVIEW-EVIDENCE.md needs exactly one '## Credential-shape hand review' section: $x"
  [ "$r" -eq 1 ] && fail "32-hex hit has no accepted Credential-shape hand review entry: $x"
  fail "32-hex hit: cannot read $ev (exit $r): $x"
done <<< "$hx"
mkdir "$t/copy" || fail "mkdir failed"
for f in "${F[@]}"; do
  { mkdir -p "$t/copy/$(dirname "$f")" && cp -- "$f" "$t/copy/$f"; } || fail "copy failed: $f"
done
gitleaks detect --no-git --redact --source "$t/copy" >/dev/null 2>&1; r=$?
[ "$r" -eq 0 ] || fail "gitleaks exit $r (1 = finding, other = error)"
# Every check above read the working tree, but a commit publishes the index. A covered
# path whose staged content differs from its working copy was not scanned as it will be
# committed, so it blocks (git diff exit codes: 0 = same, 1 = differs, other = error).
git diff --name-only --exit-code -- "${F[@]}"; r=$?
[ "$r" -ne 1 ] || fail "index and working tree differ for the files listed above: stage the scanned content, then re-run"
[ "$r" -eq 0 ] || fail "git diff error (exit $r)"
echo "publication gate: PASS (${#F[@]} tracked artifacts)"
