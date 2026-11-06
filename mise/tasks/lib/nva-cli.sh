# Sourced by the pipeline tasks, not run on its own: how to reach nva-aws-cli-tools.
# NVA_CLI is a command line (see mise/README.md), word-split once, with ~/ expanded since mise leaves it alone in [env].

read -ra nva_cli_command <<< "${NVA_CLI:?Set NVA_CLI to the nva-aws-cli-tools command in your mise config (see mise/README.md)}"
nva_cli_command=("${nva_cli_command[@]/#\~\//$HOME/}")

nva_cli() {
  "${nva_cli_command[@]}" "$@"
}
