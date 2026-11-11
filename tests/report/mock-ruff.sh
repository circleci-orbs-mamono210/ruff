#!/bin/bash
# Stand-in for the 'ruff' executable. tests/report/regression.sh puts a copy
# named 'ruff' first on PATH to produce situations that the real Ruff cannot
# be asked for, such as a report that disappears after a successful run.
#
# check.sh prints 'ruff --version' once its input checks have passed. That
# call is answered with a version line and is not recorded. Every other call
# appends its command line to the file named by MOCK_RUFF_CALLS, so a test can
# tell whether 'ruff check' was started at all. MOCK_RUFF_ACTION decides
# what happens to the '--output-file' path: 'keep' leaves it alone, 'remove'
# deletes it and 'directory' replaces it with a directory, which cannot be
# read as a file. The mock then exits with MOCK_RUFF_STATUS.
set -euo pipefail

if [ "$#" -eq 1 ] && [ "$1" = '--version' ]; then
  echo 'ruff 0.0.0 (tests/report/mock-ruff.sh)'
  exit 0
fi

output_file=''
previous=''

for argument in "$@"; do
  if [ "${previous}" = '--output-file' ]; then
    output_file="${argument}"
  fi
  previous="${argument}"
done

printf '%q ' ruff "$@" >> "${MOCK_RUFF_CALLS:?}"
printf '\n' >> "${MOCK_RUFF_CALLS}"

if [ -n "${output_file}" ]; then
  case "${MOCK_RUFF_ACTION:-keep}" in
    keep)
      ;;
    remove)
      rm -f -- "${output_file}"
      ;;
    directory)
      rm -f -- "${output_file}"
      mkdir -- "${output_file}"
      ;;
    *)
      echo "Unknown MOCK_RUFF_ACTION '${MOCK_RUFF_ACTION}'." >&2
      exit 99
      ;;
  esac
fi

exit "${MOCK_RUFF_STATUS:-0}"
