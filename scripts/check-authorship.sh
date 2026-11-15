#!/usr/bin/env bash
# CI check: every commit in RANGE has the allowed author and committer, a valid title and no trailers.
# Usage: scripts/check-authorship.sh <base>..<head>   (default: all commits on HEAD)
# Exception: commits authored by dependabot[bot] on dependabot/* branches (see docs/known-limitations.md).
set -euo pipefail
range="${1:-HEAD}"
# shellcheck source=scripts/lib/commit-policy.sh
source "$(git rev-parse --show-toplevel)/scripts/lib/commit-policy.sh"
fail=0; tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
while IFS=$'\t' read -r sha an ae cn ce; do
  if [[ "$an" == "dependabot[bot]" && "${GITHUB_HEAD_REF:-}" == dependabot/* ]]; then
    echo "SKIP ${sha:0:7} dependabot exception"; continue
  fi
  git log -1 --format=%B "$sha" > "$tmp"
  if check_message "$tmp" && check_identity "$an" "$ae" && { [[ "$cn" == "GitHub" ]] || check_identity "$cn" "$ce"; }; then
    echo "PASS ${sha:0:7}"
  else
    echo "FAIL ${sha:0:7}"; fail=1
  fi
done < <(git log --no-merges --format='%H%x09%an%x09%ae%x09%cn%x09%ce' "$range")
exit "$fail"
