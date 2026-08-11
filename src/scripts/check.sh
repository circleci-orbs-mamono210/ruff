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

# '--fix-only' implies '--fix' and wins over '--no-fix', so Ruff would rewrite
# the checkout even though 'fix: never' asked for it to stay untouched. Refuse
# the combination instead of letting a job modify files it was told not to.
if is_true "${PARAM_FIX_ONLY}" && [ "${PARAM_FIX}" = 'never' ]; then
  echo \
    "'fix-only' rewrites files, so it needs 'fix' set to 'auto', 'safe' or 'unsafe'." \
    >&2
  exit 1
fi

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

# 'ruff check' still accepts '--line-length', but the flag is absent from its
# help output and is not part of the documented interface. The equivalent
# config override is stable, so use that instead.
if [ -n "${PARAM_LINE_LENGTH}" ]; then
  RUFF_ARGS+=('--config' "line-length = ${PARAM_LINE_LENGTH}")
fi

if [ -n "${PARAM_SELECTED_RULES}" ]; then
  RUFF_ARGS+=('--select' "${PARAM_SELECTED_RULES}")
fi

if [ -n "${PARAM_EXTEND_SELECTED_RULES}" ]; then
  RUFF_ARGS+=('--extend-select' "${PARAM_EXTEND_SELECTED_RULES}")
fi

if [ -n "${PARAM_IGNORED_RULES}" ]; then
  RUFF_ARGS+=('--ignore' "${PARAM_IGNORED_RULES}")
fi

if [ -n "${PARAM_PER_FILE_IGNORES}" ]; then
  RUFF_ARGS+=('--per-file-ignores' "${PARAM_PER_FILE_IGNORES}")
fi

if [ -n "${PARAM_EXTEND_PER_FILE_IGNORES}" ]; then
  RUFF_ARGS+=('--extend-per-file-ignores' "${PARAM_EXTEND_PER_FILE_IGNORES}")
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

case "${PARAM_FIX}" in
  never)
    RUFF_ARGS+=('--no-fix')
    ;;
  safe)
    RUFF_ARGS+=('--fix' '--no-unsafe-fixes')
    ;;
  unsafe)
    RUFF_ARGS+=('--fix' '--unsafe-fixes')
    ;;
  *)
    ;;
esac

if is_true "${PARAM_FIX_ONLY}"; then
  RUFF_ARGS+=('--fix-only')
fi

if [ -n "${PARAM_FIXABLE}" ]; then
  RUFF_ARGS+=('--fixable' "${PARAM_FIXABLE}")
fi

if [ -n "${PARAM_UNFIXABLE}" ]; then
  RUFF_ARGS+=('--unfixable' "${PARAM_UNFIXABLE}")
fi

case "${PARAM_SHOW_FIXES}" in
  enabled)
    RUFF_ARGS+=('--show-fixes')
    ;;
  disabled)
    RUFF_ARGS+=('--no-show-fixes')
    ;;
  *)
    ;;
esac

if is_true "${PARAM_DIFF}"; then
  RUFF_ARGS+=('--diff')
fi

if is_true "${PARAM_IGNORE_NOQA}"; then
  RUFF_ARGS+=('--ignore-noqa')
fi

if is_true "${PARAM_STATISTICS}"; then
  RUFF_ARGS+=('--statistics')
fi

if [ "${PARAM_OUTPUT_FORMAT}" != 'default' ]; then
  RUFF_ARGS+=('--output-format' "${PARAM_OUTPUT_FORMAT}")
fi

# Ruff creates the parent directories and truncates the file itself, so no
# preparation is needed here.
if [ -n "${PARAM_OUTPUT_FILE}" ]; then
  RUFF_ARGS+=('--output-file' "${PARAM_OUTPUT_FILE}")
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

if is_true "${PARAM_EXIT_NON_ZERO_ON_FIX}"; then
  RUFF_ARGS+=('--exit-non-zero-on-fix')
fi

if is_true "${PARAM_EXIT_ZERO}"; then
  RUFF_ARGS+=('--exit-zero')
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

printf 'PARAM_EXIT_ZERO=%q\n' "${PARAM_EXIT_ZERO}"
printf 'Command:'
printf ' %q' ruff check "${RUFF_ARGS[@]}" "${TARGETS[@]}"
printf '\n'

STATUS=0

set +e
ruff check "${RUFF_ARGS[@]}" "${TARGETS[@]}"
STATUS=$?
set -e

# Ruff writes to '--output-file' INSTEAD of standard output and has no '--tee'
# of its own, so the report is echoed back here to keep it in the job log.
if [ -n "${PARAM_OUTPUT_FILE}" ] && is_true "${PARAM_TEE}"; then
  if [ -f "${PARAM_OUTPUT_FILE}" ]; then
    echo "Report written to ${PARAM_OUTPUT_FILE}:"
    cat "${PARAM_OUTPUT_FILE}"
  fi
fi

# 'exit-zero' applies to reported violations only. Ruff exits 2 for a missing
# config file or a command line error, and that status is preserved here.
# A path that does not exist is reported as a violation, so it exits 1 and IS
# masked by 'exit-zero'.
exit "${STATUS}"
