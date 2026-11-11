#!/bin/bash
set -eo pipefail

RUFF_ARGS=()
EXTRA_ARGS=()
EXTENSIONS=()
REJECTED=()
TARGET_WORDS=()
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

# ---------------------------------------------------------------------------
# Input checks. Everything down to 'ruff --version' only reads the parameters:
# Ruff is not started and no file is written until every check has passed, so
# a refused run leaves the checkout as it was.
# tests/arguments/packed-commands.py checks this order in the packed command.
# ---------------------------------------------------------------------------

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

# Split extra-args on spaces, tabs and newlines, like targets and extensions
# below, so every line counts and empty lines vanish. Nothing is evaluated:
# quotes, '$', '~' and glob characters stay literal, and an argument that
# contains whitespace cannot be expressed.
IFS=$' \t\n' read -r -d '' -a EXTRA_ARGS \
  < <(printf '%s\0' "${PARAM_EXTRA_ARGS}")

# extra-args is passed through as it is, with one exception that applies in
# every mode: '--' and '@name' would change how the rest of the command line
# is read. The script puts '--' before the paths itself, and Ruff expands
# '@name' as an argument file wherever it appears. The check looks at the
# split items alone; short options and the values of other options are not
# interpreted.
for argument in "${EXTRA_ARGS[@]}"; do
  case "${argument}" in
    --)
      REJECTED+=("'--': the paths come from 'targets', and '--' is added for them")
      ;;
    @*)
      REJECTED+=("'${argument}': Ruff would read an item that starts with '@' as an argument file")
      ;;
    *)
      ;;
  esac
done

if [ "${#REJECTED[@]}" -ne 0 ]; then
  {
    echo "'extra-args' contains items that are not accepted, so Ruff was not run:"
    printf '  %s\n' "${REJECTED[@]}"
  } >&2
  exit 1
fi

# The checks have passed. Show which Ruff runs the command.
ruff --version

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

# Split extensions on spaces, tabs and newlines, so every line counts and
# empty lines vanish. Nothing is evaluated: quotes, '$', '~' and glob
# characters stay literal. printf ends the value with a NUL, which no
# parameter can contain, so read takes the whole value at once. If it cannot
# be read, the script stops instead of carrying on without the mappings. Ruff
# takes one mapping per flag.
IFS=$' \t\n' read -r -d '' -a EXTENSIONS \
  < <(printf '%s\0' "${PARAM_EXTENSIONS}")

for extension in "${EXTENSIONS[@]}"; do
  RUFF_ARGS+=('--extension' "${extension}")
done

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

# extra-args was split and checked at the top of the script.
RUFF_ARGS+=("${EXTRA_ARGS[@]}")

# targets holds paths and nothing else. It is split like extensions, and an
# empty or blank value means the working directory. The paths follow '--', so
# none is read as an option. A relative path that starts with '-' or '@' also
# gets './' in front: Ruff reads standard input for '-', and expands '@name'
# as an argument file even after '--'. Paths containing whitespace cannot be
# expressed in this format.
IFS=$' \t\n' read -r -d '' -a TARGET_WORDS \
  < <(printf '%s\0' "${PARAM_TARGETS}")

for target in "${TARGET_WORDS[@]}"; do
  case "${target}" in
    -* | @*)
      TARGETS+=("./${target}")
      ;;
    *)
      TARGETS+=("${target}")
      ;;
  esac
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
  TARGETS=('.')
fi

printf 'Command:'
printf ' %q' ruff format "${RUFF_ARGS[@]}" -- "${TARGETS[@]}"
printf '\n'

STATUS=0

set +e
ruff format "${RUFF_ARGS[@]}" -- "${TARGETS[@]}"
STATUS=$?
set -e

# In 'check' and 'diff' mode Ruff exits 1 when a file would be reformatted and
# 2 on a configuration or command line error, so both keep failing the step.
# 'ruff format' has no '--exit-zero'.
exit "${STATUS}"
