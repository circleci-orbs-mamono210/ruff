# ruff/format parameters

Where each public parameter of `ruff/format` is tested. One row per
parameter: the default, the values the argument cases of
`format-parameters.py` set and what reaches Ruff for each, the checks of what
Ruff 0.16.2 then does, and the regression cases that cover the parameter.
`format-parameters.py` fails when a parameter of the packed command has no
row here, or a row has no parameter.

- **Arguments.** Every value in this column is an argument case of
  `format-parameters.py`, named `PARAMETER` or `PARAMETER=VALUE`. It runs the
  packed command with `record-ruff.sh` as Ruff and compares the arguments
  received. Nothing is listed for a value that passes nothing. Every
  parameter has a case with a value other than its default, and every value
  of an enum has a case of its own; the script checks both.
- **Ruff 0.16.2.** `ruff-*` names are Ruff cases of `format-parameters.py`.
  They run the packed command on files they write, with `record-real-ruff.sh`
  as Ruff, which records the arguments and runs the real Ruff. Each run
  requires an exact exit status, and the case checks the arguments received,
  standard output and standard error separately, and the files before and
  after. Steps of `.circleci/test-deploy.yml` are named by job and step.
- **Regression.** Cases of `regression.sh format`, which runs
  `src/scripts/format.sh` directly, and of the `line_length` step of
  `format-tests`. A name with `*` stands for the cases listed in full under
  "Regression cases" below.

The defaults pass `--check` for `mode: check` and `-- .` for the paths; the
arguments below come on top of those, unless a row says otherwise.

