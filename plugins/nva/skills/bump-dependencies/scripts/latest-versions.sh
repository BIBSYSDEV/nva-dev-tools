#!/usr/bin/env bash
#
# latest-versions.sh
#
# Prints the target version of each tool and library the bump workflow
# moves, one per line as "<name> <version>". Read-only.
#
# External tools get a 7-day cooldown: the printed version is the newest
# release that is at least COOLDOWN_DAYS old (default 7, override with the
# environment variable), and a newer release inside the cooldown is named
# after it in parentheses so the reader knows why the target is not the very
# latest. nva-commons and nva-gradle-plugins are released by the team and
# have no cooldown. The first line, "cooldown-cutoff <date>", is the date to
# pass on to tools that enforce the cooldown themselves (uv --exclude-newer).
#
# Runtimes get two lines each:
#   <language>         the newest release (Java: newest Corretto LTS,
#                      Node: newest LTS, Python: newest feature release)
#   <language>-lambda  the newest runtime that is generally available on
#                      AWS Lambda, followed by the eligible patch release of
#                      that version. endoflife.date lists only GA Lambda
#                      runtimes, so runtimes in public preview are left out
#                      on purpose.
# Code that runs on Lambda cannot go past the -lambda line.
#
# Requirements: curl, jq, mise.
#
set -euo pipefail

cooldown_days=${COOLDOWN_DAYS:-7}
cutoff=$(date -u -v-"${cooldown_days}"d +%Y-%m-%d 2>/dev/null || date -u -d "$cooldown_days days ago" +%Y-%m-%d)
echo "cooldown-cutoff $cutoff"

endoflife() {
  curl -sf "https://endoflife.date/api/$1.json"
}

maven_latest() {
  curl -sf "https://repo1.maven.org/maven2/$1/maven-metadata.xml" | grep -o '<latest>[^<]*' | cut -d'>' -f2
}

# The newest release of a mise tool (node@24 limits it to that major) that is
# past the cooldown, the same lookup the gradle:upgrade-wrapper task uses.
# mise compares versions as numbers, so a patch for an older major, which
# Gradle ships, never wins over the newer major.
past_cooldown() {
  local eligible newest
  eligible=$(mise latest "$1" --minimum-release-age "${cooldown_days}d")
  newest=$(mise latest "$1")
  if [[ -z "$eligible" ]]; then
    echo "none-eligible (newest $newest)"
  elif [[ "$eligible" == "$newest" ]]; then
    echo "$eligible"
  else
    echo "$eligible (newest $newest, within cooldown)"
  fi
}

lambda_runtimes=$(endoflife aws-lambda)

lambda_newest() {
  local cycle_pattern=$1 version_of_cycle=$2
  echo "$lambda_runtimes" | jq -r "[.[].cycle | select(test(\"$cycle_pattern\"))] | sort_by($version_of_cycle) | last"
}

echo "gradle $(past_cooldown gradle)"
echo "nva-commons $(maven_latest com/github/bibsysdev/versions) (no cooldown)"
echo "nva-gradle-plugins $(maven_latest com/github/bibsysdev/nva-gradle-plugins) (no cooldown)"
echo "uv $(past_cooldown uv)"

java_lts=$(endoflife amazon-corretto | jq -r '[.[] | select(.lts == true)][0].cycle')
java_lambda=$(lambda_newest '^java[0-9]+$' 'ltrimstr("java") | tonumber')
echo "java $java_lts"
echo "java-lambda $java_lambda"

node_lts_major=$(endoflife nodejs | jq -r '[.[] | select(.lts != false)][0].cycle')
node_lambda=$(lambda_newest '^nodejs[0-9]+\\.x$' 'ltrimstr("nodejs") | rtrimstr(".x") | tonumber')
node_lambda_major=${node_lambda#nodejs}
node_lambda_major=${node_lambda_major%.x}
echo "node $(past_cooldown "node@$node_lts_major")"
echo "node-lambda $node_lambda $(past_cooldown "node@$node_lambda_major")"

python_newest_minor=$(endoflife python | jq -r '.[0].cycle')
python_lambda=$(lambda_newest '^python3\\.[0-9]+$' 'split(".")[1] | tonumber')
echo "python $(past_cooldown "python@$python_newest_minor")"
echo "python-lambda $python_lambda $(past_cooldown "python@${python_lambda#python}")"
