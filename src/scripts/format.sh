#!/bin/bash
set -eo pipefail

RUFF_ARGS=()
EXTRA_ARGS=()
EXTENSIONS=()
TARGETS=()

is_true() {
  case "${1,,}" in
    true | 1 | yes | on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

case "${PARAM_MODE}" in
  check)
    RUFF_ARGS+=('--check')
    ;;
  diff)
    RUFF_ARGS+=('--diff')
    ;;
  write)
    ;;
  *)
    echo "Unknown mode '${PARAM_MODE}'." >&2
    exit 1
    ;;
esac

if is_true "${PARAM_ISOLATED}"; then
  RUFF_ARGS+=('--isolated')
fi

if [ -n "${PARAM_CONFIG_FILE}" ]; then
  RUFF_ARGS+=('--config' "${PARAM_CONFIG_FILE}")
fi

# Each override is a TOML 'KEY = VALUE' pair containing whitespace, so the
# parameter is split on newlines rather than on whitespace.
if [ -n "${PARAM_CONFIG_OVERRIDES}" ]; then
  while IFS= read -r line; do
    if [ -n "${line//[[:space:]]/}" ]; then
      RUFF_ARGS+=('--config' "${line}")
    fi
  done <<< "${PARAM_CONFIG_OVERRIDES}"
fi

if [ -n "${PARAM_LINE_LENGTH}" ]; then
  RUFF_ARGS+=('--line-length' "${PARAM_LINE_LENGTH}")
fi

if [ -n "${PARAM_EXCLUDED_PATHS}" ]; then
  RUFF_ARGS+=('--exclude' "${PARAM_EXCLUDED_PATHS}")
fi

if [ -n "${PARAM_EXTEND_EXCLUDED_PATHS}" ]; then
  RUFF_ARGS+=('--extend-exclude' "${PARAM_EXTEND_EXCLUDED_PATHS}")
fi

case "${PARAM_FORCE_EXCLUDE}" in
  enabled)
    RUFF_ARGS+=('--force-exclude')
    ;;
  disabled)
    RUFF_ARGS+=('--no-force-exclude')
    ;;
  *)
    ;;
esac

case "${PARAM_RESPECT_GITIGNORE}" in
  enabled)
    RUFF_ARGS+=('--respect-gitignore')
    ;;
  disabled)
    RUFF_ARGS+=('--no-respect-gitignore')
    ;;
  *)
    ;;
esac

case "${PARAM_PREVIEW}" in
  enabled)
    RUFF_ARGS+=('--preview')
    ;;
  disabled)
    RUFF_ARGS+=('--no-preview')
    ;;
  *)
    ;;
esac

if [ "${PARAM_TARGET_VERSION}" != 'default' ]; then
  RUFF_ARGS+=('--target-version' "${PARAM_TARGET_VERSION}")
fi

# Split extensions on shell whitespace without evaluating shell syntax or
# performing pathname expansion. Ruff takes one mapping per flag.
if [ -n "${PARAM_EXTENSIONS}" ]; then
  read -r -a EXTENSIONS <<< "${PARAM_EXTENSIONS}"

  for extension in "${EXTENSIONS[@]}"; do
    RUFF_ARGS+=('--extension' "${extension}")
  done
fi

if [ "${PARAM_OUTPUT_FORMAT}" != 'default' ]; then
  RUFF_ARGS+=('--output-format' "${PARAM_OUTPUT_FORMAT}")
fi

case "${PARAM_COLOR}" in
  always | never)
    RUFF_ARGS+=('--color' "${PARAM_COLOR}")
    ;;
  *)
    ;;
esac

if is_true "${PARAM_NO_CACHE}"; then
  RUFF_ARGS+=('--no-cache')
fi

if [ -n "${PARAM_CACHE_DIR}" ]; then
  RUFF_ARGS+=('--cache-dir' "${PARAM_CACHE_DIR}")
fi

case "${PARAM_VERBOSITY}" in
  verbose)
    RUFF_ARGS+=('--verbose')
    ;;
  quiet)
    RUFF_ARGS+=('--quiet')
    ;;
  silent)
    RUFF_ARGS+=('--silent')
    ;;
  *)
    ;;
esac

if is_true "${PARAM_EXIT_NON_ZERO_ON_FORMAT}"; then
  RUFF_ARGS+=('--exit-non-zero-on-format')
fi

# Split extra-args on shell whitespace without evaluating shell syntax or
# performing pathname expansion.
if [ -n "${PARAM_EXTRA_ARGS}" ]; then
  read -r -a EXTRA_ARGS <<< "${PARAM_EXTRA_ARGS}"
  RUFF_ARGS+=("${EXTRA_ARGS[@]}")
fi

# Split targets on shell whitespace without performing pathname expansion.
# Paths containing whitespace are not supported by this parameter format.
read -r -a TARGETS <<< "${PARAM_TARGETS}"

printf 'PARAM_MODE=%q\n' "${PARAM_MODE}"
printf 'Command:'
printf ' %q' ruff format "${RUFF_ARGS[@]}" "${TARGETS[@]}"
printf '\n'

STATUS=0

set +e
ruff format "${RUFF_ARGS[@]}" "${TARGETS[@]}"
STATUS=$?
set -e

# In 'check' and 'diff' mode Ruff exits 1 when a file would be reformatted and
# 2 on a configuration or command line error, so both keep failing the step.
# 'ruff format' has no '--exit-zero'.
exit "${STATUS}"