| Parameter | Default | Arguments | Ruff 0.16.2 | Regression |
| --------- | ------- | --------- | ----------- | ---------- |
| `cache_dir` | `''`, nothing | `build/ruff cache` → `--cache-dir` with that value as one argument | `ruff-cache`: the cache is written to the named directory and not to `.ruff_cache`. `format-tests`: `Verify cache_dir reached Ruff` | — |
| `color` | `auto`, nothing | `always` → `--color always`; `never` → `--color never` | `ruff-color`: ANSI colour codes with `always` only, in `check` and `diff` mode | — |
| `config_file` | `''`, nothing | `configs/ruff.toml` → `--config configs/ruff.toml`, before every override | `ruff-config-file`: a file with `line-length = 40` or `quote-style = "single"` changes the result, and it replaces the `ruff.toml` that Ruff would find. `ruff-configuration-errors`: a missing or invalid file, or a file together with `isolated`, exits 2 in every mode. `format-tests`: the `config_file` step | `ruff-exit-configuration-error` |
| `config_overrides` | `''`, nothing | two lines with a blank one between → one `--config` per line, in order; a blank value → nothing | `ruff-config-overrides`: changes the result and what `write` writes, wins over `config_file` and over the `ruff.toml` found, and of two overrides of one setting the first applies. `ruff-configuration-errors`: an invalid value exits 2. `format-tests`: the two `config_overrides` steps | `ruff-config-overrides`, `ruff-config-overrides-diff`, `ruff-config-invalid-*` |
| `excluded_paths` | `''`, nothing | `build/*,docs/conf.py` → `--exclude` with that value | `ruff-excluded-paths`: replaces the default exclusions, so `venv/` is formatted again. `format-tests`: the `excluded_paths` step | — |
| `exit_non_zero_on_format` | `false`, nothing | `true` with `mode: write` → `--exit-non-zero-on-format` | `ruff-exit-non-zero-on-format`: in `write` mode the file is rewritten and the step exits 1, and a formatted file exits 0; in `check` and `diff` mode the exit status stays the same. `format-tests`: `Verify exit_non_zero_on_format reports a rewrite` | — |
| `extend_excluded_paths` | `''`, nothing | `generated/*` → `--extend-exclude generated/*` | `ruff-excluded-paths`, `ruff-force-exclude`. `format-tests`: the `force_exclude` step | — |
| `extensions` | `''`, nothing | two lines → one `--extension` per mapping | `ruff-extensions`: a `.pya` file is found only with the mapping | `extensions-*`, `targets-and-extensions-together`, `ruff-extensions-several-lines` |
| `extra_args` | `''`, nothing | two lines → the items as written, after every other option; `--` and `@args` are refused before Ruff starts | `ruff-extra-args`: `--line-length 40` reaches Ruff after every other option, and `--` and `@args` exit 1 without starting Ruff. `ruff-configuration-errors`: `--line-length` together with `line_length` exits 2. `format-tests`: the `extra_args` step | `extra-args-*`, `refused-*` |
| `force_exclude` | `auto`, nothing | `auto` → nothing; `enabled` → `--force-exclude`; `disabled` → `--no-force-exclude` | `ruff-force-exclude`: `enabled` excludes a named file, and `disabled` overrides `force-exclude = true`. `format-tests`: the `force_exclude` step | — |
| `isolated` | `false`, nothing | `true` → `--isolated` | `ruff-isolated`: the `ruff.toml` found is ignored, while `config_overrides` and `line_length` still apply. `ruff-configuration-errors`: with `config_file`, exit 2. `format-tests`: the `isolated` step | — |
| `line_length` | `''`, nothing | `100` → `--line-length 100` | `ruff-line-length`: changes the result both ways, and wins over a `line-length` from `config_overrides`, in either order, and from the `ruff.toml` found. `format-tests`: `Verify line_length reaches the formatter through format.sh` and the `line_length` step | the five cases of the `line_length` step: `wide-default`, `narrow-default`, `wide-40`, `narrow-40`, `wide-40-diff` |
| `mode` | `check`, `--check` | `check` → `--check`; `diff` → `--diff`; `write` → nothing | `ruff-modes`: for each mode the arguments received, standard output, standard error, the exit status and the files. `format-tests`: `Verify check mode fails on an unformatted file`, `Verify write mode reformats the file`, `Verify diff mode fails without modifying the file` | `refused-check-*`, `refused-diff-*`, `refused-write-*`, `ruff-config-*-diff`, `ruff-mode-diff`, `ruff-mode-write` |
| `no_cache` | `false`, nothing | `true` → `--no-cache` | `ruff-cache`: no cache is written. `format-tests`: `Verify no_cache reached Ruff` | — |
| `output_format` | `default`, nothing | `default` → nothing; each of `concise`, `full`, `json`, `json-lines`, `junit`, `grouped`, `github`, `gitlab`, `pylint`, `rdjson`, `azure` and `sarif` → `--output-format` with it | `ruff-output-format-check`: in `check` mode every value gives its own report of the finding, with file, code, line and column, and `default` gives the `full` report. `ruff-output-format-other-modes`: `diff` mode prints the same diff whatever the value, and `write` mode prints no report, nothing at all with `json` and only the summary line with `concise` | — |
| `preview` | `auto`, nothing | `auto` → nothing; `enabled` → `--preview`; `disabled` → `--no-preview` | `ruff-preview`: a sole dictionary argument is hugged only with preview, and `disabled` overrides `preview = true`. `format-tests`: the `preview` step | — |
| `respect_gitignore` | `auto`, nothing | `auto` → nothing; `enabled` → `--respect-gitignore`; `disabled` → `--no-respect-gitignore` | `ruff-respect-gitignore`: in a Git repository, `disabled` formats an ignored file, and `enabled` overrides `respect-gitignore = false` | — |
| `target_version` | `default`, nothing | `default` → nothing; each of `py37` to `py315` → `--target-version` with it | `ruff-target-version`: `py37` and `py38` keep two context managers without parentheses, `py39` and later and the default, `py310`, put them in parentheses; `default` follows `requires-python`, and a value wins over it. `format-tests`: the `target_version` step | — |
| `targets` | `.`, `-- .` | `src tests` and `-x` on a second line → `-- src tests ./-x` | every Ruff case | `targets-*`, `extra-args-with-targets`, `ruff-name-*`, `ruff-names-on-several-lines`, `ruff-targets-*` |
| `verbosity` | `default`, nothing | `default` → nothing; `verbose` → `--verbose`; `quiet` → `--quiet`; `silent` → `--silent` | `ruff-verbosity`: `verbose` adds debug lines on standard error, `quiet` drops the summary line, and `silent` prints nothing and still exits 1, in `check` and `diff` mode | — |

