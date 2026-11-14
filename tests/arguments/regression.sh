#!/bin/bash
# Regression cases for how src/scripts/check.sh and src/scripts/format.sh pass
# 'targets', 'extensions' and 'extra_args' to Ruff, and for the input they
# refuse.
#
# Both scripts used to read only the first line of each parameter, so paths,
# mappings and arguments on later lines were silently dropped. The paths also
# reached Ruff without '--': a target named '--help' ran as an option, '-'
# made Ruff read standard input and '@args' was expanded as an argument file.
# 'fix: never' used to pass '--no-fix' alone, which 'fix-only = true' in a
# configuration overrides, and 'extra_args' could add '--fix' to it.
#
# Usage, from anywhere inside the repository:
#
#   bash tests/arguments/regression.sh check
#   bash tests/arguments/regression.sh format
#
# Both need Ruff 0.16.2 on PATH. Every case starts from the shared PARAM_*
# defaults in tests/defaults/check.sh or tests/defaults/format.sh, which
# tests/defaults/compare.py keeps equal to the defaults of the published
# command, and sets only what it is about.
#
# The argument cases put a copy of tests/arguments/record-ruff.sh first on
# PATH and compare what it receives with the expected lists: the paths after
# '--', the value of every '--extension' and the arguments that 'extra_args'
# adds. The 'Command:' line must show exactly the arguments received. The
# refusal cases use the same stand-in and require a non-zero status, no call
# of Ruff at all, not even 'ruff --version', and an unchanged target and
# report. The Ruff cases run the real Ruff on files named '-', '--help' and
# '@args', on extensions given on several lines, on empty targets and on
# configurations that ask for fixing or formatting, and pin the exit status.
# Everything runs in a temporary directory that is removed on exit, so nothing
# is written to tests/ or reports/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMMAND="${1:-}"

# Passes both 'ruff check' and 'ruff format --check'.
CLEAN_SOURCE='print("clean")'
# Fed to standard input. It passes both as well, so a run that reads it in
# place of the file named '-' reports nothing for '-' and exits 0.
STDIN_SOURCE='print("standard input")'

case "${COMMAND}" in
  check)
    SCRIPT="${ROOT}/src/scripts/check.sh"
    # One F401 and nothing else under the default rule set.
    BAD_SOURCE='import os'
    ;;
  format)
    SCRIPT="${ROOT}/src/scripts/format.sh"
    # Free of violations, but not formatted.
    BAD_SOURCE='x=1'
    ;;
  *)
    echo 'Usage: bash tests/arguments/regression.sh check|format' >&2
    exit 1
    ;;
esac

CASES=0
FAILURES=0
CASE_NAME=''
CASE_LOG=''
CASE_STATUS=0
ARGV=()
BASELINE=''
BASELINE_COUNT=0
REFUSE_SNAPSHOT=''
BEFORE=()
AFTER=()
SEPARATOR=''

DEFAULTS="${ROOT}/tests/defaults/${COMMAND}.sh"

if [ ! -s "${DEFAULTS}" ]; then
  echo "PARAM_* defaults not found at '${DEFAULTS}'." >&2
  exit 1
fi

if ! command -v ruff > /dev/null; then
  echo 'Ruff is not on PATH.' >&2
  exit 1
fi

RUFF_VERSION="$(ruff --version)"

echo "Testing ${SCRIPT#"${ROOT}/"} with ${RUFF_VERSION} from $(command -v ruff)"
echo "Defaults from ${DEFAULTS#"${ROOT}/"}"

SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

MOCK_BIN="${SCRATCH}/bin"
ARGV_FILE="${SCRATCH}/argv"
CALLS_FILE="${SCRATCH}/calls"
STDIN_FILE="${SCRATCH}/stdin.py"
LOG_DIR="${SCRATCH}/logs"
WORK="${SCRATCH}/work"

mkdir -p "${MOCK_BIN}" "${LOG_DIR}" "${WORK}"
cp "${ROOT}/tests/arguments/record-ruff.sh" "${MOCK_BIN}/ruff"
chmod +x "${MOCK_BIN}/ruff"
printf '%s\n' "${STDIN_SOURCE}" > "${STDIN_FILE}"

# An empty ruff.toml makes WORK the project root of every case, so neither a
# configuration in a parent directory nor the user's own Ruff configuration
# can change the results.
: > "${WORK}/ruff.toml"

# The argument cases run here, next to files their glob characters would
# match if anything expanded them.
MOCK_DIR="${WORK}/mock"
mkdir -p "${MOCK_DIR}/globdir"
: > "${MOCK_DIR}/alpha.py"
: > "${MOCK_DIR}/b.py"
: > "${MOCK_DIR}/globdir/inner.py"
: > "${MOCK_DIR}/ext:python"

# Files named like an option, standard input and an argument file. 'args' is
# what '@args' would expand to if Ruff read it as an argument file.
SPECIAL_DIR="${WORK}/special"
mkdir -p "${SPECIAL_DIR}"
printf '%s\n' "${BAD_SOURCE}" > "${SPECIAL_DIR}/-"
printf '%s\n' "${BAD_SOURCE}" > "${SPECIAL_DIR}/--help"
printf '%s\n' "${BAD_SOURCE}" > "${SPECIAL_DIR}/@args"
printf '%s\n' 'expanded-from-args-file' > "${SPECIAL_DIR}/args"

