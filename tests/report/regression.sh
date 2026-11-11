#!/bin/bash
# Regression cases for how src/scripts/check.sh handles 'output-file' and
# 'tee'.
#
# Ruff exits 2 on a configuration or command line error without touching the
# '--output-file' report. A report left over from an earlier run was therefore
# printed as 'Report written to ...' and kept for the artifact as if it were
# the new result. Most cases below first seed the report with STALE_MARKER and
# then assert that the marker reaches neither the log nor the report, and that
# the exit status follows the policy documented in README.md.
#
# Usage, from anywhere inside the repository:
#
#   bash tests/report/regression.sh
#
# The cases need Ruff 0.16.2 on PATH and the PARAM_* defaults written by the
# 'write-check-defaults' command in .circleci/test-deploy.yml. Set
# CHECK_DEFAULTS when that file is not /tmp/check-defaults.sh. The reports of
# the cases that run the real Ruff are kept below REPORT_DIR, which defaults
# to reports/report-regression. Failures are injected with
# tests/report/mock-ruff.sh inside a temporary directory that is removed on
# exit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHECK_DEFAULTS="${CHECK_DEFAULTS:-/tmp/check-defaults.sh}"
REPORT_DIR="${REPORT_DIR:-reports/report-regression}"
STALE_MARKER='ORB-TEST-STALE-REPORT-MARKER'

CASES=0
FAILURES=0
CASE_NAME=''
CASE_LOG=''
CASE_STATUS=0

cd "${ROOT}"

if [ ! -s "${CHECK_DEFAULTS}" ]; then
  echo "PARAM_* defaults not found at '${CHECK_DEFAULTS}'." >&2
  echo "Run the 'write-check-defaults' command or set CHECK_DEFAULTS." >&2
  exit 1
fi

if ! command -v ruff > /dev/null; then
  echo 'Ruff is not on PATH.' >&2
  exit 1
fi

echo "Using $(ruff --version) from $(command -v ruff)"

SCRATCH="$(mktemp -d)"
trap 'chmod -R u+rwX "${SCRATCH}" 2> /dev/null || true; rm -rf "${SCRATCH}"' EXIT

mkdir -p "${SCRATCH}/bin" "${REPORT_DIR}"
cp tests/report/mock-ruff.sh "${SCRATCH}/bin/ruff"
chmod +x "${SCRATCH}/bin/ruff"

MOCK_PATH="${SCRATCH}/bin:${PATH}"
MOCK_CALLS="${SCRATCH}/calls"

fail() {
  echo "FAIL [${CASE_NAME}]: $*"
  FAILURES=$((FAILURES + 1))
}

# seed FILE writes a recognisable report from an "earlier run" to FILE.
seed() {
  mkdir -p "$(dirname "$1")"
  printf '%s\n' "${STALE_MARKER}" > "$1"
}

# run_check NAME VARIABLE=VALUE...
#
# Runs check.sh with the defaults plus the given overrides. Its combined
# output is kept in CASE_LOG and printed, and its exit status is kept in
# CASE_STATUS.
run_check() {
  CASE_NAME="$1"
  shift
  CASE_LOG="${SCRATCH}/${CASE_NAME}.log"
  CASES=$((CASES + 1))

  set +e
  (
    # shellcheck source=/dev/null
    source "${CHECK_DEFAULTS}"

    for assignment in "$@"; do
      export "${assignment?}"
    done

    bash src/scripts/check.sh
  ) > "${CASE_LOG}" 2>&1
  CASE_STATUS=$?
  set -e

  echo
  echo "----- ${CASE_NAME} (exit status ${CASE_STATUS}) -----"
  sed 's/^/  | /' "${CASE_LOG}"
}

