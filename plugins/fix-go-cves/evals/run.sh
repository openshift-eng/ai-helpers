#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: evals/run.sh [--live] [--config FILE] [--case ID ...] [--dry-run | --prepare-only] [--run-id ID] [--model MODEL]

Without a mode flag, run the recorded admiral case and its judges.
--dry-run (alias --no-model) prepares and replays without any model calls.
--prepare-only prepares the case workspace without replay or model calls.
--live runs today's remediation scripts, real builds, tests and scanners.
It supports --prepare-only, but cannot be combined with --dry-run.
--case selects a case from that track; repeat it to select several cases.
--config selects an alternate scoring profile. All replay cases share the default.

HARNESS selects an agent-eval-harness checkout. EVAL_JUDGE_MODEL overrides
the judge model; CVE_EVAL_PYTHON selects the Python interpreter. Results go
under AGENT_EVAL_RUNS_DIR, defaulting to .work/fix-go-cves-evals/runs/.
The default mode replays historical output rather than running remediation.
For Vertex authentication, explicitly enable CLAUDE_CODE_USE_VERTEX=1.
EOF
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd "$script_dir/../../.." && pwd -P)
mode=run
live=false
run_id="fix-go-cves-$(date -u +%Y%m%dT%H%M%SZ)-$$"
model_args=()
case_ids=()
config_override=""
while (($#)); do
  case "$1" in
    --live) live=true; shift ;;
    --dry-run|--no-model|--prepare-only)
      [[ "$mode" == run ]] || { echo "Choose one mode flag." >&2; exit 2; }
      if [[ "$1" == --prepare-only ]]; then mode=prepare; else mode=dry-run; fi
      shift
      ;;
    --case|--run-id|--model|--config)
      (($# >= 2)) || { echo "$1 needs a value." >&2; exit 2; }
      case "$1" in
        --case) case_ids+=("$2") ;;
        --run-id) run_id=$2 ;;
        --model) model_args=(--model "$2") ;;
        --config) config_override=$2; [[ "$2" == /* ]] || config_override="$PWD/$2" ;;
      esac
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
if [[ "$live" == true && "$mode" == dry-run ]]; then
  echo "--live cannot be combined with --dry-run or --no-model." >&2
  exit 2
fi
[[ "$run_id" =~ ^[A-Za-z0-9._-]+$ ]] && [[ "$run_id" != . && "$run_id" != .. ]] || {
  echo "Invalid run ID: $run_id" >&2
  exit 2
}

cd "$repo_root"
harness_dir=${HARNESS:-$repo_root/.work/fix-go-cves-review/harness}
[[ -f "$harness_dir/skills/eval-run/scripts/workspace.py" ]] || {
  echo "Set HARNESS to an agent-eval-harness checkout." >&2
  exit 2
}
harness_dir=$(cd "$harness_dir" && pwd -P)
harness_scripts="$harness_dir/skills/eval-run/scripts"
python_bin=$(command -v "${CVE_EVAL_PYTHON:-python3}") || {
  echo "Selected eval Python is unavailable." >&2; exit 2;
}
# Keep the virtual-environment entrypoint; resolving its symlink loses packages.
python_bin=$("$python_bin" -c 'import os,sys; print(os.path.abspath(sys.executable))')
export CVE_EVAL_PYTHON="$python_bin"
export PATH="$(dirname "$python_bin"):$PATH"
"$python_bin" -I -c 'from yaml import CSafeLoader; import agent_eval'
config="$script_dir/eval-replay.yaml"
default_case=case-005
verify_args=()
if [[ "$live" == true ]]; then
  config="$script_dir/eval-live.yaml"
  default_case=case-001
  verify_args=(--live)
fi
[[ -z "$config_override" ]] || config="$config_override"
if ((${#case_ids[@]} == 0)); then case_ids=("$default_case"); fi
helper="$script_dir/scripts/eval.py"
export AGENT_EVAL_RUNS_DIR=${AGENT_EVAL_RUNS_DIR:-$repo_root/.work/fix-go-cves-evals/runs}
mkdir -p "$AGENT_EVAL_RUNS_DIR"
AGENT_EVAL_RUNS_DIR=$(cd "$AGENT_EVAL_RUNS_DIR" && pwd -P)
export AGENT_EVAL_RUNS_DIR
export EVAL_JUDGE_MODEL=${EVAL_JUDGE_MODEL:-claude-opus-4-6}
export PYTHONPATH="$harness_dir${PYTHONPATH:+:$PYTHONPATH}"

# A fresh case HOME hides ADC's default location. Forward its path explicitly;
# leave credential contents and the judge process's HOME untouched.
if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" && -f "$HOME/.config/gcloud/application_default_credentials.json" ]]; then
  export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"
fi

eval_name=$(
  "$python_bin" -c 'import sys; from agent_eval.config import EvalConfig; print(EvalConfig.from_yaml(sys.argv[1]).eval_name())' "$config"
)
run_dir="$AGENT_EVAL_RUNS_DIR/$eval_name/$run_id"
workspace_base=$("$python_bin" -c 'import pathlib,tempfile; print((pathlib.Path(tempfile.gettempdir()) / "agent-eval").resolve())')
if [[ -e "$run_dir" || -e "$workspace_base/$run_id" ]]; then
  echo "Run ID already exists; choose a new --run-id: $run_id" >&2
  exit 2
fi
mkdir -p "$run_dir"
git -C "$harness_dir" rev-parse HEAD > "$run_dir/harness-revision.txt"
config=$("$python_bin" "$helper" snapshot --config "$config" --run-dir "$run_dir" \
  --cases "${case_ids[@]}" "${model_args[@]}" "${verify_args[@]}")
helper="$run_dir/provenance/fix-go-cves/evals/scripts/eval.py"
workspace_output=$("$python_bin" "$harness_scripts/workspace.py" --config "$config" --run-id "$run_id" --cases "${case_ids[@]}")
printf '%s\n' "$workspace_output"
workspace_dir=$(printf '%s\n' "$workspace_output" | sed -n 's/^WORKSPACE: //p')
for case_id in "${case_ids[@]}"; do
  [[ -d "$workspace_dir/cases/$case_id" ]] || {
    echo "Harness did not prepare the expected case workspace: $case_id" >&2
    exit 1
  }
done

status=0
if [[ "$mode" != run ]]; then
  prepare_args=()
  [[ "$mode" != prepare ]] || prepare_args=(--prepare-only)
  for case_id in "${case_ids[@]}"; do
    "$python_bin" "$helper" dry-run "${prepare_args[@]}" --workspace "$workspace_dir" \
      --case-source "$run_dir/provenance/cases/$case_id"
  done
else
  # Preserve artifacts and report incomplete runs even when execution fails.
  execute_status=0
  "$python_bin" "$harness_scripts/execute.py" \
    --config "$config" --workspace "$workspace_dir" \
    --run-id "$run_id" --output "$run_dir" "${model_args[@]}" || execute_status=$?
  status=$execute_status
  collect_status=0
  "$python_bin" "$harness_scripts/collect.py" \
    --config "$config" --workspace "$workspace_dir" --output "$run_dir" || collect_status=$?
  if [[ "$status" == 0 ]]; then status=$collect_status; fi
  if [[ "$execute_status" == 0 && "$collect_status" == 0 ]]; then
    "$python_bin" "$harness_scripts/score.py" judges \
      --config "$config" --run-id "$run_id" --workspace "$workspace_dir" || status=$?
  else
    echo "Skipping judges: execution or artifact collection failed." >&2
  fi
  "$python_bin" "$harness_scripts/report.py" \
    --config "$config" --run-id "$run_id" || { rc=$?; if [[ "$status" == 0 ]]; then status=$rc; fi; }
  "$python_bin" "$helper" verify --run-dir "$run_dir" "${verify_args[@]}" \
    || { rc=$?; if [[ "$status" == 0 ]]; then status=$rc; fi; }
  if [[ "$execute_status" == 0 && "$collect_status" == 0 ]]; then
    "$python_bin" "$harness_scripts/score.py" regression \
      --config "$config" --run-id "$run_id" || { rc=$?; if [[ "$status" == 0 ]]; then status=$rc; fi; }
  fi
fi
printf 'WORKSPACE: %s\nRESULTS: %s\n' "$workspace_dir" "$run_dir"
exit "$status"
