#!/bin/bash
# Stand-in for the 'ruff' executable that records the arguments it receives.
# tests/arguments/regression.sh puts a copy named 'ruff' first on PATH, so a
# case can compare the exact argument array instead of the 'Command:' line.
#
# Every call, including 'ruff --version', appends one line to the file named
# by RECORD_RUFF_CALLS, so a case can tell that Ruff was not started at all.
# 'ruff --version' then prints a version line and exits 0. Any other call
# writes its arguments, NUL separated, to the file named by RECORD_RUFF_ARGV,
# replacing what an earlier call wrote, and exits 0.
set -euo pipefail

printf '%q ' ruff "$@" >> "${RECORD_RUFF_CALLS:?}"
printf '\n' >> "${RECORD_RUFF_CALLS}"

if [ "$#" -eq 1 ] && [ "$1" = '--version' ]; then
  echo 'ruff 0.0.0 (tests/arguments/record-ruff.sh)'
  exit 0
fi

printf '%s\0' "$@" > "${RECORD_RUFF_ARGV:?}"