expect_status() {
  if [ "${CASE_STATUS}" -ne "$1" ]; then
    fail "expected exit status $1, got ${CASE_STATUS}"
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

expect_file_has() {
  if [ ! -f "$1" ] || ! grep -Fq -- "$2" "$1"; then
    fail "$1 does not contain '$2'"
  fi
}

expect_file_lacks() {
  if [ -f "$1" ] && grep -Fq -- "$2" "$1"; then
    fail "$1 contains '$2'"
  fi
}

expect_file_empty() {
  if [ ! -f "$1" ] || [ -s "$1" ]; then
    fail "$1 is not an empty regular file"
  fi
}

# expect_no_stale FILE asserts that the seeded report reached neither the log
# nor FILE.
expect_no_stale() {
  expect_log_lacks "${STALE_MARKER}"
  expect_file_lacks "$1" "${STALE_MARKER}"
}

expect_ruff_calls() {
  local calls=0

  if [ -f "${MOCK_CALLS}" ]; then
    calls="$(wc -l < "${MOCK_CALLS}")"
    calls=$((calls))
  fi

  if [ "${calls}" -ne "$1" ]; then
    fail "expected Ruff to be started $1 time(s), got ${calls}"
  fi
}

# prime_with_violation NAME FILE leaves a real F401 report in FILE, so that the
# next case starts from a report an earlier run actually wrote.
prime_with_violation() {
  run_check "$1" \
    PARAM_OUTPUT_FILE="$2" \
    PARAM_TARGETS='tests/violations/unused_import.py'
  expect_status 1
  expect_file_has "$2" 'F401'
}

# ---------------------------------------------------------------------------
# Success, violations and a configuration error, each with tee on and off.
# The missing config file is the original report: Ruff 0.16.2 exits 2 and
# leaves the seeded report untouched.
# ---------------------------------------------------------------------------

REPORT="${REPORT_DIR}/success-tee.txt"
seed "${REPORT}"
run_check success-tee \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean'
expect_status 0
expect_no_stale "${REPORT}"
expect_file_has "${REPORT}" 'All checks passed!'
expect_log_has "Report written to ${REPORT}:"
expect_log_has 'All checks passed!'

REPORT="${REPORT_DIR}/success-no-tee.txt"
seed "${REPORT}"
run_check success-no-tee \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean' \
  PARAM_TEE='false'
expect_status 0
expect_no_stale "${REPORT}"
expect_file_has "${REPORT}" 'All checks passed!'
expect_log_lacks 'All checks passed!'
expect_log_lacks 'Report written to'

REPORT="${REPORT_DIR}/violations-tee.txt"
seed "${REPORT}"
run_check violations-tee \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/violations/unused_import.py'
expect_status 1
expect_no_stale "${REPORT}"
expect_file_has "${REPORT}" 'F401'
expect_log_has "Report written to ${REPORT}:"
expect_log_has 'F401'

REPORT="${REPORT_DIR}/violations-no-tee.txt"
seed "${REPORT}"
run_check violations-no-tee \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/violations/unused_import.py' \
  PARAM_TEE='false'
expect_status 1
expect_no_stale "${REPORT}"
expect_file_has "${REPORT}" 'F401'
expect_log_lacks 'F401'
expect_log_lacks 'Report written to'

REPORT="${REPORT_DIR}/config-error-tee.txt"
seed "${REPORT}"
run_check config-error-tee \
  PARAM_CONFIG_FILE='no-such-config.toml' \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean'
expect_status 2
expect_no_stale "${REPORT}"
expect_file_empty "${REPORT}"
expect_log_has 'no-such-config.toml'
expect_log_has "Report ${REPORT} is empty."
expect_log_lacks 'Report written to'

REPORT="${REPORT_DIR}/config-error-no-tee.txt"
seed "${REPORT}"
run_check config-error-no-tee \
  PARAM_CONFIG_FILE='no-such-config.toml' \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean' \
  PARAM_TEE='false'
expect_status 2
expect_no_stale "${REPORT}"
expect_file_empty "${REPORT}"
expect_log_lacks 'Report written to'
expect_log_lacks 'is empty.'

# exit-zero is the usual setting of a reporting step. It turns violations into
# 0 but must not hide a configuration error.
REPORT="${REPORT_DIR}/exit-zero-violations.txt"
seed "${REPORT}"
run_check exit-zero-violations \
  PARAM_EXIT_ZERO='true' \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/violations/unused_import.py'
expect_status 0
expect_no_stale "${REPORT}"
expect_file_has "${REPORT}" 'F401'
expect_log_has 'F401'

REPORT="${REPORT_DIR}/exit-zero-config-error.txt"
seed "${REPORT}"
run_check exit-zero-config-error \
  PARAM_CONFIG_FILE='no-such-config.toml' \
  PARAM_EXIT_ZERO='true' \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean'
expect_status 2
expect_no_stale "${REPORT}"
expect_file_empty "${REPORT}"

# ---------------------------------------------------------------------------
# Repeated runs into the same file. Each case starts from a report that an
# earlier run really wrote, which is the situation a CI job meets when a step
# is retried or a report path is reused.
# ---------------------------------------------------------------------------

REPORT="${REPORT_DIR}/rerun.txt"
seed "${REPORT}"
prime_with_violation rerun-first "${REPORT}"
cp "${REPORT}" "${SCRATCH}/rerun-first.txt"
run_check rerun-same-result \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/violations/unused_import.py'
expect_status 1
expect_no_stale "${REPORT}"

if ! cmp -s "${SCRATCH}/rerun-first.txt" "${REPORT}"; then
  fail 'the second run did not leave the same report as the first one'
fi

if [ "$(grep -c 'F401' "${REPORT}")" -ne 1 ]; then
  fail 'the report was appended to instead of replaced'
fi

REPORT="${REPORT_DIR}/rerun-clean.txt"
prime_with_violation rerun-clean-first "${REPORT}"
run_check rerun-clean \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean'
expect_status 0
expect_file_has "${REPORT}" 'All checks passed!'
expect_file_lacks "${REPORT}" 'F401'
expect_log_lacks 'F401'

# 'quiet' on a clean target and 'silent' on a violation leave the report
# empty. Neither may be mistaken for the earlier F401 report.
REPORT="${REPORT_DIR}/rerun-empty-success.txt"
prime_with_violation rerun-empty-success-first "${REPORT}"
run_check rerun-empty-success \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean' \
  PARAM_VERBOSITY='quiet'
expect_status 0
expect_file_empty "${REPORT}"
expect_log_has "Report ${REPORT} is empty."
expect_log_lacks 'F401'

REPORT="${REPORT_DIR}/rerun-empty-failure.txt"
prime_with_violation rerun-empty-failure-first "${REPORT}"
run_check rerun-empty-failure \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/violations/unused_import.py' \
  PARAM_VERBOSITY='silent'
expect_status 1
expect_file_empty "${REPORT}"
expect_log_has "Report ${REPORT} is empty."
expect_log_lacks 'F401'

REPORT="${REPORT_DIR}/rerun-config-error.txt"
prime_with_violation rerun-config-error-first "${REPORT}"
run_check rerun-config-error \
  PARAM_CONFIG_FILE='no-such-config.toml' \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean'
expect_status 2
expect_file_empty "${REPORT}"
expect_log_lacks 'F401'
expect_log_lacks 'Report written to'

# ---------------------------------------------------------------------------
# The report cannot be prepared. The step must fail before Ruff is started,
# which the mock records, and must not print what an old file holds.
# ---------------------------------------------------------------------------

printf 'a regular file, not a directory\n' > "${SCRATCH}/blocker"
rm -f "${MOCK_CALLS}"
run_check prepare-parent-is-a-file \
  MOCK_RUFF_CALLS="${MOCK_CALLS}" \
  PATH="${MOCK_PATH}" \
  PARAM_OUTPUT_FILE="${SCRATCH}/blocker/report.txt" \
  PARAM_TARGETS='tests/clean'
expect_status 2
expect_ruff_calls 0
expect_log_has 'so Ruff was not run'

REPORT="${SCRATCH}/report-is-a-directory"
seed "${REPORT}/old-report.txt"
rm -f "${MOCK_CALLS}"
run_check prepare-path-is-a-directory \
  MOCK_RUFF_CALLS="${MOCK_CALLS}" \
  PATH="${MOCK_PATH}" \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean'
expect_status 2
expect_ruff_calls 0
expect_log_has 'so Ruff was not run'
expect_log_lacks "${STALE_MARKER}"
expect_file_has "${REPORT}/old-report.txt" "${STALE_MARKER}"

# Root can write to a read-only file, so this case only proves something for
# an ordinary user, which is what the CircleCI convenience images run as.
if [ "$(id -u)" -eq 0 ]; then
  echo
  echo '----- prepare-read-only-report (skipped: running as root) -----'
else
  REPORT="${SCRATCH}/read-only.txt"
  seed "${REPORT}"
  chmod 0444 "${REPORT}"
  rm -f "${MOCK_CALLS}"
  run_check prepare-read-only-report \
    MOCK_RUFF_CALLS="${MOCK_CALLS}" \
    PATH="${MOCK_PATH}" \
    PARAM_OUTPUT_FILE="${REPORT}" \
    PARAM_TARGETS='tests/clean'
  expect_status 2
  expect_ruff_calls 0
  expect_log_has 'so Ruff was not run'
  expect_log_lacks "${STALE_MARKER}"
fi

# ---------------------------------------------------------------------------
# The report cannot be read back for tee. A run that Ruff passed must fail
# with 2, and a status Ruff already failed with must be returned unchanged.
# ---------------------------------------------------------------------------

for ruff_status in 0 1 2; do
  case "${ruff_status}" in
    0)
      expected_status=2
      ;;
    *)
      expected_status="${ruff_status}"
      ;;
  esac

  REPORT="${SCRATCH}/unreadable-${ruff_status}.txt"
  seed "${REPORT}"
  rm -f "${MOCK_CALLS}"
  run_check "read-fails-after-ruff-exits-${ruff_status}" \
    MOCK_RUFF_ACTION='directory' \
    MOCK_RUFF_CALLS="${MOCK_CALLS}" \
    MOCK_RUFF_STATUS="${ruff_status}" \
    PATH="${MOCK_PATH}" \
    PARAM_OUTPUT_FILE="${REPORT}" \
    PARAM_TARGETS='tests/clean'
  expect_status "${expected_status}"
  expect_ruff_calls 1
  expect_log_has "Could not read the report file '${REPORT}'."
  expect_log_lacks 'Report written to'
  expect_log_lacks "${STALE_MARKER}"
