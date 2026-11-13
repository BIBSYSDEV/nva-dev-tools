#!/usr/bin/env bash
#
# nva-commons-changes.sh
#
# Shows what changed in nva-commons between two released versions: the commits
# on main, and the diff of the shared version catalog (what nvaCatalog gains,
# loses or bumps). Read-only; it only fetches.
#
# nva-commons has no release tags. A release is the commit that set
# VERSION_NAME=<version> in gradle.properties, which this script locates on
# origin/main.
#
# Usage:
#   ./nva-commons-changes.sh <old-version> <new-version> [nva-commons-checkout]
#
# The checkout defaults to the nva-commons clone in $NVA_REPOS_DIR (default
# ~/projects/nva). Any clone layout works, since the script only runs git.
#
set -euo pipefail

if [[ $# -lt 2 || "$1" == "-h" || "$1" == "--help" ]]; then
  grep -E '^#( |$)' "$0" | sed -E 's/^# ?//'
  exit 0
fi

old_version=$1
new_version=$2
repos_dir=${NVA_REPOS_DIR:-$HOME/projects/nva}
# mise leaves a leading ~ in [env] values as it is
repos_dir=${repos_dir/#\~\//$HOME/}
checkout=${3:-$repos_dir/nva-commons}

if [[ ! -d "$checkout/.git" && ! -f "$checkout/.git" ]]; then
  echo "No nva-commons checkout at $checkout" >&2
  exit 1
fi

git -C "$checkout" fetch --quiet origin

release_commit() {
  git -C "$checkout" log origin/main -S"VERSION_NAME=$1" --format=%H -- gradle.properties | tail -1
}

old_commit=$(release_commit "$old_version")
new_commit=$(release_commit "$new_version")

if [[ -z "$old_commit" || -z "$new_commit" ]]; then
  echo "Could not find a commit setting VERSION_NAME for ${old_commit:+$new_version}${old_commit:-$old_version} on origin/main" >&2
  exit 1
fi

echo "== nva-commons $old_version ($old_commit) -> $new_version ($new_commit) =="
echo
echo "Commits:"
git -C "$checkout" log --oneline --first-parent "$old_commit..$new_commit"
echo
echo "Catalog diff (gradle/libs.versions.toml):"
git -C "$checkout" diff --no-color "$old_commit" "$new_commit" -- gradle/libs.versions.toml | grep -E '^[+-][^+-]' || echo "(no catalog changes)"
