#!/usr/bin/env bash
# Shared commit policy used by the commit-msg hook and by CI (scripts/check-authorship.sh).
# Source this file; it defines functions only.

policy_root() { git rev-parse --show-toplevel; }

# Prints "name<TAB>email" from .github/allowed-author ("Name <email>").
allowed_identity() {
  local line
  line="$(grep -Ev '^\s*(#|$)' "$(policy_root)/.github/allowed-author" | head -n1)"
  printf '%s\t%s\n' "$(sed -E 's/^(.*) <.*>$/\1/' <<<"$line")" "$(sed -E 's/^.*<([^>]+)>.*$/\1/' <<<"$line")"
}

# Conventional Commit title, plus git-generated Merge and Revert titles.
TITLE_RE='^((feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|security)(\([a-z0-9._/-]+\))?!?: [^[:space:]].{0,70}|Merge .+|Revert ".+")$'

# check_message <file>: rejects trailers and bad titles. Returns 1 on violation.
check_message() {
  local file="$1" title
  if grep -Eiq '^\s*Co-authored-by:' "$file"; then
    echo "Rejected: Co-authored-by trailers are not allowed." >&2; return 1
  fi
  if grep -Eiq '^\s*(Signed-off-by|Generated-by|Assisted-by):.*(claude|copilot|gpt|bot|ai\b)' "$file"; then
    echo "Rejected: tool attribution trailers are not allowed." >&2; return 1
  fi
  title="$(grep -Ev '^\s*(#|$)' "$file" | head -n1 | tr -d '\r')"
  if [[ ! "$title" =~ $TITLE_RE ]]; then
    echo "Rejected: title must be a Conventional Commit, e.g. 'fix(app): reject empty titles' (max 72 chars). Got: '$title'" >&2
    return 1
  fi
}

# check_identity <name> <email>: compares against .github/allowed-author.
check_identity() {
  local want_name want_email
  IFS=$'\t' read -r want_name want_email < <(allowed_identity)
  if [[ "$1" != "$want_name" ]]; then echo "Rejected: author name must be $want_name (got '$1')." >&2; return 1; fi
  if [[ "$2" != "$want_email" ]]; then echo "Rejected: author email does not match .github/allowed-author." >&2; return 1; fi
}
