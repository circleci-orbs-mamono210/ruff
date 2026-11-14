#!/bin/bash
# Keeps the files under tests/ as the commit has them while the tests run.
#
# Usage, from anywhere inside the repository:
#
#   bash tests/fixtures.sh record SNAPSHOT
#   bash tests/fixtures.sh verify SNAPSHOT
#
# 'record' fails unless every fixture listed below exists and has content,
# and then writes the SHA-256 of every file under tests/ to SNAPSHOT. Ruff
# exits 0 when it finds no Python files, so a missing fixture could otherwise
# let a test pass for the wrong reason. SNAPSHOT must not exist yet: it is
# taken once, right after the checkout, and a second 'record' later in the
# job cannot replace it with fixtures that a test has changed.
#
# 'verify' compares the files under tests/ with SNAPSHOT and fails when one
# was changed, removed or added. A test that rewrites a fixture has to restore
# it. Verifying after such a test, and at the end of the job, shows that it
# did before a later test can pass because of the change.
#
# A relative SNAPSHOT is taken from the current directory. The paths in it
# are relative to the root of the repository.
set -euo pipefail

FIXTURES=(
  tests/clean/compliant.py
  tests/line-length/formatted_at_40.py
  tests/unformatted/spacing.py
  tests/violations/undefined_name.py
  tests/violations/unsorted_imports.py
  tests/violations/unused_import.py
)

if [ "$#" -ne 2 ] || { [ "$1" != 'record' ] && [ "$1" != 'verify' ]; }; then
  echo 'Usage: bash tests/fixtures.sh record|verify SNAPSHOT' >&2
  exit 2
fi

ACTION="$1"
SNAPSHOT="$2"

case "${SNAPSHOT}" in
  /*)
    ;;
  *)
    SNAPSHOT="${PWD}/${SNAPSHOT}"
    ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# SHA-256 of every regular file under tests/, sorted by path.
hash_tests() {
  find tests -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum --
}

if [ "${ACTION}" = 'record' ]; then
  if [ -e "${SNAPSHOT}" ]; then
    echo "${SNAPSHOT} exists already. The snapshot is taken once, right after the checkout." >&2
    exit 1
  fi

  missing=0

  for fixture in "${FIXTURES[@]}"; do
    if [ ! -f "${fixture}" ] || [ ! -s "${fixture}" ]; then
      echo "Missing or empty fixture: ${fixture}" >&2
      missing=1
    fi
  done

  if [ "${missing}" -ne 0 ]; then
    exit 1
  fi

  hash_tests > "${SNAPSHOT}"

  echo "All ${#FIXTURES[@]} fixtures are present."
  echo "Snapshot of $(wc -l < "${SNAPSHOT}") files under tests/ in ${SNAPSHOT}:"
  cat "${SNAPSHOT}"
  exit 0
fi

if [ ! -s "${SNAPSHOT}" ]; then
  echo "No snapshot in ${SNAPSHOT}. Run 'record' right after the checkout." >&2
  exit 1
fi

current="$(mktemp)"
trap 'rm -f "${current}"' EXIT

hash_tests > "${current}"

set +e
diff -u "${SNAPSHOT}" "${current}"
status=$?
set -e

case "${status}" in
  0)
    echo "All $(wc -l < "${SNAPSHOT}") files under tests/ match the snapshot."
    ;;
  1)
    echo 'The files under tests/ differ from the snapshot taken after the checkout.' >&2
    echo "Lines starting with '-' are the snapshot, lines starting with '+' are now." >&2
    exit 1
    ;;
  *)
    echo "Could not compare the files under tests/ with ${SNAPSHOT}." >&2
    exit 1
    ;;
esac
