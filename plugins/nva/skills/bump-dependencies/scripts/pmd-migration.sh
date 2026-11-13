#!/usr/bin/env bash
#
# pmd-migration.sh
#
# Compares a repository's own PMD ruleset (config/pmd/ruleset.xml) with the
# ruleset bundled in a nva-gradle-plugins release, and prints what the switch
# to `nva.pmd.excludedRules` means for that repository. Read-only.
#
# Sections printed:
#   excludedRules   rules the local ruleset excludes that the bundled one does
#                   not, as a ready-to-paste Groovy list
#   redundant       local excludes the bundled ruleset already has (drop them)
#   loosened        rules the local ruleset ran that the bundled one excludes
#   activated       PMD categories the bundled ruleset runs that the local one
#                   never referenced; expect new violations from these
#   lost            categories the local ruleset referenced that the bundled
#                   one does not (e.g. security.xml)
#   tests           whether the local ruleset skipped test sources, which maps
#                   to `analyzeTests = false`
#
# Renamed or replaced rules are mapped to their current name before comparing
# (UseUtilityClass -> InstantiableUtilityClass,
# UnnecessaryLocalBeforeReturn -> VariableCanBeInlined).
#
# Usage:
#   ./pmd-migration.sh <repository-dir> [plugins-version] [local-ruleset]
#
# plugins-version defaults to the latest nva-gradle-plugins release on GitHub.
# local-ruleset defaults to <repository-dir>/config/pmd/ruleset.xml.
#
# Requirements: gh (authenticated).
#
set -euo pipefail

if [[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  grep -E '^#( |$)' "$0" | sed -E 's/^# ?//'
  exit 0
fi

repository_dir=$1
plugins_repository=BIBSYSDEV/nva-gradle-plugins
plugins_version=${2:-$(gh api "repos/$plugins_repository/releases/latest" --jq .tag_name)}
plugins_version=v${plugins_version#v}
local_ruleset=${3:-$repository_dir/config/pmd/ruleset.xml}

if [[ ! -f "$local_ruleset" ]]; then
  echo "No local ruleset at $local_ruleset; nothing to migrate." >&2
  exit 0
fi

bundled_ruleset=$(gh api -H 'Accept: application/vnd.github.raw' \
  "repos/$plugins_repository/contents/src/main/resources/pmd-ruleset.xml?ref=$plugins_version")

# Rules PMD has renamed or replaced; the local ruleset may still use the old name.
rename_rules() {
  sed -E -e 's/^UseUtilityClass$/InstantiableUtilityClass/' \
    -e 's/^UnnecessaryLocalBeforeReturn$/VariableCanBeInlined/'
}

excluded_rules() {
  grep -oE '<exclude name="[^"]+"' | sed -E 's/.*name="//; s/"$//' | rename_rules | sort -u
}

categories() {
  grep -oE 'rule ref="category/java/[a-z]+\.xml"' | sed -E 's/.*category\/java\///; s/\.xml"$//' | sort -u
}

local_excludes=$(excluded_rules < "$local_ruleset")
bundled_excludes=$(echo "$bundled_ruleset" | excluded_rules)
local_categories=$(categories < "$local_ruleset")
bundled_categories=$(echo "$bundled_ruleset" | categories)

carry_over=$(comm -23 <(echo "$local_excludes") <(echo "$bundled_excludes"))
redundant=$(comm -12 <(echo "$local_excludes") <(echo "$bundled_excludes"))
loosened=$(comm -13 <(echo "$local_excludes") <(echo "$bundled_excludes"))
activated=$(comm -13 <(echo "$local_categories") <(echo "$bundled_categories"))
lost=$(comm -23 <(echo "$local_categories") <(echo "$bundled_categories"))

echo "== $local_ruleset vs bundled ruleset in nva-gradle-plugins $plugins_version =="
echo
echo "excludedRules (paste into nva { pmd { ... } }):"
if [[ -n "$carry_over" ]]; then
  echo "        excludedRules = ["
  echo "$carry_over" | sed -E "s/^(.*)$/                '\1',/" | sed '$ s/,$//'
  echo "        ]"
else
  echo "        (none: the bundled ruleset covers every local exclude)"
fi
echo
echo "redundant (already excluded by the bundled ruleset):"
echo "${redundant:-  (none)}" | sed -E 's/^([A-Za-z])/  \1/'
echo
echo "loosened (ran locally, excluded by the bundled ruleset):"
echo "${loosened:-  (none)}" | sed -E 's/^([A-Za-z])/  \1/'
echo
echo "activated (categories the local ruleset never referenced):"
echo "${activated:-  (none)}" | sed -E 's/^([A-Za-z])/  \1/'
echo
echo "lost (categories the bundled ruleset does not run):"
echo "${lost:-  (none)}" | sed -E 's/^([A-Za-z])/  \1/'
echo
echo "tests:"
if grep -q "<exclude-pattern>.*test" "$local_ruleset"; then
  echo "  local ruleset skips test sources; set analyzeTests = false to keep that, or leave it on and fix what PMD finds in the tests"
else
  echo "  local ruleset analyzed test sources, same as the default (analyzeTests = true)"
fi
