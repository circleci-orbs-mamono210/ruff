#!/bin/bash
set -eo pipefail

PACKAGES=()

if [ -n "${PARAM_VERSION}" ]; then
  PACKAGES+=("ruff==${PARAM_VERSION}")
else
  # Only an explicit empty 'version' gets here; the default names a version.
  echo 'version is empty: installing the latest Ruff release, which this Orb is not tested with.'
  PACKAGES+=('ruff')
fi

printf 'Installing:'
printf ' %q' "${PACKAGES[@]}"
printf '\n'

python -m pip install --upgrade "${PACKAGES[@]}"
