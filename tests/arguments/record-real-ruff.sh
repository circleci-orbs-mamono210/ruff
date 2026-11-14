#!/bin/bash
# Stand-in for the 'ruff' executable that records the arguments it receives,
# like record-ruff.sh, and then runs the real Ruff with them.
# tests/arguments/format-parameters.py puts a copy named 'ruff' first on PATH,
# so a case can compare the arguments Ruff actually received with what Ruff
# printed and did, instead of trusting the 'Command:' line.
#
# Every call, including 'ruff --version', appends one line to the file named
# by RECORD_RUFF_CALLS. Any other call writes its arguments, NUL separated, to
# the file named by RECORD_RUFF_ARGV, replacing what an earlier call wrote.
# Then the Ruff named by RECORD_RUFF_REAL runs with the same arguments,
# standard input, output and error, and its exit status is the exit status.
set -euo pipefail

printf '%q ' ruff "$@" >> "${RECORD_RUFF_CALLS:?}"
printf '\n' >> "${RECORD_RUFF_CALLS}"

if [ "$#" -ne 1 ] || [ "$1" != '--version' ]; then
  printf '%s\0' "$@" > "${RECORD_RUFF_ARGV:?}"
fi

exec "${RECORD_RUFF_REAL:?}" "$@"
