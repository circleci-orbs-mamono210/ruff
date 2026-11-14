# Ruff Orb

[![CircleCI Build Status](https://circleci.com/gh/circleci-orbs-mamono210/ruff.svg?style=shield)](https://circleci.com/gh/circleci-orbs-mamono210/ruff) [![CircleCI Orb Version](https://badges.circleci.com/orbs/orbss/ruff.svg)](https://circleci.com/orbs/registry/orb/orbss/ruff) [![GitHub License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](https://github.com/circleci-orbs-mamono210/ruff/blob/main/LICENSE)

A CircleCI Orb for running [Ruff](https://docs.astral.sh/ruff/), the Python linter and formatter.

This Orb provides:

* A command for installing Ruff with `python -m pip`
* A command for running `ruff check`, the linter
* A command for running `ruff format`, the formatter
* A configurable Python executor
* Rule selection and ignore lists, including per-file ignores
* Exclusion patterns, gitignore handling and target version selection
* Inline TOML configuration overrides
* Report capture to a file for storage as a build artifact
* Support for `pyproject.toml`, `ruff.toml` and `.ruff.toml`

## Orb Registry

The published Orb, parameter reference and generated examples are available in the CircleCI Orb Registry:

https://circleci.com/developer/orbs/orb/orbss/ruff

## Quick Start

The default executor uses a CircleCI Python convenience image. Ruff is not preinstalled, so run `ruff/install` before `ruff/check`.

```yaml
version: 2.1

orbs:
  ruff: orbss/ruff@0.0.1

jobs:
  execute-ruff:
    executor: ruff/default
    steps:
      - checkout
      - ruff/install:
          version: "0.16.2"
      - ruff/check

workflows:
  ruff:
    jobs:
      - execute-ruff
```

By default, `ruff/check` checks the current working directory recursively and the job fails when any violation is reported.

Both `ruff/check` and `ruff/format` first check their input, then print the installed Ruff version using `ruff --version`, and then run Ruff, all in one step. A step whose input is refused does not start Ruff at all; see [Extra Arguments](#extra-arguments).

## Pin the Version

Ruff is pre-1.0 and its releases are not backward compatible in the way a stable tool's are. Version 0.16.0 raised the default rule set **from 59 rules to 413**, which turned many green pipelines red without any change to the repository under test.

Pinning is therefore not a recommendation here so much as a requirement for a reproducible pipeline:

```yaml
- ruff/install:
    version: "0.16.2"
```

If a repository was configured against the older defaults, restoring them is a one-line change:

```yaml
- ruff/check:
    selected_rules: E4,E7,E9,F
```

## Coming from flake8 and isort

Ruff replaces flake8, isort and Black with a single binary, so an Orb that mirrors the flake8 Orb one-to-one would misrepresent the tool. The differences worth planning around:

| Topic | flake8 | Ruff |
| ----- | ------ | ---- |
| Plugins | Separate pip packages | None; every rule is built in and selected with `selected_rules` |
| Default rules | pycodestyle, pyflakes, mccabe | 413 rules across 34 categories since 0.16.0 |
| Line length | `E501` on by default | `E501` is **not** in the default set; add it with `extend_selected_rules` |
| Import sorting | `isort` as a separate tool | `I` rules, in the default set since 0.16.0 |
| Formatting | Black as a separate tool | `ruff/format` |
| Per-file ignores | Whitespace-separated pairs | Comma-separated pairs, one rule code each |
| Config file | `setup.cfg`, `tox.ini`, `.flake8` | `pyproject.toml`, `ruff.toml`, `.ruff.toml` |
| Ignored files | Its own exclusion list | Also honours `.gitignore` by default |

A staged migration usually gates on a narrow set first and reports on the full one:

```yaml
- ruff/check:
    extend_selected_rules: E501,I
    line_length: "100"
    selected_rules: E4,E7,E9,F
    targets: src

- ruff/check:
    exit_zero: true
    output_file: reports/ruff-full.txt
    statistics: true
    targets: src

- store_artifacts:
    path: reports
```

The second step never fails the job. It exists to show how much work adopting the full rule set would be.

## Linting

`ruff/check` runs the linter.

```yaml
- ruff/check:
    extend_selected_rules: E501,D
    ignored_rules: D203,D213
    line_length: "100"
    targets: src tests
```

`selected_rules` **replaces** the selection, so prefer `extend_selected_rules` when the intent is to add rules. `ignored_rules` is applied after the selection and removes rules that either of them turned on.

`line_length` is passed as a `--config "line-length = N"` override rather than as a command-line flag, because `ruff check --line-length` is absent from Ruff's help output and is not part of its documented interface. Note that the limit is only *reported* when `E501` is selected; on its own it affects how other rules and the formatter wrap code.

### Per-file ignores

```yaml
- ruff/check:
    extend_per_file_ignores: "__init__.py:F401,tests/*:S101"
```

Two differences from flake8 catch people out. Ruff separates the pairs with commas rather than whitespace, and each pair carries exactly **one** rule code on the command line, so covering several rules under one pattern means repeating the pattern:

```yaml
- ruff/check:
    extend_per_file_ignores: "tests/*:S101,tests/*:F401"
```

The list form used in a config file, `"tests/*" = ["S101", "F401"]`, is not accepted on the command line.

## Formatting

`ruff/format` runs the formatter. The default mode is `check`, which passes `--check`: Ruff reports the files that would be reformatted and fails the step instead of rewriting them, which is what a CI gate wants.

```yaml
- ruff/format:
    color: always
    mode: diff
    targets: src tests
```

| Mode | Behaviour |
| ---- | --------- |
| `check` | Reports which files would be reformatted; fails the step if there are any |
| `diff` | Also prints the exact changes, which makes a failure actionable from the log |
| `write` | **Rewrites the files in place**; only useful when the job goes on to commit the result |

> Since Ruff 0.16.0 the formatter also reformats Python code blocks inside Markdown files, so `targets: .` reaches every `.md` file in the repository. Add `*.md` to `extend_excluded_paths` when that is not wanted.

Neither `check` nor `diff` rewrites the files it is given. This is verified with Ruff 0.16.2 for runs set up through the Orb's own parameters, including settings that come from a configuration file or from `config_overrides`. It does not cover `extra_args` or other Ruff versions, and Ruff's cache is still written.

`line_length` is a first-class formatter flag here. Keep it in step with the `line_length` given to `ruff/check`, because the two commands configure it independently.

## Configuration Files

Ruff reads `pyproject.toml`, `ruff.toml` or `.ruff.toml` automatically.

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
extend-select = ["E501", "D"]
ignore = ["D203", "D213"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
```

The Orb only passes a flag when the parameter differs from Ruff's own default, so settings in the configuration file are preserved unless the Orb parameter explicitly overrides them.

Use `config_file` to point at a different file:

```yaml
- ruff/check:
    config_file: build/ruff.toml
```

Use `config_overrides` for individual settings. Each line becomes its own `--config` argument, and these take precedence over every configuration file:

```yaml
- ruff/check:
    config_overrides: |
      lint.dummy-variable-rgx = "^_$"
      lint.extend-select = ["E501"]
```

The parameter is split on **newlines** rather than on whitespace, because a TOML pair contains whitespace of its own.

`isolated: true` ignores every configuration file. Unlike flake8, Ruff rejects that in combination with a `config_file` path itself, so the Orb does not need to guard against it.

Ruff draws the line at files, not at settings, so `config_overrides` and `line_length` are still applied under `isolated`:

```yaml
- ruff/check:
    config_overrides: |
      lint.extend-select = ["E501"]
    isolated: true
    line_length: "100"
```

## Choosing the Files

`targets` names the files and directories that `ruff/check` and `ruff/format` work on. Separate the items with spaces, tabs or newlines, so a YAML block with one path per line works:

```yaml
- ruff/check:
    targets: |
      src
      tests
      tools/release.py
```

Both commands read `targets` the same way:

* Empty lines are ignored. An empty or blank value means `.`, the working directory, which is also the default.
* Every item is a path. The paths are passed after `--`, and a relative path that starts with `-` or `@` is passed as `./<path>`. A file named `-`, `--help` or `@args` is therefore checked or formatted as that file; it never makes Ruff read standard input, run an option or expand an argument file. Absolute paths and other relative paths are passed unchanged.
* Nothing is evaluated. Quotes, backslashes, `$`, `~` and glob characters reach Ruff as they are, so `"my file.py"` is the two paths `"my` and `file.py"`. Ruff does not expand glob characters either, so name a directory rather than a pattern such as `src/*.py`.
* A path that contains whitespace cannot be given. Name a directory that contains it instead.
* Options do not belong in `targets`. Pass them through `extra_args`.

`extensions` is split the same way, and each `extension:language` mapping is passed as its own `--extension`:

```yaml
- ruff/check:
    extensions: |
      pyw:python
      ipy:ipynb
```

Version 0.0.1 read `targets` and `extensions` only up to the first newline, so every later line was silently ignored. It also passed the paths without `--`, so an item that started with `-` reached Ruff as an option, `-` read standard input and `@name` was expanded as an argument file. An option written into `targets` is now looked up as a file instead and is not applied: `ruff/check` reports it as a missing file (`E902`, exit 1, which `exit_zero` masks) and `ruff/format` exits 2. Move such options to `extra_args`.

## Excluding Paths

`extend_excluded_paths` adds to Ruff's built-in exclusions, which already cover `.git`, `__pycache__`, `.venv`, `node_modules` and similar directories.

```yaml
- ruff/check:
    extend_excluded_paths: migrations,vendor
```

`excluded_paths` replaces the built-in list entirely, so use it only when that is intended.

Ruff also honours `.gitignore` and other standard ignore files by default, which flake8 does not. Set `respect_gitignore: disabled` when generated code is both ignored by Git and expected to be linted.

`force_exclude: enabled` makes the exclusions apply to paths named directly in `targets` as well; Ruff otherwise checks an explicitly named file even when it is excluded.

## Fixing

`ruff/check` defaults to `fix: never`, which passes both `--no-fix` and `--no-fix-only`. With the two flags the linter applies no fixes **even when the configuration sets `fix = true` or `fix-only = true`**, whether in `ruff.toml`, in `pyproject.toml` or through `config_overrides`. `--no-fix` alone is not enough, because `fix-only = true` implies fixing and wins over it. This is the behaviour a CI gate wants.

What that statement covers:

* It is verified with Ruff 0.16.2, for runs set up through the Orb's own parameters.
* `extra_args` can ask Ruff for almost anything. Under `fix: never` the Orb refuses the items listed in [Extra Arguments](#extra-arguments); other extra arguments are passed on as written and are not covered.
* Other Ruff versions are not covered.
* It is about fixes to the checked files. The report in `output_file` and Ruff's cache are still written.

| Value | Behaviour |
| ----- | --------- |
| `never` | Passes `--no-fix --no-fix-only`; the linter applies no fixes, within the scope described above |
| `auto` | Passes nothing; the configuration file decides |
| `safe` | Passes `--fix --no-unsafe-fixes` |
| `unsafe` | Passes `--fix --unsafe-fixes`; may not preserve the original intent of the code |

To see what fixing *would* change, use `diff`. Ruff then prints the fixes instead of applying them, also under `fix: never`:

```yaml
- ruff/check:
    diff: true
```

`fix_only: true` asks Ruff to rewrite files, which `fix: never` forbids. The Orb refuses that combination before Ruff is started rather than modifying files a job was told to leave alone; set `fix` explicitly when a fixing run is intended.

## Extra Arguments

`extra_args` appends options that the Orb does not expose as parameters. Separate the items with spaces, tabs or newlines; empty lines are ignored:

```yaml
- ruff/check:
    extra_args: |
      --extend-fixable F401
      --no-show-fixes
```

For example, `--show-settings` makes Ruff print the settings it resolved instead of checking:

```yaml
- ruff/check:
    extra_args: --show-settings
    targets: src/app.py
```

Nothing is evaluated: quotes, backslashes, `$`, `~` and glob characters reach Ruff as they are, so an argument that contains whitespace cannot be given.

The items are passed to Ruff as written, with these exceptions:

| Command | Refused item | Reason |
| ------- | ------------ | ------ |
| `ruff/check` and `ruff/format`, always | `--` | The Orb puts `--` before the paths from `targets` itself |
| `ruff/check` and `ruff/format`, always | Any item that starts with `@` | Ruff expands it as an argument file |
| `ruff/check` with `fix: never` | `--fix`, `--fix-only`, `--add-noqa`, `--add-ignore`, and each of them followed by `=` and a value | They rewrite the checked files |

When an item is refused, the step exits 1 and names the item. This happens before Ruff is started, even for `ruff --version`, and before `output_file` is prepared, so no file is touched.

The rule looks at each item on its own, by its exact text:

* `--fixable` is not `--fix`, and `--fix=false` is refused like `--fix=true`.
* Combined short options such as `-ne`, and `NAME=VALUE` forms such as `--output-file=x`, are not taken apart or interpreted.
* An item that starts with `@` is refused even where Ruff would read it as the value of another option.

Being accepted is not a guarantee. An extra argument can still override a parameter, skip checks, change the exit status or send output elsewhere; Ruff decides how the arguments combine, and the Orb does not try to rule that out.

Version 0.0.1 read `extra_args` only up to the first newline and passed every item on. Under `fix: never` it also passed `--no-fix` alone, so `fix-only = true` in a configuration, or `--fix` in `extra_args`, made the linter rewrite files.

## Saving the Report as an Artifact

Use `output_file` to write the report to a file. Before Ruff starts, the Orb creates the parent directory and empties the file, so the file only ever holds what the current run wrote. Ruff never writes colour into it, so the artifact needs no extra settings.

```yaml
version: 2.1

orbs:
  ruff: orbss/ruff@0.0.1

jobs:
  execute-ruff:
    executor: ruff/default
    steps:
      - checkout
      - ruff/install:
          version: "0.16.2"

      - ruff/check:
          exit_zero: true
          output_file: reports/ruff.json
          output_format: json
          tee: false

      - store_artifacts:
          path: reports

      - ruff/check:
          color: always

workflows:
  ruff:
    jobs:
      - execute-ruff
```

`exit_zero: true` prevents the reporting step from stopping the job when violations are found, so the artifact is stored. The second run is the one that decides whether the job passes.

Ruff writes to the file **instead of** standard output and has no `--tee` of its own, so the Orb prints the file back to the job log afterwards. The `tee` parameter, which defaults to `true`, controls that. Because Ruff never writes colour into the file, the log copy is always uncoloured; use `color: always` on the gating run instead, where CircleCI renders ANSI escape sequences even though the log is not a TTY.

`output_format: github` emits workflow annotations, and `junit` or `sarif` suit report ingestion.

### Report handling and exit status

Ruff leaves `output_file` untouched when it stops on a configuration or command-line error and exits 2. Because the Orb has already emptied the file, such a run leaves an empty file, so neither the log nor the artifact shows an earlier run's report.

| Situation | `output_file` afterwards | Log with `tee: true` | Exit status |
| --------- | ------------------------ | -------------------- | ----------- |
| Ruff wrote a report | The report of this run | `Report written to <path>:` followed by the report | Ruff's |
| Ruff wrote nothing, for example after a configuration error, or with `verbosity: quiet` when nothing is reported | Empty | `Report <path> is empty.` | Ruff's |
| The Orb cannot create the parent directory or empty the file | Left as it was; Ruff is not run | An error message | 2 |
| Ruff exited 0 but the report cannot be read back | Whatever is at the path | An error message | 2 |
| Ruff exited non-zero and the report cannot be read back | Whatever is at the path | An error message | Ruff's |

With `tee: false` the Orb neither prints nor reads the report, so the last two rows do not apply.

The Orb never changes a non-zero status from Ruff, so printing the report cannot hide a failure. The status 2 for a file that cannot be prepared matches what Ruff itself returns when it cannot create the output file. In that case the Orb does not delete the file, so a later step that stores the path regardless of the failure, for example with `when: always`, stores whatever the file already held.

## Exit Codes

| Code | Meaning |
| ---- | ------- |
| 0 | No violations reported |
| 1 | Violations reported |
| 2 | Configuration error or command-line usage error |

A step also exits 1, before Ruff is started, when the Orb refuses its input: an item in `extra_args` that is [not accepted](#extra-arguments), or `fix_only: true` together with `fix: never`.

`exit_zero` applies to reported violations only, so a broken configuration keeps failing the step. Note that a path which does not exist is reported as a violation and exits 1, so `exit_zero` **does** mask it. A reporting step that uses `exit_zero` should therefore always be paired with a gating step that does not.

With `output_file`, `ruff/check` also exits 2 when the file cannot be prepared, in which case Ruff is not run, and when Ruff exited 0 but `tee` cannot read the report back. A non-zero status from Ruff is always passed through unchanged. See [Report handling and exit status](#report-handling-and-exit-status).

`ruff format` has no `--exit-zero`. In `check` and `diff` mode it exits 1 when a file would be reformatted.

## Upgrading from 0.0.1

Two kinds of change separate 1.0.0 from 0.0.1: every parameter name made of several words was renamed, and a few bugs were fixed in ways that change what a step does.

### Renamed parameters

Parameter names now use underscores instead of hyphens, as CircleCI's own configuration keys do. Only the names changed: the types, defaults, accepted values and behaviour of these parameters are the same. The old names are not kept as aliases, so a configuration that still uses one is rejected when CircleCI compiles it, before any job starts. Rename them when moving to 1.0.0:

| 0.0.1 | 1.0.0 | Command |
| ----- | ----- | ------- |
| `cache-dir` | `cache_dir` | `ruff/check` and `ruff/format` |
| `config-file` | `config_file` | `ruff/check` and `ruff/format` |
| `config-overrides` | `config_overrides` | `ruff/check` and `ruff/format` |
| `excluded-paths` | `excluded_paths` | `ruff/check` and `ruff/format` |
| `exit-non-zero-on-fix` | `exit_non_zero_on_fix` | `ruff/check` |
| `exit-non-zero-on-format` | `exit_non_zero_on_format` | `ruff/format` |
| `exit-zero` | `exit_zero` | `ruff/check` |
| `extend-excluded-paths` | `extend_excluded_paths` | `ruff/check` and `ruff/format` |
| `extend-per-file-ignores` | `extend_per_file_ignores` | `ruff/check` |
| `extend-selected-rules` | `extend_selected_rules` | `ruff/check` |
| `extra-args` | `extra_args` | `ruff/check` and `ruff/format` |
| `fix-only` | `fix_only` | `ruff/check` |
| `force-exclude` | `force_exclude` | `ruff/check` and `ruff/format` |
| `ignore-noqa` | `ignore_noqa` | `ruff/check` |
| `ignored-rules` | `ignored_rules` | `ruff/check` |
| `line-length` | `line_length` | `ruff/check` and `ruff/format` |
| `no-cache` | `no_cache` | `ruff/check` and `ruff/format` |
| `output-file` | `output_file` | `ruff/check` |
| `output-format` | `output_format` | `ruff/check` and `ruff/format` |
| `per-file-ignores` | `per_file_ignores` | `ruff/check` |
| `respect-gitignore` | `respect_gitignore` | `ruff/check` and `ruff/format` |
| `selected-rules` | `selected_rules` | `ruff/check` |
| `show-fixes` | `show_fixes` | `ruff/check` |
| `target-version` | `target_version` | `ruff/check` and `ruff/format` |

`color`, `diff`, `extensions`, `fix`, `fixable`, `isolated`, `mode`, `preview`, `statistics`, `targets`, `tee`, `unfixable`, `verbosity` keep their names, as do `version` of `ruff/install` and `image` and `resource_class` of the executor.

The rename applies to the Orb's parameters only. Ruff's own command-line options and configuration keys keep their hyphens: `--output-file`, `--fix-only`, `line-length = 100` and `[tool.ruff.lint.per-file-ignores]` are written as before, including inside `extra_args` and `config_overrides`.

### Changed behaviour

These are bug fixes, independent of the rename. Each links to the section that describes the current behaviour.

* `output_file` is emptied before Ruff runs, so a report left by an earlier run is no longer shown or stored when Ruff stops on an error. The step exits 2 when the file cannot be prepared. See [Report handling and exit status](#report-handling-and-exit-status).
* `targets`, `extensions` and `extra_args` take every line, not only the first. `targets` is always a list of paths, so options written there are no longer applied. See [Choosing the Files](#choosing-the-files).
* `fix: never` also passes `--no-fix-only`, and some `extra_args` items are refused before Ruff is started. See [Fixing](#fixing) and [Extra Arguments](#extra-arguments).
* `ruff/check` and `ruff/format` are one step each, which prints the Ruff version after checking its input.

## Commands

### `ruff/install`

Installs Ruff using `python -m pip`.

Using `python -m pip` ensures that Ruff is installed into the Python environment associated with the executor's `python` command instead of relying on whichever standalone `pip` executable appears first in `PATH`.

Ruff has no plugin system, so unlike the flake8 Orb there is no `plugins` parameter.

| Parameter | Type   | Default | Description                                            |
| --------- | ------ | ------- | ------------------------------------------------------ |
| `version` | string | `""`    | Ruff version to install; empty installs the latest release |

### `ruff/check`

Runs `ruff check` against the selected source files or directories.

| Parameter                  | Type    | Default   | Description                                                                |
| -------------------------- | ------- | --------- | -------------------------------------------------------------------------- |
| `cache_dir`                | string  | `""`      | Path to Ruff's cache directory                                             |
| `color`                    | enum    | `auto`    | Colour the output: `auto`, `always` or `never`                             |
| `config_file`              | string  | `""`      | Path of a TOML configuration file                                          |
| `config_overrides`         | string  | `""`      | Newline-separated TOML `KEY = VALUE` pairs, each passed as `--config`       |
| `diff`                     | boolean | `false`   | Print the diff each fix would produce instead of applying it               |
| `excluded_paths`           | string  | `""`      | Comma-separated exclusion globs, replaces the built-in list                |
| `exit_non_zero_on_fix`     | boolean | `false`   | Fail the step when any file was modified by fixing                         |
| `exit_zero`                | boolean | `false`   | Exit successfully when violations are reported                             |
| `extend_excluded_paths`    | string  | `""`      | Comma-separated exclusion globs, added to the built-in list               |
| `extend_per_file_ignores`  | string  | `""`      | Comma-separated `pattern:rule` pairs, added to the configured ones          |
| `extend_selected_rules`    | string  | `""`      | Rule codes added to the current selection                                  |
| `extensions`               | string  | `""`      | `extension:language` mappings separated by spaces, tabs or newlines, each passed as `--extension` |
| `extra_args`               | string  | `""`      | Additional arguments separated by spaces, tabs or newlines; some items are refused, see [Extra Arguments](#extra-arguments) |
| `fix`                      | enum    | `never`   | Whether Ruff may rewrite files: `never`, `auto`, `safe` or `unsafe`; see [Fixing](#fixing) |
| `fix_only`                 | boolean | `false`   | Apply fixes without reporting the remaining violations                     |
| `fixable`                  | string  | `""`      | Rule codes that may be fixed                                              |
| `force_exclude`            | enum    | `auto`    | Apply exclusions to paths named on the command line                        |
| `ignore_noqa`              | boolean | `false`   | Report violations on `# noqa` lines as well                                |
| `ignored_rules`            | string  | `""`      | Rule codes to disable                                                     |
| `isolated`                 | boolean | `false`   | Ignore every configuration file                                           |
| `line_length`              | string  | `""`      | Maximum line length, applied as a configuration override                   |
| `no_cache`                 | boolean | `false`   | Disable cache reads                                                       |
| `output_file`              | string  | `""`      | Path to write the report to                                               |
| `output_format`            | enum    | `default` | Serialization format for the reported violations                          |
| `per_file_ignores`         | string  | `""`      | Comma-separated `pattern:rule` pairs, replaces the configured ones          |
| `preview`                  | enum    | `auto`    | Enable unstable rules and fixes                                           |
| `respect_gitignore`        | enum    | `auto`    | Honour `.gitignore` and other standard ignore files                        |
| `selected_rules`           | string  | `""`      | Rule codes to enable, or `ALL`; replaces the selection                    |
| `show_fixes`               | enum    | `auto`    | Print an enumeration of the applied fixes                                 |
| `statistics`               | boolean | `false`   | Print a count per rule instead of the individual violations               |
| `target_version`           | enum    | `default` | Minimum Python version the code must support                              |
| `targets`                  | string  | `.`       | Files or directories separated by spaces, tabs or newlines; every item is a path, see [Choosing the Files](#choosing-the-files) |
| `tee`                      | boolean | `true`    | With `output_file`, also print the report to the job log                   |
| `unfixable`                | string  | `""`      | Rule codes that must never be fixed                                       |
| `verbosity`                | enum    | `default` | Log verbosity: `default`, `verbose`, `quiet` or `silent`                  |

The `auto` value of the `force_exclude`, `preview`, `respect_gitignore` and `show_fixes` enums passes no flag, so the configuration file decides. `enabled` and `disabled` pass the `--flag` and `--no-flag` forms respectively, which makes it possible to override a configuration file in either direction.

### `ruff/format`

Runs `ruff format` against the selected source files or directories.

| Parameter                  | Type    | Default   | Description                                                     |
| -------------------------- | ------- | --------- | --------------------------------------------------------------- |
| `cache_dir`                | string  | `""`      | Path to Ruff's cache directory                                  |
| `color`                    | enum    | `auto`    | Colour the output: `auto`, `always` or `never`                  |
| `config_file`              | string  | `""`      | Path of a TOML configuration file                               |
| `config_overrides`         | string  | `""`      | Newline-separated TOML `KEY = VALUE` pairs, each passed as `--config` |
| `excluded_paths`           | string  | `""`      | Comma-separated exclusion globs, replaces the built-in list     |
| `exit_non_zero_on_format`  | boolean | `false`   | Fail the step when any file was reformatted                     |
| `extend_excluded_paths`    | string  | `""`      | Comma-separated exclusion globs, added to the built-in list     |
| `extensions`               | string  | `""`      | `extension:language` mappings separated by spaces, tabs or newlines, each passed as `--extension` |
| `extra_args`               | string  | `""`      | Additional arguments separated by spaces, tabs or newlines; `--` and items starting with `@` are refused, see [Extra Arguments](#extra-arguments) |
| `force_exclude`            | enum    | `auto`    | Apply exclusions to paths named on the command line             |
| `isolated`                 | boolean | `false`   | Ignore every configuration file                                 |
| `line_length`              | string  | `""`      | Maximum line length the formatter wraps to                      |
| `mode`                     | enum    | `check`   | `check`, `diff` or `write`                                      |
| `no_cache`                 | boolean | `false`   | Disable cache reads                                             |
| `output_format`            | enum    | `default` | Serialization format used in `check` mode                       |
| `preview`                  | enum    | `auto`    | Enable unstable formatting                                      |
| `respect_gitignore`        | enum    | `auto`    | Honour `.gitignore` and other standard ignore files             |
| `target_version`           | enum    | `default` | Minimum Python version the code must support                    |
| `targets`                  | string  | `.`       | Files or directories separated by spaces, tabs or newlines; every item is a path, see [Choosing the Files](#choosing-the-files) |
| `verbosity`                | enum    | `default` | Log verbosity: `default`, `verbose`, `quiet` or `silent`        |

`ruff format` has no `--output-file`, so there is no `output_file` or `tee` parameter here.

## Executor

### `ruff/default`

A configurable CircleCI Python executor for running Ruff.

Ruff is not preinstalled. Run `ruff/install` before `ruff/check` or `ruff/format`.

| Parameter        | Type   | Default            | Description                       |
| ---------------- | ------ | ------------------ | --------------------------------- |
| `image`          | string | `cimg/python:3.14` | Docker image used by the executor |
| `resource_class` | enum   | `small`            | CircleCI resource class           |

Supported resource classes are `small`, `medium`, `medium+` and `large`.

```yaml
executor:
  name: ruff/default
  image: cimg/python:3.13
  resource_class: medium
```

Ruff is a Rust binary distributed as a wheel, so it does not run on the Python interpreter of the image. The Python version therefore affects only which interpreter `python -m pip` installs into, not how the checks behave. Use `target_version` to control the Python version the rules assume.

## Changelog

Release history and notable changes are recorded in [CHANGELOG.md](https://github.com/circleci-orbs-mamono210/ruff/blob/main/CHANGELOG.md).

## Development

The Orb source is stored under `src/` in unpacked Orb format. The CircleCI pipeline uses the Orb Development Kit of `circleci/orb-tools@12.5.0` and runs in two parts:

1. `.circleci/config.yml` runs the `lint-pack` workflow: `orb-tools/lint`, `orb-tools/pack`, `orb-tools/review` and `shellcheck/check`. When all four pass, `orb-tools/continue` puts the Orb that `orb-tools/pack` built from this commit into `.circleci/test-deploy.yml` under the name `ruff` and continues the pipeline with it.
2. `.circleci/test-deploy.yml` runs the `test-deploy` workflow. Its integration tests run that Orb. `orb-tools/publish` publishes a production version only for a tag of the form `vX.Y.Z`, and only after every other job of the workflow has passed.

No development version is published to the registry, so branches and pull requests need no publishing token. Only the production publish job uses the `CIRCLECI_ORBS` context, which has to provide a `CIRCLE_TOKEN` that may publish to the `orbss` namespace.

The Orb slug has to exist in the registry before the first publish:

```console
circleci orb create orbss/ruff --no-prompt
```

Production releases use Semantic Versioning tags. The `v1.0.0` tag publishes Orb version `1.0.0`. A tag in any other form runs the checks and tests but publishes nothing.

### Checking the usage examples before a release tag

`orb-tools/review` runs the review check RC011 with `orb_name: ruff`. RC011 requires every usage example in `src/examples/` to reference the Orb with the major version of the release tag, for example `orbss/ruff@1.0.0` or `orbss/ruff@1` for `v1.0.0`. It runs only in a pipeline for a `vX.Y.Z` tag and is skipped everywhere else, so a passing branch pipeline does not show that it will pass. When it fails on a release tag, the pipeline stops before publishing; nothing deletes or moves the tag automatically.

Run RC011 under the conditions of the planned tag before creating it, on the commit to be tagged. Use the review checks of the orb-tools version the pipeline pins. This needs `bats-core` and `yq` v4 on `PATH`. From the repository root:

```console
git clone --depth 1 --branch v12.5.0 https://github.com/CircleCI-Public/orb-tools-orb.git /tmp/orb-tools-orb
CIRCLE_TAG=v1.0.0 ORB_VAL_ORB_NAME=ruff ORB_VAL_SOURCE_DIR=src \
  bats --filter RC011 /tmp/orb-tools-orb/src/scripts/review.bats
```

The check has passed only when the output reads `ok 1 RC011: ...` without `# skip`. A `# skip` means that `CIRCLE_TAG` or `ORB_VAL_ORB_NAME` did not reach the check. A `not ok` names the first example that references another major version.

## License

This project is released under the [MIT License](https://github.com/circleci-orbs-mamono210/ruff/blob/main/LICENSE).