## Modes and exit status

`ruff-modes` runs one file that is not formatted in each mode and records
what Ruff received. Ruff 0.16.2 shows the change in `check` mode as well, so
the modes are told apart by the form of the output, not by the code in it:

| Mode | Ruff receives | Exit | Standard output | Standard error | The file |
| ---- | ------------- | ---- | --------------- | -------------- | -------- |
| `check` | `--check` | 1 | a diagnostic per file, with the old and the new lines in the `full` report, then `1 file would be reformatted` | nothing | unchanged |
| `diff` | `--diff` | 1 | a unified diff: `--- a.py`, `+++ a.py`, `@@ -1,3 +1 @@` and the lines | `1 file would be reformatted` | unchanged |
| `write` | neither | 0 | `1 file reformatted` | nothing | rewritten |

A formatted file exits 0 in every mode. A setting Ruff cannot use exits 2 in
every mode, never 1, prints no report, and changes no file:
`ruff-configuration-errors` covers a missing and an invalid `config_file`, an
invalid value in `config_overrides`, `isolated` together with `config_file`,
and `line_length` together with `--line-length` in `extra_args`.
`exit_non_zero_on_format` only changes the exit status of `write` mode.

## Precedence of settings

What `ruff-config-file`, `ruff-config-overrides`, `ruff-isolated`,
`ruff-line-length`, `ruff-target-version`, `ruff-preview`,
`ruff-force-exclude` and `ruff-respect-gitignore` show with Ruff 0.16.2:

- `config_file` replaces the configuration Ruff would find.
- `config_overrides` and `line_length` win over every configuration file.
  Of two overrides of one setting, the first applies.
- `line_length` is passed as `--line-length`, which wins over a
  `line-length` from `config_overrides` in either order. `ruff/check` passes
  its `line_length` as an override after `config_overrides`, so there the
  override wins.
- `isolated` ignores every configuration file, while `config_overrides` and
  `line_length` still apply. Together with `config_file`, Ruff exits 2.
- `target_version`, `preview`, `force_exclude` and `respect_gitignore` leave
  the decision to the configuration at `default` or `auto`, and their other
  values win over it.

## Regression cases

The cases that `format-tests` runs with `bash tests/arguments/regression.sh
format`. The job keeps the log of the run, and `format-parameters.py
--regression-log` compares the cases it ran with this list, both ways, so a
case that is added, renamed or removed has to be listed here as well.

The run covers how `targets`, `extensions` and `extra_args` are split and
passed on, the `--` before the paths and the `./` in front of a path that
starts with `-` or `@`, files named `-`, `--help` and `@args`, the refused
`extra_args` items in every mode, a configuration that wants a change in
`ruff.toml`, `pyproject.toml` and `config_overrides` in `check` and `diff`
mode, an invalid setting, and the exit statuses.

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
extra-args-rewriting-names
refused-check-separator
refused-check-argument-file
refused-check-at-alone
refused-diff-separator
refused-diff-argument-file
refused-diff-at-alone
refused-write-separator
refused-write-argument-file
refused-write-at-alone
refused-at-as-a-value
refused-on-a-later-line
refused-several-at-once
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
ruff-config-invalid-check
ruff-config-invalid-diff
ruff-exit-clean
ruff-exit-findings
ruff-exit-configuration-error
ruff-mode-diff
ruff-mode-write
```

The `line_length` step of `format-tests`, `Verify line_length reaches the
formatter through format.sh`, runs the five cases named in the `line_length`
row. They are not compared with a log; see "Format line_length test" in
`tests/README.md`.