# Ruff only discovers these files through their '--extension' mapping.
EXTENSIONS_DIR="${WORK}/extensions"
mkdir -p "${EXTENSIONS_DIR}"
printf '%s\n' "${BAD_SOURCE}" > "${EXTENSIONS_DIR}/first.pya"
printf '%s\n' "${BAD_SOURCE}" > "${EXTENSIONS_DIR}/second.pyb"

# Only a recursive run from the working directory reaches pkg/module.py.
TREE_DIR="${WORK}/tree"
mkdir -p "${TREE_DIR}/pkg"
printf '%s\n' "${CLEAN_SOURCE}" > "${TREE_DIR}/top.py"
printf '%s\n' "${BAD_SOURCE}" > "${TREE_DIR}/pkg/module.py"

EXIT_DIR="${WORK}/exit"
mkdir -p "${EXIT_DIR}"
printf '%s\n' "${CLEAN_SOURCE}" > "${EXIT_DIR}/clean.py"
printf '%s\n' "${BAD_SOURCE}" > "${EXIT_DIR}/bad.py"
printf '%s\n' "${BAD_SOURCE}" > "${EXIT_DIR}/rewrite.py"

# A refused run must leave this directory exactly as it is.
REFUSE_DIR="${WORK}/refuse"
mkdir -p "${REFUSE_DIR}"
printf '%s\n' "${BAD_SOURCE}" > "${REFUSE_DIR}/target.py"
printf '%s\n' 'REPORT OF AN EARLIER RUN' > "${REFUSE_DIR}/report.txt"

# One directory per way a configuration can reach Ruff: its own ruff.toml,
# its own pyproject.toml, and 'config_overrides', which is given per case.
# For check.sh the setting asks Ruff to apply fixes without reporting. For
# format.sh it makes the formatter want to change code that is formatted
# under the defaults.
CONFIG_DIR="${WORK}/config"
mkdir -p "${CONFIG_DIR}/ruff-toml" "${CONFIG_DIR}/pyproject" \
  "${CONFIG_DIR}/overrides"

if [ "${COMMAND}" = 'check' ]; then
  CONFIG_SOURCE="${BAD_SOURCE}"
  CONFIG_OVERRIDE='fix-only = true'
  CONFIG_DIFF_LINE='-import os'
  CONFIG_DIFF_PARAMETER='PARAM_DIFF=true'
  # The backticks are part of Ruff's message.
  # shellcheck disable=SC2016
  CONFIG_REPORT_LINE='a.py:1:8: F401 [*] `os` imported but unused'
  printf '%s\n' 'fix-only = true' > "${CONFIG_DIR}/ruff-toml/ruff.toml"
  printf '%s\n' '[tool.ruff]' 'fix-only = true' \
    > "${CONFIG_DIR}/pyproject/pyproject.toml"
else
  CONFIG_SOURCE='x = "a"'
  CONFIG_OVERRIDE='format.quote-style = "single"'
  CONFIG_DIFF_LINE="+x = 'a'"
  CONFIG_DIFF_PARAMETER='PARAM_MODE=diff'
  CONFIG_REPORT_LINE='a.py:1:5: unformatted: File would be reformatted'
  printf '%s\n' '[format]' 'quote-style = "single"' \
    > "${CONFIG_DIR}/ruff-toml/ruff.toml"
  printf '%s\n' '[tool.ruff.format]' 'quote-style = "single"' \
    > "${CONFIG_DIR}/pyproject/pyproject.toml"
fi

for route in ruff-toml pyproject overrides; do
  printf '%s\n' "${CONFIG_SOURCE}" > "${CONFIG_DIR}/${route}/a.py"
done

fail() {
  echo "FAIL [${COMMAND} ${CASE_NAME}]: $*"
  FAILURES=$((FAILURES + 1))
}

load_defaults() {
  # shellcheck source=/dev/null
  source "${DEFAULTS}"
}

# run_case NAME DIRECTORY VARIABLE=VALUE...
#
# Runs the script under test from DIRECTORY with the defaults plus the given
# overrides and with STDIN_FILE on standard input. The combined output is kept
# in CASE_LOG and printed, and the exit status is kept in CASE_STATUS. The
# debug lines that used to print single parameters must not come back.
run_case() {
  CASE_NAME="$1"
  local directory="$2"
  shift 2
  CASE_LOG="${LOG_DIR}/${CASE_NAME}.log"
  CASES=$((CASES + 1))

  # A second case of the same name would overwrite the first one's log.
  if [ -e "${CASE_LOG}" ]; then
    echo "The case name '${CASE_NAME}' is used twice." >&2
    exit 1
  fi

  set +e
  (
    load_defaults

    for assignment in "$@"; do
      export "${assignment?}"
    done

    cd "${directory}"
    bash "${SCRIPT}" < "${STDIN_FILE}"
  ) > "${CASE_LOG}" 2>&1
  CASE_STATUS=$?
  set -e

  echo
  echo "----- ${COMMAND} ${CASE_NAME} (exit status ${CASE_STATUS}) -----"
  sed 's/^/  | /' "${CASE_LOG}"

  if grep -q '^PARAM_' "${CASE_LOG}"; then
    fail 'the log prints a PARAM_ debug line'
  fi
}

