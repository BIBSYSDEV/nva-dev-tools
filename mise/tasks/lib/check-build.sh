# Sourced by the check and build tasks, not run on its own: the repo detection they share.
# Both declare a --dry-run flag, which mise hands over as usage_dry_run.

dry_run=${usage_dry_run:-false}
matched=false

run() {
  matched=true
  if [[ "$dry_run" == "true" ]]; then
    echo "would run: $*"
  else
    echo "+ $*"
    "$@"
  fi
}

has_npm_script() {
  node -e 'process.exit(require("./package.json").scripts?.[process.argv[1]] ? 0 : 1)' "$1"
}

pyproject_lists() {
  grep -q "\"$1[>=<~ \"]" pyproject.toml
}
