# ruff/check parameters

Where each public parameter of `ruff/check` is tested. One row per
parameter: the default, the values the argument cases of
`check-parameters.py` set and what reaches Ruff for each, the checks of what
Ruff 0.16.2 then does, and the regression cases that cover the parameter.
`check-parameters.py` fails when a parameter of the packed command has no
row here, or a row has no parameter.

- **Arguments.** Every value in this column is an argument case of
  `check-parameters.py`, named `PARAMETER` or `PARAMETER=VALUE`. It runs the
  packed command with `record-ruff.sh` as Ruff and compares the arguments
  received. Nothing is listed for a value that passes nothing. Every
  parameter has a case with a value other than its default, and every value
  of an enum has a case of its own; the script checks both.
- **Ruff 0.16.2.** `ruff-*` names are Ruff cases of `check-parameters.py`,
  which run the packed command on files they write and require an exact exit
  status and the expected output and file contents. Steps of
  `.circleci/test-deploy.yml` are named by job and step. A step that only
  passes, such as the one with `color: always`, shows that Ruff accepts the
  arguments, not what they do.
- **Regression.** Cases of `../report/regression.sh` and `regression.sh`,
  which run `src/scripts/check.sh` directly. A name with `*` stands for the
  cases listed in full under "Regression cases" below.

The defaults pass `--no-fix --no-fix-only` for `fix: never` and `-- .` for
the paths; the arguments below come on top of those, unless a row says
otherwise.

