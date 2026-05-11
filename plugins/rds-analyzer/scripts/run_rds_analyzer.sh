#!/usr/bin/env bash
# Helper to run rds-analyzer for common scenarios from docs/full-workflow.md.
# Usage: run_rds_analyzer.sh <subcommand> [options passed to rds-analyzer...]
# Environment:
#   RDS_ANALYZER_BIN  Path to rds-analyzer binary (default: rds-analyzer)

set -euo pipefail

BIN="${RDS_ANALYZER_BIN:-rds-analyzer}"

usage() {
  sed -n '1,40p' <<'EOF'
Usage: run_rds_analyzer.sh <subcommand> -- [args to rds-analyzer]

Subcommands:
  text          -o text -m simple  (terminal deviation report)
  html          -o html -m simple  (HTML report; redirect stdout to a file)
  reporting     -o text -m reporting  (LLM-oriented two-section report)
  validate-rules  --validate-rules-only  (upstream flag; regexp validation only; no -i)

Examples:
  run_rds_analyzer.sh text -- -i comparison.json -r rules.yaml
  run_rds_analyzer.sh html -- -i comparison.json -r rules.yaml > report.html
  run_rds_analyzer.sh reporting -- -i comparison.json -r rules.yaml
  run_rds_analyzer.sh validate-rules -- -r rules.yaml
  run_rds_analyzer.sh text -- -i comparison.json -r rules.yaml -t 4.21

Note: Upstream accepts one -r path per run; merge YAML offline if multiple rule files are required.
EOF
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

sub="$1"
shift

if [[ "${1:-}" == "--" ]]; then
  shift
fi

case "$sub" in
  text)
    exec "$BIN" -o text -m simple "$@"
    ;;
  html)
    exec "$BIN" -o html -m simple "$@"
    ;;
  reporting)
    exec "$BIN" -o text -m reporting "$@"
    ;;
  validate-rules)
    exec "$BIN" --validate-rules-only "$@"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown subcommand: $sub" >&2
    usage
    ;;
esac
