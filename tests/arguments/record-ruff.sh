#!/bin/bash
# Stand-in for the 'ruff' executable that records the arguments it receives.
# tests/arguments/regression.sh puts a copy named 'ruff' first on PATH, so a
# case can compare the exact argument array instead of the 'Command:' line.
#
# Each call writes its arguments, NUL separated, to the file named by
# RECORD_RUFF_ARGV, replacing whatever an earlier call wrote, and exits 0.
set -euo pipefail

printf '%s\0' "$@" > "${RECORD_RUFF_ARGV:?}"