| Parameter | Default | Arguments | Ruff 0.16.2 | Regression |
| --------- | ------- | --------- | ----------- | ---------- |
| `cache_dir` | `''`, nothing | `build/ruff cache` → `--cache-dir` with that value as one argument | `ruff-cache-dir`: the cache is written to the named directory and not to `.ruff_cache`. `parameter-tests`: `Verify cache_dir reached Ruff` | — |
| `color` | `auto`, nothing | `always` → `--color always`; `never` → `--color never` | `parameter-tests`: the step with `color: always` passes | — |
| `config_file` | `''`, nothing | `configs/ruff.toml` → `--config configs/ruff.toml`, before every override | `ruff-exit-statuses`: a missing file exits 2. `parameter-tests`: `Verify isolated and config_file cannot be combined`, `Verify exit_zero does not mask configuration errors` | `config-error-*`, `exit-zero-config-error`, `rerun-config-error`, `ruff-exit-configuration-error`, `ruff-exit-zero-configuration-error` |
| `config_overrides` | `''`, nothing | two lines with a blank one between → one `--config` per line, in order; a blank value → nothing | `parameter-tests`: the `config_overrides` step and `Verify isolated accepts config overrides` | `ruff-config-overrides`, `ruff-config-overrides-diff` |
| `diff` | `false`, nothing | `true` → `--diff` | `ruff-diff`: the diff is printed, exit 1, the files are unchanged; nothing to fix exits 0; with `output_file` the file gets only Ruff's summary. `parameter-tests`: the `diff` step, then the fixture check | `ruff-config-*-diff` |
| `excluded_paths` | `''`, nothing | `build/*,docs/conf.py` → `--exclude` with that value | `ruff-excluded-paths`: replaces the default exclusions, so `venv/` is checked again. `parameter-tests`: the `excluded_paths` step | — |
| `exit_non_zero_on_fix` | `false`, nothing | `true` → `--exit-non-zero-on-fix` | `parameter-tests`: `Verify fix safe rewrites and exit_non_zero_on_fix reports it` | — |
| `exit_zero` | `false`, nothing | `true` → `--exit-zero` | `parameter-tests`: the steps with `exit_zero: true`, `Verify exit_zero does not mask configuration errors` | `exit-zero-violations`, `exit-zero-config-error`, `ruff-exit-zero-findings`, `ruff-exit-zero-configuration-error` |
| `extend_excluded_paths` | `''`, nothing | `generated/*` → `--extend-exclude generated/*` | `ruff-excluded-paths`, `ruff-force-exclude`. `parameter-tests`: the `extend_excluded_paths` step | — |
| `extend_per_file_ignores` | `''`, nothing | `tests/*:S101,__init__.py:F401` → `--extend-per-file-ignores` with that value | `parameter-tests`: the `extend_per_file_ignores` step | — |
| `extend_selected_rules` | `''`, nothing | `E501,D` → `--extend-select E501,D` | `parameter-tests`: the `line_length` steps | — |
| `extensions` | `''`, nothing | two lines → one `--extension` per mapping | `ruff-extensions`: a `.pya` file is checked only with the mapping | `extensions-*`, `targets-and-extensions-together`, `ruff-extensions-several-lines` |
| `extra_args` | `''`, nothing | two lines → the items as written, after every other option | `parameter-tests`: the three `extra_args` steps | `extra-args-*`, `fix-*-extra-args-rewriting`, `refused-*`, `ruff-show-settings` |
| `fix` | `never`, `--no-fix --no-fix-only` | `never` → the default's arguments; `auto` → nothing; `safe` → `--fix --no-unsafe-fixes`; `unsafe` → `--fix --unsafe-fixes` | `ruff-fixable-and-unfixable`, `ruff-fix-safety`: `safe` leaves an unsafe fix that `unsafe` applies; `ruff-exit-statuses`. `parameter-tests`: `Verify fix never rewrites the checkout`, `Verify fix safe rewrites and exit_non_zero_on_fix reports it`. `command-tests`: `Verify the default check against the shared defaults` | `fix-auto`, `fix-safe`, `fix-unsafe`, `ruff-config-ruff-toml`, `ruff-config-pyproject`, `ruff-config-overrides`, `refused-never-*` |
| `fix_only` | `false`, nothing | `true` with `fix: safe` → `--fix-only` on top of `safe`; with `fix: never` → refused before Ruff starts (`fix_only=true-with-fix=never`) | `ruff-exit-statuses`: refused, exit 1, Ruff not started. `parameter-tests`: `Verify fix_only cannot be combined with fix never` | `refused-fix-only-parameter` |
| `fixable` | `''`, nothing | `F401,I001` → `--fixable F401,I001` | `ruff-fixable-and-unfixable`: only `F401` is fixed | — |
| `force_exclude` | `auto`, nothing | `auto` → nothing; `enabled` → `--force-exclude`; `disabled` → `--no-force-exclude` | `ruff-force-exclude`: `enabled` excludes a named file, `disabled` overrides `force-exclude = true`. `parameter-tests`: the `force_exclude` step | — |
| `ignore_noqa` | `false`, nothing | `true` → `--ignore-noqa` | `ruff-ignore-noqa`: a suppressed `F401` is reported | — |
| `ignored_rules` | `''`, nothing | `E203,D203` → `--ignore E203,D203` | `parameter-tests`: the `ignored_rules` step | — |
| `isolated` | `false`, nothing | `true` → `--isolated` | `parameter-tests`: `Verify isolated and config_file cannot be combined`, `Verify isolated accepts config overrides`, the `isolated` step | — |
| `line_length` | `''`, nothing | `100` → `--config 'line-length = 100'`, after every `config_overrides` line | `parameter-tests`: the `line_length` steps | — |
| `no_cache` | `false`, nothing | `true` → `--no-cache` | `parameter-tests`: the step with `no_cache: true` passes | — |
| `output_file` | `''`, nothing | `reports/ruff.txt` → `--output-file reports/ruff.txt`; the file is emptied first | `ruff-output-format-json`, `ruff-diff`. `parameter-tests`: every report and `Verify the reports to be stored` | every case of `../report/regression.sh` |
| `output_format` | `default`, nothing | `default` → nothing; each of `concise`, `full`, `json`, `json-lines`, `junit`, `grouped`, `github`, `gitlab`, `pylint`, `rdjson`, `azure` and `sarif` → `--output-format` with it | `ruff-output-format-json`: the report parses and holds each finding's file, code, position and fix. `parameter-tests`: `Verify output_format json reached Ruff`. `command-tests`: the default is `full` | — |
| `per_file_ignores` | `''`, nothing | `tests/*:S101` → `--per-file-ignores tests/*:S101` | `parameter-tests`: the `per_file_ignores` step | — |
| `preview` | `auto`, nothing | `auto` → nothing; `enabled` → `--preview`; `disabled` → `--no-preview` | `ruff-preview`: `E225` is reported only with preview, and `disabled` overrides `preview = true` | — |
| `respect_gitignore` | `auto`, nothing | `auto` → nothing; `enabled` → `--respect-gitignore`; `disabled` → `--no-respect-gitignore` | `ruff-respect-gitignore`: in a Git repository, `disabled` checks an ignored file, and `enabled` overrides `respect-gitignore = false` | — |
| `selected_rules` | `''`, nothing | `E4,E7,E9,F` → `--select E4,E7,E9,F` | `ruff-fix-safety`, `ruff-preview`. `parameter-tests`: `Verify selected_rules limited the report`, `Verify the legacy default set excludes isort` | — |
| `show_fixes` | `auto`, nothing | `auto` → nothing; `enabled` → `--show-fixes`; `disabled` → `--no-show-fixes` | `ruff-show-fixes`: `enabled` lists the fixes, and `disabled` overrides `show-fixes = true` | — |
| `statistics` | `false`, nothing | `true` → `--statistics` | `parameter-tests`: the step with `statistics: true` passes | — |
| `target_version` | `default`, nothing | `default` → nothing; each of `py37` to `py315` → `--target-version` with it | `parameter-tests`: the step with `target_version: py311` passes | — |
| `targets` | `.`, `-- .` | `src tests` and `-x` on a second line → `-- src tests ./-x` | every Ruff case | `targets-*`, `extra-args-with-targets`, `ruff-name-*`, `ruff-names-on-several-lines`, `ruff-targets-*` |
| `tee` | `true`, nothing | no argument either way. With `output_file`: `true` prints the report back, `false` does not | — | `success-*`, `violations-*`, `config-error-*`, `no-read-without-tee` |
| `unfixable` | `''`, nothing | `F401` → `--unfixable F401` | `ruff-fixable-and-unfixable`: everything but `F401` is fixed | — |
| `verbosity` | `default`, nothing | `default` → nothing; `verbose` → `--verbose`; `quiet` → `--quiet`; `silent` → `--silent` | `parameter-tests`: the step with `verbosity: verbose` passes | `rerun-empty-success` (`quiet`), `rerun-empty-failure` (`silent`) |

