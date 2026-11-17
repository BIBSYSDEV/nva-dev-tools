#!/usr/bin/env bash
#
# outdated-actions.sh
#
# Lists every GitHub Action used in a repository's workflows together with the
# newest release of that action that is at least COOLDOWN_DAYS old (default 7),
# so the SHA pins and their version comments can be updated. Read-only: it
# never edits a workflow.
#
# For each unique "uses: owner/repo[/path]@ref" it prints one line:
#
#   <status>  <owner/repo[/path]>  <current ref>  <current comment>  <target tag>  <target commit>  [(newest X within cooldown)]
#
# where status is one of
#   up-to-date  the pinned commit is the one the target release tag points to
#   outdated    a newer eligible release exists; replace the SHA and the comment
#   unpinned    the ref is a tag or branch, not a commit SHA; pin it
#   branch      a reusable workflow referenced by branch (e.g. @v2); check its README instead
#   no-release  the repository publishes no releases or tags; inspect by hand
#
# Usage:
#   ./outdated-actions.sh [repository-dir]      default: current directory
#
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  grep -E '^#( |$)' "$0" | sed -E 's/^# ?//'
  exit 0
fi

repository_dir=${1:-.}
workflows_dir="$repository_dir/.github/workflows"

if [[ ! -d "$workflows_dir" ]]; then
  echo "No workflows directory at $workflows_dir" >&2
  exit 1
fi

cooldown_days=${COOLDOWN_DAYS:-7}
cutoff=$(date -u -v-"${cooldown_days}"d +%Y-%m-%d 2>/dev/null || date -u -d "$cooldown_days days ago" +%Y-%m-%d)

highest_version() {
  sort -V | tail -n 1
}

# Succeeds when the first version is higher than the second. A leading v is
# ignored, and versions with different prefixes (release-1.3.0 against 1.2.0,
# or a comment that is no version at all) are never compared.
is_higher_version() {
  local candidate=${1#v} reference=${2#v}
  [[ "${candidate%%[0-9]*}" == "${reference%%[0-9]*}" && "$candidate" != "$reference" ]] || return 1
  [[ "$(printf '%s\n' "$candidate" "$reference" | highest_version)" == "$candidate" ]]
}

# Prints "<target> <newest> <pinned-is-newer>": the highest stable release
# published on or before the cutoff, the highest release overall, and 1 when
# the currently pinned release (by its version comment) is higher than the
# target, so the caller never proposes a downgrade. Versions are compared
# instead of trusting the order GitHub lists releases in, where a backport to
# an older major can come before the newest release. Repositories without
# releases fall back to their newest tag, which has no publish date, so no
# cooldown applies there.
latest_tag() {
  local repo=$1 pinned=$2 releases target newest pinned_is_newer=0
  releases=$(gh api "repos/$repo/releases?per_page=30" \
    --jq '.[] | select(.draft == false and .prerelease == false) | "\(.tag_name) \(.published_at[0:10])"' 2>/dev/null || true)
  if [[ -n "$releases" ]]; then
    target=$(echo "$releases" | awk -v cutoff="$cutoff" '$2 <= cutoff { print $1 }' | highest_version)
    [[ -z "$target" ]] && return 0
    newest=$(echo "$releases" | cut -d' ' -f1 | highest_version)
    if is_higher_version "$pinned" "$target"; then
      pinned_is_newer=1
    fi
    echo "$target $newest $pinned_is_newer"
    return
  fi
  local tag
  tag=$(gh api "repos/$repo/tags?per_page=1" --jq '.[0].name' 2>/dev/null || true)
  [[ -n "$tag" ]] && echo "$tag $tag 0"
}

tag_commit() {
  local repo=$1 tag=$2 tag_ref object_type object_sha
  tag_ref=$(gh api "repos/$repo/git/ref/tags/$tag" --jq '"\(.object.type) \(.object.sha)"' 2>/dev/null) || return 0
  read -r object_type object_sha <<< "$tag_ref"
  if [[ "$object_type" == "tag" ]]; then
    gh api "repos/$repo/git/tags/$object_sha" --jq .object.sha
  else
    echo "$object_sha"
  fi
}

# One line per unique uses: value, with its trailing comment if any.
grep -rhoE 'uses:[[:space:]]*[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[^[:space:]]+([[:space:]]*#[[:space:]]*[^[:space:]]+)?' \
  "$workflows_dir" \
  | sed -E 's/^uses:[[:space:]]*//' \
  | sort -u \
  | while IFS= read -r line; do
    uses_value=${line%%[[:space:]]*}
    comment=$(echo "$line" | grep -oE '#[[:space:]]*[^[:space:]]+' | sed -E 's/^#[[:space:]]*//' || true)
    action=${uses_value%@*}
    ref=${uses_value##*@}
    repo=$(echo "$action" | cut -d/ -f1-2)

    if [[ "$action" == *".github/workflows/"* ]]; then
      printf '%-11s %s  %s  %s\n' "branch" "$action" "$ref" "${comment:--}"
      continue
    fi

    read -r tag newest pinned_is_newer <<< "$(latest_tag "$repo" "${comment:-}")"
    if [[ -z "${tag:-}" ]]; then
      printf '%-11s %s  %s  %s  -  -\n' "no-release" "$action" "$ref" "${comment:--}"
      continue
    fi
    commit=$(tag_commit "$repo" "$tag")
    cooldown_note=""
    [[ "$newest" != "$tag" ]] && cooldown_note="  (newest $newest within cooldown)"

    if [[ ! "$ref" =~ ^[0-9a-f]{40}$ ]]; then
      status="unpinned"
    elif [[ "$ref" == "$commit" || "$pinned_is_newer" == "1" ]]; then
      status="up-to-date"
    else
      status="outdated"
    fi
    printf '%-11s %s  %s  %s  %s  %s%s\n' "$status" "$action" "$ref" "${comment:--}" "$tag" "${commit:--}" "$cooldown_note"
  done
