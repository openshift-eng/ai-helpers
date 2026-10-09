#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Read-only heuristic searches: no JavaScript parsing or policy verdicts.
# Deliberately handle exit codes explicitly: ripgrep's exit 1 means no matches.
set -o pipefail
export LC_ALL=C

usage() {
  printf '%s\n' 'Usage: bash scan-csp.sh <production-bundle-directory> [--max-findings 50] [--max-file-bytes 20971520]'
  printf '%s\n' 'Requires Bash, ripgrep and standard Unix utilities. Exit 0: text searches completed (candidates may exist); exit 2: input/tool error or incomplete search.'
}

fail() { printf 'error: %s\n' "$1" >&2; exit 2; }

max_findings=200
max_file_bytes=20971520
directory=''
while (( $# )); do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --max-findings|--max-file-bytes)
      option=$1
      (( $# >= 2 )) || fail "Missing value for $option"
      [[ $2 =~ ^[1-9][0-9]{0,8}$ ]] || fail "$option requires a positive integer of at most nine digits"
      if [[ $option == --max-findings ]]; then max_findings=$2; else max_file_bytes=$2; fi
      shift 2 ;;
    --)
      shift
      [[ $# == 1 && -z $directory ]] || fail 'Provide exactly one directory'
      directory=$1; shift ;;
    -*) fail "Unknown option: $1" ;;
    *) [[ -z $directory ]] || fail 'Provide exactly one directory'; directory=$1; shift ;;
  esac
done
[[ -n $directory && -d $directory && ! -L ${directory%/} ]] || fail 'Provide an existing directory, not a file or symbolic link'
root=$(cd -- "$directory" && pwd -P) || fail 'Cannot access the selected directory'
[[ $root != / ]] || fail 'Select a bundle directory, not the filesystem root'
for tool in rg wc mktemp rm rmdir; do
  command -v "$tool" >/dev/null 2>&1 || fail "Required command is missing: $tool"
done
scratch=$(mktemp -d "${TMPDIR:-/tmp}/console-csp-scan.XXXXXXXX") || fail 'Cannot create temporary scan storage'
cleanup() {
  rm -f -- "$scratch/files" "$scratch/matches" "$scratch/errors"
  rmdir -- "$scratch"
}
trap cleanup EXIT
trap 'exit 2' HUP INT TERM

error_count=0
errors_returned=0
total_candidates=0
returned_candidates=0
files_skipped=0
files=()
report_error() {
  (( error_count += 1 ))
  if (( errors_returned < 20 )); then
    printf 'error\t%s\t%q\n' "$1" "${2:0:300}"
    (( errors_returned += 1 ))
  fi
}
printf 'scope\theuristic-text-candidates; not JavaScript validation or a CSP verdict\n'
printf 'directory\t%q\n' "$root"
printf 'exclusions\tsource maps, .git, node_modules, symlinks\n'
printf 'columns\tcategory, shell-escaped relative file, line, byte-column, shell-escaped short match\n'

# Do not inherit ignore files or RIPGREP_CONFIG_PATH (which can configure --pre).
rg --no-config --files --null --sort path --hidden --no-ignore --glob '*.{js,mjs,cjs}' --glob '!**/.git/**' --glob '!**/node_modules/**' -- "$root" > "$scratch/files" 2> "$scratch/errors"
rg_status=$?
if (( rg_status > 1 )); then
  report_error enumeration-failed "$(< "$scratch/errors")"
fi
while IFS= read -r -d '' file; do
  if (( ${#files[@]} >= 10000 )); then
    report_error file-limit 'Stopped selecting files at the 10000-file limit'
    break
  fi
  if [[ ! -f $file || -L $file || ! -r $file ]]; then
    report_error unreadable-file "$file"
    (( files_skipped += 1 )); continue
  fi
  if ! bytes=$(wc -c < "$file"); then
    report_error size-check-failed "$file"
    (( files_skipped += 1 )); continue
  fi
  bytes=${bytes//[[:space:]]/}
  if (( bytes > max_file_bytes )); then
    report_error file-too-large "$file exceeds $max_file_bytes bytes; raise --max-file-bytes only if appropriate"
    (( files_skipped += 1 )); continue
  fi
  files+=("$file")
done < "$scratch/files"
if (( ${#files[@]} == 0 )); then report_error no-files 'No readable .js, .mjs or .cjs files were selected'; fi

# Whitespace spans are bounded to keep each emitted match short. These are
# lexical candidates, including comments/strings; computed access may be missed.
categories=(eval-reference function-constructor string-timer inline-style script-element innerHTML-assignment blob-url cdn-reference worker service-worker connection)
patterns=(
  '\beval\b(?:[ \t]{0,32}\(|[ \t]{0,32}[,;)]|[ \t]{0,32}$)'
  '\b(?:new[ \t]{1,32})?Function[ \t]{0,32}\('
  '\b(?:setTimeout|setInterval|execScript)[ \t]{0,32}\([ \t]{0,32}["\x27\x60]'
  'createElement[ \t]{0,32}\([ \t]{0,32}["\x27]style["\x27]'
  'createElement[ \t]{0,32}\([ \t]{0,32}["\x27]script["\x27]'
  '\.innerHTML[ \t]{0,32}='
  '\bcreateObjectURL[ \t]{0,32}\('
  '\bcdn\.[a-z]'
  '\b(?:Worker|SharedWorker)[ \t]{0,32}\('
  'serviceWorker[ \t]{0,32}\.[ \t]{0,32}register[ \t]{0,32}\('
  '\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)[ \t]{0,32}\('
)
for index in "${!categories[@]}"; do
  start=0
  # Small argument batches avoid command-line size limits with long paths.
  while (( start < ${#files[@]} )); do
    batch=("${files[@]:start:20}")
    rg --no-config --hidden --no-ignore --color never --no-heading --with-filename --null --line-number --column --only-matching --sort path --text --encoding none --regexp "${patterns[$index]}" -- "${batch[@]}" > "$scratch/matches" 2> "$scratch/errors"
    rg_status=$?
    if (( rg_status > 1 )); then
      report_error search-failed "${categories[$index]}: $(< "$scratch/errors")"
    fi
    while IFS= read -r -d '' file; do
      if ! IFS= read -r record; then report_error invalid-output 'Incomplete ripgrep match record'; break; fi
      line=${record%%:*}; remainder=${record#*:}
      column=${remainder%%:*}; match=${remainder#*:}
      if [[ ! $line =~ ^[0-9]+$ || ! $column =~ ^[0-9]+$ ]]; then
        report_error invalid-output 'Unexpected ripgrep location format'; continue
      fi
      (( total_candidates += 1 ))
      if (( returned_candidates < max_findings )); then
        relative=${file#"$root"/}
        printf 'candidate\t%s\t%q\t%s\t%s\t%q\n' "${categories[$index]}" "$relative" "$line" "$column" "${match:0:160}"
        (( returned_candidates += 1 ))
      fi
    done < "$scratch/matches"
    (( start += 20 ))
  done
done
printf 'summary\tfiles_selected=%s files_skipped=%s candidates_total=%s candidates_returned=%s candidates_omitted=%s errors_total=%s errors_omitted=%s\n' "${#files[@]}" "$files_skipped" "$total_candidates" "$returned_candidates" "$(( total_candidates - returned_candidates ))" "$error_count" "$(( error_count - errors_returned ))"
if (( error_count )); then printf 'status\tincomplete\n'; exit 2; fi
printf 'status\tcomplete-text-search\n'
