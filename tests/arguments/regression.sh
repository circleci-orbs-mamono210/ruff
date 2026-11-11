#!/bin/bash
# Regression cases for how src/scripts/check.sh and src/scripts/format.sh pass
# 'targets' and 'extensions' to Ruff.
#
# Both scripts used to read only the first line of each parameter, so paths
# and mappings on later lines were silently dropped. The paths also reached
# Ruff without '--': a target named '--help' ran as an option, '-' made Ruff
# read standard input and '@args' was expanded as an argument file.
#
# Usage, from anywhere inside the repository:
#
#   bash tests/arguments/regression.sh check
#   bash tests/arguments/regression.sh format
#
# Both need Ruff 0.16.2 on PATH. 'check' also needs the PARAM_* defaults
# written by the 'write-check-defaults' command in .circleci/test-deploy.yml;
# set CHECK_DEFAULTS when that file is not /tmp/check-defaults.sh. 'format'
# carries the defaults of src/commands/format.yml below.
#
# The argument cases put a copy of tests/arguments/record-ruff.sh first on
# PATH and compare what it receives with the expected lists: the paths after
# '--' and the value of every '--extension'. The 'Command:' line must show
# exactly the arguments received. The Ruff cases run the real Ruff on files
# named '-', '--help' and '@args', on extensions given on several lines and on
# empty targets, and pin the exit status. Everything runs in a temporary
# directory that is removed on exit, so nothing is written to tests/ or
# reports/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMMAND="${1:-}"
CHECK_DEFAULTS="${CHECK_DEFAULTS:-/tmp/check-defaults.sh}"

# The defaults of src/commands/format.yml, spelled out the same way as in the
# format-tests steps of .circleci/test-deploy.yml.
FORMAT_DEFAULTS=(
  PARAM_CACHE_DIR=''
  PARAM_COLOR='auto'
  PARAM_CONFIG_FILE=''
  PARAM_CONFIG_OVERRIDES=''
  PARAM_EXCLUDED_PATHS=''
  PARAM_EXIT_NON_ZERO_ON_FORMAT='false'
  PARAM_EXTEND_EXCLUDED_PATHS=''
  PARAM_EXTENSIONS=''
  PARAM_EXTRA_ARGS=''
  PARAM_FORCE_EXCLUDE='auto'
  PARAM_ISOLATED='false'
  PARAM_LINE_LENGTH=''
  PARAM_MODE='check'
  PARAM_NO_CACHE='false'
  PARAM_OUTPUT_FORMAT='default'
  PARAM_PREVIEW='auto'
  PARAM_RESPECT_GITIGNORE='auto'
  PARAM_TARGETS='.'
  PARAM_TARGET_VERSION='default'
  PARAM_VERBOSITY='default'
)

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
BEFORE=()
AFTER=()
SEPARATOR=''

if [ "${COMMAND}" = 'check' ] && [ ! -s "${CHECK_DEFAULTS}" ]; then
  echo "PARAM_* defaults not found at '${CHECK_DEFAULTS}'." >&2
  echo "Run the 'write-check-defaults' command or set CHECK_DEFAULTS." >&2
  exit 1
fi

if ! command -v ruff > /dev/null; then
  echo 'Ruff is not on PATH.' >&2
  exit 1
fi

echo "Testing ${SCRIPT#"${ROOT}/"} with $(ruff --version) from $(command -v ruff)"

SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

MOCK_BIN="${SCRATCH}/bin"
ARGV_FILE="${SCRATCH}/argv"
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

fail() {
  echo "FAIL [${COMMAND} ${CASE_NAME}]: $*"
  FAILURES=$((FAILURES + 1))
}

load_defaults() {
  local assignment

  if [ "${COMMAND}" = 'check' ]; then
    # shellcheck source=/dev/null
    source "${CHECK_DEFAULTS}"
  else
    for assignment in "${FORMAT_DEFAULTS[@]}"; do
      export "${assignment?}"
    done
  fi
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
# exactly the arguments the stand-in received.
run_mock() {
  local name="$1"
  shift

  rm -f "${ARGV_FILE}"
  run_case "${name}" "${MOCK_DIR}" \
    PATH="${MOCK_BIN}:${PATH}" \
    RECORD_RUFF_ARGV="${ARGV_FILE}" \
    "$@"
  expect_status 0
  load_argv

  if [ "${#ARGV[@]}" -gt 0 ]; then
    expect_log_line "Command:$(printf ' %q' ruff "${ARGV[@]}")"
  fi
}

# run_ruff NAME DIRECTORY VARIABLE=VALUE... runs a case with the real Ruff.
# Concise output puts each finding on one line that starts with the file name.
run_ruff() {
  local name="$1"
  local directory="$2"
  shift 2

  run_case "${name}" "${directory}" PARAM_OUTPUT_FORMAT='concise' "$@"

  if ! grep -q '^Command:.* -- ' "${CASE_LOG}"; then
    fail "the 'Command:' line does not show '--'"
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
# Exit status. The removed debug line came right before 'Command:', so pin the
# statuses again: 0, 1 and 2 for both scripts, 'exit-zero' for check.sh, and
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