Two argument cases set several parameters at once. `values-not-evaluated`
passes `$(echo F) E`, `` `id` `` and `*` through `selected_rules`,
`ignored_rules` and `fixable`, and each must arrive as written, as one
argument. `config-order-and-extra-args` pins the order that matters:
`config_file`, the `config_overrides` lines and `line_length` in this order,
because Ruff 0.16.2 applies the first of several overrides of one setting, as
`ruff check --show-settings` shows, and `extra_args` after every option the
command builds.

`ruff-exit-statuses` separates the outcomes: a clean file exits 0, a
violation 1, a missing `config_file` 2, a refused input 1 without starting
Ruff, and an allowed fix 0 with the file rewritten. Files that a case does
not fix are compared before and after.

## Regression cases

The cases that `parameter-tests` runs for `check`. The job keeps the log of
each script, and `check-parameters.py --regression-log` compares the cases
it ran with these lists, both ways, so a case that is added, renamed or
removed has to be listed here as well.

`../report/regression.sh` covers the report of an earlier run: `output_file`,
`tee`, `exit_zero`, a missing `config_file`, `verbosity`, and failures to
prepare or read the report.

```text tests/report/regression.sh
success-tee
success-no-tee
violations-tee
violations-no-tee
config-error-tee
config-error-no-tee
exit-zero-violations
exit-zero-config-error
rerun-first
rerun-same-result
rerun-clean-first
rerun-clean
rerun-empty-success-first
rerun-empty-success
rerun-empty-failure-first
rerun-empty-failure
rerun-config-error-first
rerun-config-error
prepare-parent-is-a-file
prepare-path-is-a-directory
prepare-read-only-report
read-fails-after-ruff-exits-0
read-fails-after-ruff-exits-1
read-fails-after-ruff-exits-2
read-fails-after-report-removed
no-read-without-tee
```

`regression.sh check` covers how `targets`, `extensions` and `extra_args` are
split and passed on, the `--` before the paths and the `./` in front of a
path that starts with `-` or `@`, files named `-`, `--help` and `@args`, what
`fix` passes, the refused `extra_args` items and `fix_only`, `fix: never`
against `fix-only = true` in `ruff.toml`, `pyproject.toml` and
`config_overrides`, alone and with `diff`, and the exit statuses.

```text tests/arguments/regression.sh
targets-one-line
targets-two-lines
targets-empty-lines-and-indentation
targets-tabs
targets-empty
targets-blank
targets-glob-characters
targets-quotes
targets-shell-syntax
targets-backslashes
targets-dash-and-at
targets-dash-and-at-on-several-lines
extensions-one-line
extensions-several-lines
extensions-empty-lines-and-tabs
extensions-empty
extensions-blank
extensions-glob-characters
targets-and-extensions-together
extra-args-none
extra-args-blank
extra-args-one-line
extra-args-several-lines
extra-args-not-evaluated
extra-args-passed-through
extra-args-near-the-refused-names
extra-args-with-targets
fix-auto
fix-safe
fix-unsafe
fix-auto-extra-args-rewriting
fix-safe-extra-args-rewriting
fix-unsafe-extra-args-rewriting
refused-never-separator
refused-never-argument-file
refused-never-at-alone
refused-auto-separator
refused-auto-argument-file
refused-auto-at-alone
refused-safe-separator
refused-safe-argument-file
refused-safe-at-alone
refused-unsafe-separator
refused-unsafe-argument-file
refused-unsafe-at-alone
refused-at-as-a-value
refused-on-a-later-line
refused-several-at-once
refused-never-1--fix
refused-never-2--fix-equals-true
refused-never-3--fix-equals-false
refused-never-4--fix-equals-
refused-never-5--fix-only
refused-never-6--fix-only-equals-true
refused-never-7--fix-only-equals-false
refused-never-8--add-noqa
refused-never-9--add-noqa-equals-why
refused-never-10--add-ignore
refused-never-11--add-ignore-equals-why
refused-never-on-a-later-line
refused-never-after-no-fix
refused-never-all-at-once
refused-fix-only-parameter
refused-never-with-the-real-ruff
ruff-name-standard-input
ruff-name-option
ruff-name-argument-file
ruff-names-on-several-lines
ruff-extensions-several-lines
ruff-targets-dot
ruff-targets-empty
ruff-targets-blank
ruff-config-ruff-toml
ruff-config-ruff-toml-diff
ruff-config-pyproject
ruff-config-pyproject-diff
ruff-config-overrides
ruff-config-overrides-diff
ruff-show-settings
ruff-exit-clean
ruff-exit-findings
ruff-exit-configuration-error
ruff-exit-zero-findings
ruff-exit-zero-configuration-error
```