done

REPORT="${SCRATCH}/removed.txt"
seed "${REPORT}"
rm -f "${MOCK_CALLS}"
run_check read-fails-after-report-removed \
  MOCK_RUFF_ACTION='remove' \
  MOCK_RUFF_CALLS="${MOCK_CALLS}" \
  MOCK_RUFF_STATUS='0' \
  PATH="${MOCK_PATH}" \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean'
expect_status 2
expect_ruff_calls 1
expect_log_has "Could not read the report file '${REPORT}'."

# With tee disabled the report is never read, so the same damage cannot fail
# the step. This pins down that tee: false leaves the report alone.
REPORT="${SCRATCH}/not-read.txt"
seed "${REPORT}"
rm -f "${MOCK_CALLS}"
run_check no-read-without-tee \
  MOCK_RUFF_ACTION='directory' \
  MOCK_RUFF_CALLS="${MOCK_CALLS}" \
  MOCK_RUFF_STATUS='0' \
  PATH="${MOCK_PATH}" \
  PARAM_OUTPUT_FILE="${REPORT}" \
  PARAM_TARGETS='tests/clean' \
  PARAM_TEE='false'
expect_status 0
expect_ruff_calls 1
expect_log_lacks 'Could not read the report file'

echo
echo "Kept reports below ${REPORT_DIR}:"
ls -l "${REPORT_DIR}"

if [ "${FAILURES}" -ne 0 ]; then
  echo "${FAILURES} assertion(s) failed across ${CASES} runs of check.sh."
  exit 1
fi

echo "All ${CASES} runs of check.sh met their expectations."
