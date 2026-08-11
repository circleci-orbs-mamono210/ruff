#!/bin/bash
set -eo pipefail

PACKAGES=()

if [ -n "${PARAM_VERSION}" ]; then
  PACKAGES+=("ruff==${PARAM_VERSION}")
else
  PACKAGES+=('ruff')
fi

printf 'Installing:'
printf ' %q' "${PACKAGES[@]}"
printf '\n'

python -m pip install --upgrade "${PACKAGES[@]}"