# load_argv reads what the stand-in received into ARGV, then splits it into
# BEFORE, the arguments between the subcommand and the first '--', and AFTER,
# everything after that '--'. SEPARATOR is 'found' when there is a '--'.
load_argv() {
  local argument index

  ARGV=()
  BEFORE=()
  AFTER=()
  SEPARATOR=''

  if [ ! -f "${ARGV_FILE}" ]; then
    fail 'the stand-in for Ruff was not started'
    return 0
  fi

  while IFS= read -r -d '' argument; do
    ARGV+=("${argument}")
  done < "${ARGV_FILE}"

  for ((index = 1; index < ${#ARGV[@]}; index++)); do
    if [ "${SEPARATOR}" = 'found' ]; then
      AFTER+=("${ARGV[index]}")
    elif [ "${ARGV[index]}" = '--' ]; then
      SEPARATOR='found'
    else
      BEFORE+=("${ARGV[index]}")
    fi
  done
}

# run_mock NAME VARIABLE=VALUE...
#
# Runs a case with the stand-in first on PATH and loads what it received. The
# stand-in exits 0, so the script must too, and the 'Command:' line must show
# exactly the arguments the stand-in received. The script must start Ruff
# twice: 'ruff --version' first, then the command.
run_mock() {
  local name="$1"
  shift

  rm -f "${ARGV_FILE}" "${CALLS_FILE}"
  run_case "${name}" "${MOCK_DIR}" \
    PATH="${MOCK_BIN}:${PATH}" \
    RECORD_RUFF_ARGV="${ARGV_FILE}" \
    RECORD_RUFF_CALLS="${CALLS_FILE}" \
    "$@"
  expect_status 0
  load_argv

  if [ "${#ARGV[@]}" -gt 0 ]; then
    expect_log_line "Command:$(printf ' %q' ruff "${ARGV[@]}")"
  fi

  if [ ! -f "${CALLS_FILE}" ] ||
    [ "$(wc -l < "${CALLS_FILE}")" -ne 2 ] ||
    [ "$(head -n 1 "${CALLS_FILE}")" != 'ruff --version ' ]; then
    fail "Ruff was not started as 'ruff --version' and then once more"
  fi
}

# snapshot DIRECTORY prints the name and SHA-256 of every file below it.
snapshot() {
  (
    cd "$1"
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
  )
}

# expect_refuse_dir_unchanged compares REFUSE_DIR with the snapshot taken when
# it was set up, so one case cannot hide a change that an earlier one made.
expect_refuse_dir_unchanged() {
  if [ "$(snapshot "${REFUSE_DIR}")" != "${REFUSE_SNAPSHOT}" ]; then
    fail 'the target, the report or another file changed'
  fi
}

# run_refused NAME VARIABLE=VALUE...
#
# Runs a case that the script must refuse, with the stand-in first on PATH.
# The case passes only when the script exits 1, says that Ruff was not run,
# prints no 'Command:' line, did not start the stand-in even for
# 'ruff --version', and left the target, the existing report and the rest of
# REFUSE_DIR exactly as they were. check.sh is also given the report as
# 'output_file', so preparing it too early would empty it.
run_refused() {
  local name="$1"
  local -a report=()
  shift

  if [ "${COMMAND}" = 'check' ]; then
    report=(PARAM_OUTPUT_FILE='report.txt')
  fi

  rm -f "${ARGV_FILE}" "${CALLS_FILE}"
  run_case "${name}" "${REFUSE_DIR}" \
    PATH="${MOCK_BIN}:${PATH}" \
    RECORD_RUFF_ARGV="${ARGV_FILE}" \
    RECORD_RUFF_CALLS="${CALLS_FILE}" \
    PARAM_TARGETS='target.py' \
    "${report[@]}" \
    "$@"
  expect_status 1
  expect_log_line "'extra_args' contains items that are not accepted, so Ruff was not run:"
  expect_log_lacks 'Command:'

  if [ -e "${CALLS_FILE}" ] || [ -e "${ARGV_FILE}" ]; then
    fail "Ruff was started: $(tr "\n" ";" < "${CALLS_FILE}" 2> /dev/null || true)"
  fi

  expect_refuse_dir_unchanged
}

# expect_refused ITEM... asserts that the log names exactly these items as
# refused, in this order.
expect_refused() {
  local expected actual

  expected="$(printf "'%s'\\n" "$@")"
  actual="$(sed -n "s/^  \\('[^']*'\\): .*/\\1/p" "${CASE_LOG}")"

  if [ "${actual}" != "${expected}" ]; then
    fail "expected the refused items $(describe "$@"), the log names: ${actual//$'\n'/ }"
  fi
}

# expect_arguments ARGUMENT... asserts that exactly these arguments stand
# between the subcommand and '--'.
expect_arguments() {
  local expected actual

  expected="$(describe "$@")"
  actual="$(describe "${BEFORE[@]}")"

  if [ "${actual}" != "${expected}" ]; then
    fail "expected the arguments ${expected}, got ${actual}"
  fi
}

# expect_extra ARGUMENT... asserts that the arguments before '--' are those of
# the run without extra_args, counted in BASELINE_COUNT and described in
# BASELINE, followed by exactly these.
expect_extra() {
  if [ "${#BEFORE[@]}" -lt "${BASELINE_COUNT}" ] ||
    [ "$(describe "${BEFORE[@]:0:BASELINE_COUNT}")" != "${BASELINE}" ] ||
    [ "$(describe "${BEFORE[@]:BASELINE_COUNT}")" != "$(describe "$@")" ]; then
    fail "expected ${BASELINE} followed by $(describe "$@"), got $(describe "${BEFORE[@]}")"
  fi
}

# run_ruff NAME DIRECTORY VARIABLE=VALUE... runs a case with the real Ruff.
# Concise output puts each finding on one line that starts with the file name.
# The log must start with the version that 'ruff --version' prints.
run_ruff() {
  local name="$1"
  local directory="$2"
  shift 2

  run_case "${name}" "${directory}" PARAM_OUTPUT_FORMAT='concise' "$@"

  if ! grep -q '^Command:.* -- ' "${CASE_LOG}"; then
    fail "the 'Command:' line does not show '--'"
  fi

  # The version is still printed, and before the command line.
  if [ "$(head -n 1 "${CASE_LOG}")" != "${RUFF_VERSION}" ]; then
    fail "the log does not start with '${RUFF_VERSION}'"
  fi
}

# expect_unchanged FILE CONTENT asserts that FILE still holds CONTENT.
expect_unchanged() {
  if [ "$(cat "$1")" != "$2" ]; then
    fail "$1 was modified"
  fi
}

# describe ARGUMENT... prints the count and the quoted arguments, so two lists
# compare equal only when they hold the same strings in the same order.
describe() {
  printf '%d:' "$#"

  if [ "$#" -gt 0 ]; then
    printf ' %q' "$@"
  fi
}

# expect_paths PATH... asserts that Ruff received '--' followed by exactly
# these paths.
expect_paths() {
  local expected actual

  if [ "${SEPARATOR}" != 'found' ]; then
    fail "Ruff received no '--' before the paths"
    return 0
  fi

  expected="$(describe "$@")"
  actual="$(describe "${AFTER[@]}")"

  if [ "${actual}" != "${expected}" ]; then
    fail "expected the paths ${expected}, got ${actual}"
  fi
}

# expect_extensions MAPPING... asserts that the arguments before '--' carry
# exactly these mappings, each as the value of its own '--extension'.
expect_extensions() {
  local -a values=()
  local expected actual index

  for ((index = 0; index < ${#BEFORE[@]}; index++)); do
    if [ "${BEFORE[index]}" = '--extension' ]; then
      index=$((index + 1))

      if [ "${index}" -ge "${#BEFORE[@]}" ]; then
        fail "the last '--extension' has no value"
        return 0
      fi

      values+=("${BEFORE[index]}")
    fi
  done

  expected="$(describe "$@")"
  actual="$(describe "${values[@]}")"

  if [ "${actual}" != "${expected}" ]; then
    fail "expected the mappings ${expected}, got ${actual}"
  fi
}

expect_status() {
  if [ "${CASE_STATUS}" -ne "$1" ]; then
    fail "expected exit status $1, got ${CASE_STATUS}"
  fi
}

# expect_log_line LINE asserts that LINE is a whole line of the log.
expect_log_line() {
  if ! grep -Fxq -- "$1" "${CASE_LOG}"; then
    fail "the log has no line '$1'"
  fi
}

expect_log_has() {
  if ! grep -Fq -- "$1" "${CASE_LOG}"; then
    fail "the log does not contain '$1'"
  fi
}

expect_log_lacks() {
  if grep -Fq -- "$1" "${CASE_LOG}"; then
    fail "the log contains '$1'"
  fi
}

# expect_same_log FILE asserts that this case printed exactly what FILE holds.
expect_same_log() {
  if ! diff -u "$1" "${CASE_LOG}"; then
    fail "the output differs from $(basename "$1" .log)"
  fi
}

# diagnostic NAME prints the line that Ruff's concise output gives for
# BAD_SOURCE in the file NAME.
diagnostic() {
  if [ "${COMMAND}" = 'check' ]; then
    # The backticks are part of Ruff's message.
    # shellcheck disable=SC2016
    printf '%s:1:8: F401 [*] `os` imported but unused\n' "$1"
  else
    printf '%s:1:2: unformatted: File would be reformatted\n' "$1"
  fi
}

# ---------------------------------------------------------------------------
# targets, as received by the stand-in. Spaces, tabs and newlines separate the
# items, empty lines vanish, and an empty or blank value means '.'. Nothing is
# evaluated, and a relative item starting with '-' or '@' gains './'.
# ---------------------------------------------------------------------------

run_mock targets-one-line PARAM_TARGETS='src tests'
expect_paths src tests

run_mock targets-two-lines PARAM_TARGETS=$'src\ntests'
expect_paths src tests

run_mock targets-empty-lines-and-indentation \
  PARAM_TARGETS=$'\n  src\n\n    tests\n\nlib/pkg\n'
expect_paths src tests lib/pkg

run_mock targets-tabs PARAM_TARGETS=$'src\ttests\t\tlib   pkg'
expect_paths src tests lib pkg

run_mock targets-empty PARAM_TARGETS=''
expect_paths .

run_mock targets-blank PARAM_TARGETS=$' \t\n  \n\t'
expect_paths .

run_mock targets-glob-characters \
  PARAM_TARGETS='*.py ?.py [ab]*.py globdir/* {alpha,b}.py'
expect_paths '*.py' '?.py' '[ab]*.py' 'globdir/*' '{alpha,b}.py'

run_mock targets-quotes PARAM_TARGETS=$'"two words" \'single quoted\''
expect_paths '"two' 'words"' "'single" "quoted'"

# The dollar signs, backticks and tildes are meant to stay literal.
# shellcheck disable=SC2016
run_mock targets-shell-syntax \
  PARAM_TARGETS='$HOME ${HOME} $(id) `id` ~/src ~ a;b a|b a&&b >out'
# shellcheck disable=SC2016,SC2088
expect_paths '$HOME' '${HOME}' '$(id)' '`id`' '~/src' '~' 'a;b' 'a|b' \
  'a&&b' '>out'

# A backslash escapes nothing, so it neither joins two items nor disappears.
# shellcheck disable=SC1003
run_mock targets-backslashes PARAM_TARGETS='a\ b c\\d trailing\'
# shellcheck disable=SC1003
expect_paths 'a\' 'b' 'c\\d' 'trailing\'

# A relative item that starts with '-' or '@' gains './', including '-',
# '--' and '@' on their own. Absolute paths and other relative paths stay as
# they are.
run_mock targets-dash-and-at \
  PARAM_TARGETS='- -x --help -- @ @args ./-y src/-z /abs/-w /abs/@v'
expect_paths ./- ./-x ./--help ./-- ./@ ./@args ./-y src/-z /abs/-w /abs/@v

run_mock targets-dash-and-at-on-several-lines \
  PARAM_TARGETS=$'-\n--help\n\n@args\n'
expect_paths ./- ./--help ./@args

# ---------------------------------------------------------------------------
# extensions, as received by the stand-in. The items are split like targets,
# and each one becomes the value of its own '--extension'.
# ---------------------------------------------------------------------------

run_mock extensions-one-line PARAM_EXTENSIONS='pya:python pyb:python'
expect_extensions pya:python pyb:python
expect_paths .

run_mock extensions-several-lines \
  PARAM_EXTENSIONS=$'pya:python\npyb:python\npyc:python'
expect_extensions pya:python pyb:python pyc:python
expect_paths .

run_mock extensions-empty-lines-and-tabs \
  PARAM_EXTENSIONS=$'\n\tpya:python\n\n  pyb:python\tpyc:python\n'
expect_extensions pya:python pyb:python pyc:python

run_mock extensions-empty PARAM_EXTENSIONS=''
expect_extensions

run_mock extensions-blank PARAM_EXTENSIONS=$' \n\t\n'
expect_extensions

run_mock extensions-glob-characters PARAM_EXTENSIONS='*:python ?xt:python'
expect_extensions '*:python' '?xt:python'

run_mock targets-and-extensions-together \
  PARAM_EXTENSIONS=$'pya:python\npyb:python' \
  PARAM_TARGETS=$'src\n-\ntests'
expect_extensions pya:python pyb:python
expect_paths src ./- tests

# ---------------------------------------------------------------------------
# extra_args, as received by the stand-in. The items are split like targets
# and appended after the arguments the parameters produce. BASELINE holds
# those arguments for the defaults: 'fix: never' passes both '--no-fix' and
# '--no-fix-only', and the format mode 'check' passes '--check'.
# ---------------------------------------------------------------------------

run_mock extra-args-none PARAM_EXTRA_ARGS=''

if [ "${COMMAND}" = 'check' ]; then
  expect_arguments --no-fix --no-fix-only
else
  expect_arguments --check
fi

BASELINE="$(describe "${BEFORE[@]}")"
BASELINE_COUNT="${#BEFORE[@]}"

run_mock extra-args-blank PARAM_EXTRA_ARGS=$' \n\t\n'
expect_extra

run_mock extra-args-one-line PARAM_EXTRA_ARGS='--alpha --beta value'
expect_extra --alpha --beta value

run_mock extra-args-several-lines \
  PARAM_EXTRA_ARGS=$'--alpha\n\n  --beta value\n\t--gamma\n'
expect_extra --alpha --beta value --gamma
expect_paths .

# shellcheck disable=SC2016
run_mock extra-args-not-evaluated \
  PARAM_EXTRA_ARGS='--extend-exclude *.py "a b" $HOME $(id) ~ a\ b'
# shellcheck disable=SC2016,SC2088,SC1003
expect_extra --extend-exclude '*.py' '"a' 'b"' '$HOME' '$(id)' '~' 'a\' 'b'

# Arguments outside the refused list arrive exactly as written. The script
# does not take combined short options or 'NAME=VALUE' apart, and '--fixable'
# is not '--fix'. This shows what is passed on, not what Ruff then does.
run_mock extra-args-passed-through \
  PARAM_EXTRA_ARGS='-ne --output-file=x -ox --fixable F401 --show-settings'
expect_extra -ne --output-file=x -ox --fixable F401 --show-settings

run_mock extra-args-near-the-refused-names \
  PARAM_EXTRA_ARGS='--fixable --fix-onlyx --fixed --add-noqa-x --add-ignored --no-fix --no-fix-only --unsafe-fixes -fix --FIX fix --x=@y a@b --- --='
expect_extra --fixable --fix-onlyx --fixed --add-noqa-x --add-ignored \
  --no-fix --no-fix-only --unsafe-fixes -fix --FIX fix --x=@y a@b --- --=

run_mock extra-args-with-targets \
  PARAM_EXTRA_ARGS=$'--alpha\n--beta' \
  PARAM_TARGETS=$'src\n-'
expect_extra --alpha --beta
expect_paths src ./-

REWRITING='--fix --fix=1 --fix-only --fix-only=0 --add-noqa --add-noqa=why --add-ignore --add-ignore=why'

if [ "${COMMAND}" = 'check' ]; then
  # The other values of 'fix' keep their arguments, and there the options
  # that rewrite files are passed on.
  run_mock fix-auto PARAM_FIX='auto'
  expect_arguments

  run_mock fix-safe PARAM_FIX='safe'
  expect_arguments --fix --no-unsafe-fixes

  run_mock fix-unsafe PARAM_FIX='unsafe'
  expect_arguments --fix --unsafe-fixes

  run_mock fix-auto-extra-args-rewriting \
    PARAM_FIX='auto' \
    PARAM_EXTRA_ARGS="${REWRITING}"
  expect_arguments --fix --fix=1 --fix-only --fix-only=0 --add-noqa \
    --add-noqa=why --add-ignore --add-ignore=why

  run_mock fix-safe-extra-args-rewriting \
    PARAM_FIX='safe' \
    PARAM_EXTRA_ARGS="${REWRITING}"
  expect_arguments --fix --no-unsafe-fixes --fix --fix=1 --fix-only \
    --fix-only=0 --add-noqa --add-noqa=why --add-ignore --add-ignore=why

  run_mock fix-unsafe-extra-args-rewriting \
    PARAM_FIX='unsafe' \
    PARAM_EXTRA_ARGS="${REWRITING}"
  expect_arguments --fix --unsafe-fixes --fix --fix=1 --fix-only \
    --fix-only=0 --add-noqa --add-noqa=why --add-ignore --add-ignore=why
else
  # format.sh has no 'fix' parameter, so it does not refuse these names.
  run_mock extra-args-rewriting-names PARAM_EXTRA_ARGS="${REWRITING}"
  expect_extra --fix --fix=1 --fix-only --fix-only=0 --add-noqa \
    --add-noqa=why --add-ignore --add-ignore=why
fi

# ---------------------------------------------------------------------------
# extra_args that are refused. '--' and an item that starts with '@' are
# refused whatever 'fix' or 'mode' says.
# ---------------------------------------------------------------------------

REFUSE_SNAPSHOT="$(snapshot "${REFUSE_DIR}")"

if [ "${COMMAND}" = 'check' ]; then
  VARIANT_NAME='PARAM_FIX'
  VARIANTS=(never auto safe unsafe)
else
  VARIANT_NAME='PARAM_MODE'
  VARIANTS=(check diff write)
fi

for variant in "${VARIANTS[@]}"; do
  run_refused "refused-${variant}-separator" \
    "${VARIANT_NAME}=${variant}" \
    PARAM_EXTRA_ARGS='--'
  expect_refused --

  run_refused "refused-${variant}-argument-file" \
    "${VARIANT_NAME}=${variant}" \
    PARAM_EXTRA_ARGS='@args'
  expect_refused @args

  run_refused "refused-${variant}-at-alone" \
    "${VARIANT_NAME}=${variant}" \
    PARAM_EXTRA_ARGS='@'
  expect_refused @
done

# The rule looks at each item on its own, so '@' is also refused where Ruff
# would read the item as the value of an option.
run_refused refused-at-as-a-value PARAM_EXTRA_ARGS='--config @settings.toml'
expect_refused @settings.toml

run_refused refused-on-a-later-line \
  PARAM_EXTRA_ARGS=$'--alpha\n--beta value\n\n  @args\n--gamma'
expect_refused @args

run_refused refused-several-at-once \
  PARAM_EXTRA_ARGS=$'--alpha @one\n--\n@two'
expect_refused @one -- @two

if [ "${COMMAND}" = 'check' ]; then
  # Under 'fix: never' each option that rewrites files is refused, alone and
  # as 'NAME=VALUE', whatever the value is.
  REFUSED_INDEX=0

  for item in --fix --fix=true --fix=false --fix= --fix-only \
    --fix-only=true --fix-only=false --add-noqa --add-noqa=why \
    --add-ignore --add-ignore=why; do
    REFUSED_INDEX=$((REFUSED_INDEX + 1))
    run_refused "refused-never-${REFUSED_INDEX}${item//=/-equals-}" \
      PARAM_EXTRA_ARGS="${item}"
    expect_refused "${item}"
  done

  run_refused refused-never-on-a-later-line \
    PARAM_EXTRA_ARGS=$'--show-settings\n--extend-fixable F401\n--fix'
  expect_refused --fix

  run_refused refused-never-after-no-fix \
    PARAM_EXTRA_ARGS='--no-fix --fix-only --no-fix-only'
  expect_refused --fix-only

  run_refused refused-never-all-at-once \
    PARAM_EXTRA_ARGS=$'--fix --fix-only\n--add-noqa=x\n--add-ignore\n--\n@a'
  expect_refused --fix --fix-only --add-noqa=x --add-ignore -- @a

  # The dedicated parameter is still refused under 'fix: never', before Ruff
  # is started.
  rm -f "${ARGV_FILE}" "${CALLS_FILE}"
  run_case refused-fix-only-parameter "${REFUSE_DIR}" \
    PATH="${MOCK_BIN}:${PATH}" \
    RECORD_RUFF_ARGV="${ARGV_FILE}" \
    RECORD_RUFF_CALLS="${CALLS_FILE}" \
    PARAM_FIX_ONLY='true' \
    PARAM_OUTPUT_FILE='report.txt' \
    PARAM_TARGETS='target.py'
  expect_status 1
  expect_log_line "'fix_only' rewrites files, so it needs 'fix' set to 'auto', 'safe' or 'unsafe'."

  if [ -e "${CALLS_FILE}" ]; then
    fail 'Ruff was started'
  fi

  expect_refuse_dir_unchanged

  # The same refusal with the real Ruff on PATH: the file it could fix stays
  # as it is, and not even the version is printed.
  run_case refused-never-with-the-real-ruff "${REFUSE_DIR}" \
    PARAM_EXTRA_ARGS='--fix' \
    PARAM_OUTPUT_FILE='report.txt' \
    PARAM_TARGETS='target.py'
  expect_status 1
  expect_refused --fix
  expect_log_lacks "${RUFF_VERSION}"
  expect_log_lacks 'Command:'
  expect_refuse_dir_unchanged
fi

# ---------------------------------------------------------------------------
# The real Ruff on files named '-', '--help' and '@args'. Each must be
# reported under its own name. Reading standard input instead would report
# nothing for '-' and exit 0, '--help' would print the usage and exit 0, and
# expanding '@args' would look for 'expanded-from-args-file'.
# ---------------------------------------------------------------------------

run_ruff ruff-name-standard-input "${SPECIAL_DIR}" PARAM_TARGETS='-'
expect_status 1
expect_log_line "$(diagnostic -)"

run_ruff ruff-name-option "${SPECIAL_DIR}" PARAM_TARGETS='--help'
expect_status 1
expect_log_line "$(diagnostic --help)"
expect_log_lacks 'Usage:'

run_ruff ruff-name-argument-file "${SPECIAL_DIR}" PARAM_TARGETS='@args'
expect_status 1
expect_log_line "$(diagnostic @args)"
expect_log_lacks 'expanded-from-args-file'

run_ruff ruff-names-on-several-lines "${SPECIAL_DIR}" \
  PARAM_TARGETS=$'-\n--help\n\n@args'
expect_status 1
expect_log_line "$(diagnostic -)"
expect_log_line "$(diagnostic --help)"
expect_log_line "$(diagnostic @args)"
expect_log_lacks 'Usage:'
expect_log_lacks 'expanded-from-args-file'

# ---------------------------------------------------------------------------
# The real Ruff with extensions on several lines and empty targets. Both files
# are found only when both mappings arrive.
# ---------------------------------------------------------------------------

run_ruff ruff-extensions-several-lines "${EXTENSIONS_DIR}" \
  PARAM_EXTENSIONS=$'pya:python\n\npyb:python' \
  PARAM_TARGETS=''
expect_status 1
expect_log_line "$(diagnostic first.pya)"
expect_log_line "$(diagnostic second.pyb)"

# ---------------------------------------------------------------------------
# Empty and blank targets give exactly the run that '.' gives.
# ---------------------------------------------------------------------------

run_ruff ruff-targets-dot "${TREE_DIR}" PARAM_TARGETS='.'
expect_status 1
expect_log_line "$(diagnostic pkg/module.py)"
DOT_LOG="${CASE_LOG}"

run_ruff ruff-targets-empty "${TREE_DIR}" PARAM_TARGETS=''
expect_status 1
expect_same_log "${DOT_LOG}"

run_ruff ruff-targets-blank "${TREE_DIR}" PARAM_TARGETS=$' \t\n\n  '
expect_status 1
expect_same_log "${DOT_LOG}"

# ---------------------------------------------------------------------------
# The real Ruff with a configuration that asks for changes. For check.sh it
# sets 'fix-only = true', which '--no-fix' alone does not stop, in ruff.toml,
# in pyproject.toml and through 'config_overrides'. Under 'fix: never' the
# file must stay as it is and the violation must be reported, and with 'diff'
# the fix must be shown instead. For format.sh the configuration makes the
# 'check' and 'diff' modes want a change, which they must report or show
# without making it.
# ---------------------------------------------------------------------------

for route in ruff-toml pyproject overrides; do
  ROUTE_OVERRIDES=''

  if [ "${route}" = 'overrides' ]; then
    ROUTE_OVERRIDES="${CONFIG_OVERRIDE}"
  fi

  run_ruff "ruff-config-${route}" "${CONFIG_DIR}/${route}" \
    PARAM_CONFIG_OVERRIDES="${ROUTE_OVERRIDES}" \
    PARAM_TARGETS='a.py'
  expect_status 1
  expect_log_line "${CONFIG_REPORT_LINE}"
  expect_unchanged "${CONFIG_DIR}/${route}/a.py" "${CONFIG_SOURCE}"

  run_ruff "ruff-config-${route}-diff" "${CONFIG_DIR}/${route}" \
    PARAM_CONFIG_OVERRIDES="${ROUTE_OVERRIDES}" \
    "${CONFIG_DIFF_PARAMETER}" \
    PARAM_TARGETS='a.py'
  expect_status 1
  expect_log_line "${CONFIG_DIFF_LINE}"
  expect_unchanged "${CONFIG_DIR}/${route}/a.py" "${CONFIG_SOURCE}"
done

if [ "${COMMAND}" = 'check' ]; then
  # '--show-settings' is not refused and reaches Ruff, which prints the
  # settings instead of checking.
  run_ruff ruff-show-settings "${EXIT_DIR}" \
    PARAM_EXTRA_ARGS='--show-settings' \
    PARAM_TARGETS='bad.py'
  expect_status 0
  expect_log_has 'Resolved settings for: '
else
  # An invalid setting is a configuration error, 2, in both modes, which is
  # not the 1 of a file that would be reformatted. Nothing is modified.
  for mode in check diff; do
    run_ruff "ruff-config-invalid-${mode}" "${CONFIG_DIR}/overrides" \
      PARAM_CONFIG_OVERRIDES='format.quote-style = "no-such-style"' \
      PARAM_MODE="${mode}" \
      PARAM_TARGETS='a.py'
    expect_status 2
    expect_unchanged "${CONFIG_DIR}/overrides/a.py" "${CONFIG_SOURCE}"
  done
fi

# ---------------------------------------------------------------------------
# Exit status. The removed debug line came right before 'Command:', so pin the
# statuses again: 0, 1 and 2 for both scripts, 'exit_zero' for check.sh, and
# the 'diff' and 'write' modes for format.sh.
# ---------------------------------------------------------------------------

run_ruff ruff-exit-clean "${EXIT_DIR}" PARAM_TARGETS='clean.py'
expect_status 0

run_ruff ruff-exit-findings "${EXIT_DIR}" PARAM_TARGETS='bad.py'
expect_status 1
expect_log_line "$(diagnostic bad.py)"

run_ruff ruff-exit-configuration-error "${EXIT_DIR}" \
  PARAM_CONFIG_FILE='missing.toml' \
  PARAM_TARGETS='clean.py'
expect_status 2

if [ "${COMMAND}" = 'check' ]; then
  run_ruff ruff-exit-zero-findings "${EXIT_DIR}" \
    PARAM_EXIT_ZERO='true' \
    PARAM_TARGETS='bad.py'
  expect_status 0
  expect_log_line "$(diagnostic bad.py)"

  run_ruff ruff-exit-zero-configuration-error "${EXIT_DIR}" \
    PARAM_CONFIG_FILE='missing.toml' \
    PARAM_EXIT_ZERO='true' \
    PARAM_TARGETS='clean.py'
  expect_status 2
else
  run_ruff ruff-mode-diff "${EXIT_DIR}" \
    PARAM_MODE='diff' \
    PARAM_TARGETS='bad.py'
  expect_status 1
  expect_log_line '+x = 1'

  run_ruff ruff-mode-write "${EXIT_DIR}" \
    PARAM_MODE='write' \
    PARAM_TARGETS='rewrite.py'
  expect_status 0

  if [ "$(cat "${EXIT_DIR}/rewrite.py")" != 'x = 1' ]; then
    fail 'write mode did not reformat rewrite.py'
  fi
fi

echo

if [ "${FAILURES}" -ne 0 ]; then
  echo "${FAILURES} assertion(s) failed across ${CASES} runs of ${SCRIPT#"${ROOT}/"}."
  exit 1
fi

echo "All ${CASES} runs of ${SCRIPT#"${ROOT}/"} met their expectations."
