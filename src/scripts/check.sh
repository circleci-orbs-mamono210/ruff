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
# a refused run leaves the checkout and an existing report as they were.
# tests/arguments/packed-commands.py checks this order in the packed command.
# ---------------------------------------------------------------------------

# 'fix_only' asks Ruff to rewrite files and 'fix: never' forbids it. Refuse
# the combination instead of letting a job modify files it was told not to.
if is_true "${PARAM_FIX_ONLY}" && [ "${PARAM_FIX}" = 'never' ]; then
  echo \
    "'fix_only' rewrites files, so it needs 'fix' set to 'auto', 'safe' or 'unsafe'." \
    >&2
  exit 1
fi

# Split extra_args on spaces, tabs and newlines, like targets and extensions
# below, so every line counts and empty lines vanish. Nothing is evaluated:
# quotes, '$', '~' and glob characters stay literal, and an argument that
# contains whitespace cannot be expressed.
IFS=$' \t\n' read -r -d '' -a EXTRA_ARGS \
  < <(printf '%s\0' "${PARAM_EXTRA_ARGS}")

# extra_args is passed through as it is, with two exceptions. Both are decided
# on the split items alone, by exact name or by the name followed by '=', so
# '--fixable' is not mistaken for '--fix'. Short options, combined short
# options and the values of other options are not interpreted.
#
# - '--' and '@name' would change how the rest of the command line is read.
#   The script puts '--' before the paths itself, and Ruff expands '@name' as
#   an argument file wherever it appears.
# - Under 'fix: never' the four options below would rewrite the checked files.
#   'NAME=VALUE' is refused whatever the value is.
for argument in "${EXTRA_ARGS[@]}"; do
  case "${argument}" in
    --)
      REJECTED+=("'--': the paths come from 'targets', and '--' is added for them")
      ;;
    @*)
      REJECTED+=("'${argument}': Ruff would read an item that starts with '@' as an argument file")
      ;;
    --fix | --fix=* | --fix-only | --fix-only=* | \
      --add-noqa | --add-noqa=* | --add-ignore | --add-ignore=*)
      if [ "${PARAM_FIX}" = 'never' ]; then
        REJECTED+=("'${argument}': it rewrites files, which 'fix: never' forbids")
      fi
      ;;
    *)
      ;;
  esac
done

if [ "${#REJECTED[@]}" -ne 0 ]; then
  {
    echo "'extra_args' contains items that are not accepted, so Ruff was not run:"
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

case "${PARAM_FIX}" in
  never)
    # '--no-fix' alone is not enough: 'fix-only = true' in a configuration
    # file or in a '--config' override implies fixing and wins over it.
    RUFF_ARGS+=('--no-fix' '--no-fix-only')
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

# The file itself is prepared just before Ruff runs, once every input check
# has passed. See the comment above that step.
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

# extra_args was split and checked at the top of the script.
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
printf ' %q' ruff check "${RUFF_ARGS[@]}" -- "${TARGETS[@]}"
printf '\n'

# Ruff only rewrites the output file once it gets as far as reporting. A
# configuration or command line error exits 2 and leaves the file untouched,
# so a report from an earlier run would otherwise be shown and stored as this
# run's result. Emptying the file first means that whatever it holds afterwards
# was written by this run. When that is impossible the step stops with 2, the
# status Ruff itself uses when it cannot create the output file, and Ruff is
# not run.
if [ -n "${PARAM_OUTPUT_FILE}" ]; then
  if ! mkdir -p -- "$(dirname -- "${PARAM_OUTPUT_FILE}")" ||
    ! printf '' > "${PARAM_OUTPUT_FILE}"; then
    echo \
      "Could not prepare the report file '${PARAM_OUTPUT_FILE}', so Ruff was not run." \
      >&2
    exit 2
  fi
fi

STATUS=0

set +e
ruff check "${RUFF_ARGS[@]}" -- "${TARGETS[@]}"
STATUS=$?
set -e

# Ruff writes to '--output-file' INSTEAD of standard output and has no '--tee'
# of its own, so the report is echoed back here to keep it in the job log.
# Only a non-empty report is printed. The file was emptied above, so an empty
# file means this run wrote nothing to it, for example after a configuration
# error or under 'verbosity: quiet'.
REPORT_STATUS=0

if [ -n "${PARAM_OUTPUT_FILE}" ] && is_true "${PARAM_TEE}"; then
  if [ ! -f "${PARAM_OUTPUT_FILE}" ] || [ ! -r "${PARAM_OUTPUT_FILE}" ]; then
    REPORT_STATUS=1
  elif [ -s "${PARAM_OUTPUT_FILE}" ]; then
    echo "Report written to ${PARAM_OUTPUT_FILE}:"
    cat -- "${PARAM_OUTPUT_FILE}" || REPORT_STATUS=1
  else
    echo "Report ${PARAM_OUTPUT_FILE} is empty."
  fi

  if [ "${REPORT_STATUS}" -ne 0 ]; then
    echo "Could not read the report file '${PARAM_OUTPUT_FILE}'." >&2
  fi
fi

# Ruff's own non-zero status is always returned unchanged, so printing the
# report can never turn a failure into a success. A run that Ruff passed still
# fails with 2 when the report it was asked to print could not be read.
if [ "${STATUS}" -eq 0 ] && [ "${REPORT_STATUS}" -ne 0 ]; then
  exit 2
fi

# 'exit_zero' applies to reported violations only. Ruff exits 2 for a missing
# config file or a command line error, and that status is preserved here.
# A path that does not exist is reported as a violation, so it exits 1 and IS
# masked by 'exit_zero'.
exit "${STATUS}"
