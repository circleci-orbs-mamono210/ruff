# shellcheck shell=bash
# The environment that the published 'check' command gives
# src/scripts/check.sh when every parameter is left at its default: one
# PARAM_* variable for each of its 35 parameters.
#
# Source the file, then set only what a test is about:
#
#   source tests/defaults/check.sh
#   PARAM_TARGETS='tests/clean' bash src/scripts/check.sh
#
# tests/defaults/compare.py compares this file with the orb that
# orb-tools/pack builds, in the packed-command-tests job. A parameter that is
# added, removed or renamed, or a default that changes, on one side only
# makes that job fail. Keep every line in the form
# export PARAM_<NAME>='<value>', without a quote inside the value, so the
# script and Bash read the same values.
export PARAM_CACHE_DIR=''
export PARAM_COLOR='auto'
export PARAM_CONFIG_FILE=''
export PARAM_CONFIG_OVERRIDES=''
export PARAM_DIFF='false'
export PARAM_EXCLUDED_PATHS=''
export PARAM_EXIT_NON_ZERO_ON_FIX='false'
export PARAM_EXIT_ZERO='false'
export PARAM_EXTEND_EXCLUDED_PATHS=''
export PARAM_EXTEND_PER_FILE_IGNORES=''
export PARAM_EXTEND_SELECTED_RULES=''
export PARAM_EXTENSIONS=''
export PARAM_EXTRA_ARGS=''
export PARAM_FIX='never'
export PARAM_FIXABLE=''
export PARAM_FIX_ONLY='false'
export PARAM_FORCE_EXCLUDE='auto'
export PARAM_IGNORED_RULES=''
export PARAM_IGNORE_NOQA='false'
export PARAM_ISOLATED='false'
export PARAM_LINE_LENGTH=''
export PARAM_NO_CACHE='false'
export PARAM_OUTPUT_FILE=''
export PARAM_OUTPUT_FORMAT='default'
export PARAM_PER_FILE_IGNORES=''
export PARAM_PREVIEW='auto'
export PARAM_RESPECT_GITIGNORE='auto'
export PARAM_SELECTED_RULES=''
export PARAM_SHOW_FIXES='auto'
export PARAM_STATISTICS='false'
export PARAM_TARGETS='.'
export PARAM_TARGET_VERSION='default'
export PARAM_TEE='true'
export PARAM_UNFIXABLE=''
export PARAM_VERBOSITY='default'
