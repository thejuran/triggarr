#!/usr/bin/env bash
# Phase 86 evidence publication gate re-check (86-01 Task 3).
# Run from the repository root, always through bash: bash <this file> [phase-dir]
# Exit 0 only when every tracked review artifact passes. Any match, read error,
# tool error or empty file list exits non-zero (fails closed).
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
nohit "public-infrastructure check" -E '/Users/|/home/|\.ts\.net|tailnet|tailscale'
nohit "local user name check" -F -e "$u"
nohit "local host name check" -F -e "$h"
hx=$(grep -lE '(^|[^0-9a-f])[0-9a-f]{32}([^0-9a-f]|$)' -- "${F[@]}"); r=$?
[ "$r" -le 1 ] || fail "32-hex scan: grep error (exit $r)"
# A hit passes only with an accepted entry for its exact repository-relative path
# inside the one "## Credential-shape hand review" section of 86-REVIEW-EVIDENCE.md:
#   - `<path>`: not a credential -- <reason>
# Any other line in that section naming the same path (rejected, pending) blocks.
ev="$d/86-REVIEW-EVIDENCE.md"
reviewed() { X=$1 awk '
  BEGIN { k = "- `" ENVIRON["X"] "`"; p = k ": not a credential -- " }
  /^## / { ins = ($0 == "## Credential-shape hand review"); n += ins; next }
  ins && substr($0, 1, length(p)) == p && substr($0, length(p) + 1) ~ /[^[:space:]]/ { ok = 1; next }
  ins && substr($0, 1, length(k)) == k { bad = 1 }
  END { if (n != 1) exit 3; exit (ok && !bad) ? 0 : 1 }' "$ev"; }
while IFS= read -r x; do
  [ -n "$x" ] || continue
  reviewed "$x"; r=$?
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
echo "publication gate: PASS (${#F[@]} tracked artifacts)"
