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

Before running the checks, both `ruff/check` and `ruff/format` print the installed Ruff version using `ruff --version`.

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
    selected-rules: E4,E7,E9,F
```

## Coming from flake8 and isort

Ruff replaces flake8, isort and Black with a single binary, so an Orb that mirrors the flake8 Orb one-to-one would misrepresent the tool. The differences worth planning around:

| Topic | flake8 | Ruff |
| ----- | ------ | ---- |
| Plugins | Separate pip packages | None; every rule is built in and selected with `selected-rules` |
| Default rules | pycodestyle, pyflakes, mccabe | 413 rules across 34 categories since 0.16.0 |
| Line length | `E501` on by default | `E501` is **not** in the default set; add it with `extend-selected-rules` |
| Import sorting | `isort` as a separate tool | `I` rules, in the default set since 0.16.0 |
| Formatting | Black as a separate tool | `ruff/format` |
| `per-file-ignores` | Whitespace-separated pairs | Comma-separated pairs, one rule code each |
| Config file | `setup.cfg`, `tox.ini`, `.flake8` | `pyproject.toml`, `ruff.toml`, `.ruff.toml` |
| Ignored files | Its own exclusion list | Also honours `.gitignore` by default |

A staged migration usually gates on a narrow set first and reports on the full one:

```yaml
- ruff/check:
    extend-selected-rules: E501,I
    line-length: "100"
    selected-rules: E4,E7,E9,F
    targets: src

- ruff/check:
    exit-zero: true
    output-file: reports/ruff-full.txt
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
    extend-selected-rules: E501,D
    ignored-rules: D203,D213
    line-length: "100"
    targets: src tests
```

`selected-rules` **replaces** the selection, so prefer `extend-selected-rules` when the intent is to add rules. `ignored-rules` is applied after the selection and removes rules that either of them turned on.

`line-length` is passed as a `--config "line-length = N"` override rather than as a command-line flag, because `ruff check --line-length` is absent from Ruff's help output and is not part of its documented interface. Note that the limit is only *reported* when `E501` is selected; on its own it affects how other rules and the formatter wrap code.

### Per-file ignores

```yaml
- ruff/check:
    extend-per-file-ignores: "__init__.py:F401,tests/*:S101"
```

Two differences from flake8 catch people out. Ruff separates the pairs with commas rather than whitespace, and each pair carries exactly **one** rule code on the command line, so covering several rules under one pattern means repeating the pattern:

```yaml
- ruff/check:
    extend-per-file-ignores: "tests/*:S101,tests/*:F401"
```

The list form used in a config file, `"tests/*" = ["S101", "F401"]`, is not accepted on the command line.

## Formatting

`ruff/format` runs the formatter. The default mode is `check`, which reports the files that would be reformatted and leaves the checkout untouched, so it is safe to use as a CI gate.

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

> Since Ruff 0.16.0 the formatter also reformats Python code blocks inside Markdown files, so `targets: .` reaches every `.md` file in the repository. Add `*.md` to `extend-excluded-paths` when that is not wanted.

`line-length` is a first-class formatter flag here. Keep it in step with the `line-length` given to `ruff/check`, because the two commands configure it independently.

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

Use `config-file` to point at a different file:

```yaml
- ruff/check:
    config-file: build/ruff.toml
```

Use `config-overrides` for individual settings. Each line becomes its own `--config` argument, and these take precedence over every configuration file:

```yaml
- ruff/check:
    config-overrides: |
      lint.dummy-variable-rgx = "^_$"
      lint.extend-select = ["E501"]
```

The parameter is split on **newlines** rather than on whitespace, because a TOML pair contains whitespace of its own.

`isolated: true` ignores every configuration file. Unlike flake8, Ruff rejects that in combination with a `config-file` path itself, so the Orb does not need to guard against it.

Ruff draws the line at files, not at settings, so `config-overrides` and `line-length` are still applied under `isolated`:

```yaml
- ruff/check:
    config-overrides: |
      lint.extend-select = ["E501"]
    isolated: true
    line-length: "100"
```

## Excluding Paths

`extend-excluded-paths` adds to Ruff's built-in exclusions, which already cover `.git`, `__pycache__`, `.venv`, `node_modules` and similar directories.

```yaml
- ruff/check:
    extend-excluded-paths: migrations,vendor
```

`excluded-paths` replaces the built-in list entirely, so use it only when that is intended.

Ruff also honours `.gitignore` and other standard ignore files by default, which flake8 does not. Set `respect-gitignore: disabled` when generated code is both ignored by Git and expected to be linted.

`force-exclude: enabled` makes the exclusions apply to paths named directly in `targets` as well; Ruff otherwise checks an explicitly named file even when it is excluded.

## Fixing

`ruff/check` defaults to `fix: never`, which passes `--no-fix` and keeps the checkout untouched **even when a configuration file sets `fix = true`**. This is the behaviour a CI gate wants.

| Value | Behaviour |
| ----- | --------- |
| `never` | Passes `--no-fix`; the checkout is never modified |
| `auto` | Passes nothing; the configuration file decides |
| `safe` | Passes `--fix --no-unsafe-fixes` |
| `unsafe` | Passes `--fix --unsafe-fixes`; may not preserve the original intent of the code |

To show what fixing *would* change without touching anything, use `diff` instead:

```yaml
- ruff/check:
    diff: true
```

`fix-only: true` implies `--fix` and overrides `--no-fix`, which means it would rewrite the checkout despite `fix: never`. The Orb refuses that combination rather than modifying files a job was told to leave alone; set `fix` explicitly when a fixing run is intended.

## Saving the Report as an Artifact

Use `output-file` to write the report to a file. Before Ruff starts, the Orb creates the parent directory and empties the file, so the file only ever holds what the current run wrote. Ruff never writes colour into it, so the artifact needs no extra settings.

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
          exit-zero: true
          output-file: reports/ruff.json
          output-format: json
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

`exit-zero: true` prevents the reporting step from stopping the job when violations are found, so the artifact is stored. The second run is the one that decides whether the job passes.

Ruff writes to the file **instead of** standard output and has no `--tee` of its own, so the Orb prints the file back to the job log afterwards. The `tee` parameter, which defaults to `true`, controls that. Because Ruff never writes colour into the file, the log copy is always uncoloured; use `color: always` on the gating run instead, where CircleCI renders ANSI escape sequences even though the log is not a TTY.

`output-format: github` emits workflow annotations, and `junit` or `sarif` suit report ingestion.

### Report handling and exit status

Ruff leaves `output-file` untouched when it stops on a configuration or command-line error and exits 2. Because the Orb has already emptied the file, such a run leaves an empty file, so neither the log nor the artifact shows an earlier run's report.

| Situation | `output-file` afterwards | Log with `tee: true` | Exit status |
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

`exit-zero` applies to reported violations only, so a broken configuration keeps failing the step. Note that a path which does not exist is reported as a violation and exits 1, so `exit-zero` **does** mask it. A reporting step that uses `exit-zero` should therefore always be paired with a gating step that does not.

With `output-file`, `ruff/check` also exits 2 when the file cannot be prepared, in which case Ruff is not run, and when Ruff exited 0 but `tee` cannot read the report back. A non-zero status from Ruff is always passed through unchanged. See [Report handling and exit status](#report-handling-and-exit-status).

`ruff format` has no `--exit-zero`. In `check` and `diff` mode it exits 1 when a file would be reformatted.

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
| `cache-dir`                | string  | `""`      | Path to Ruff's cache directory                                             |
| `color`                    | enum    | `auto`    | Colour the output: `auto`, `always` or `never`                             |
| `config-file`              | string  | `""`      | Path of a TOML configuration file                                          |
| `config-overrides`         | string  | `""`      | Newline-separated TOML `KEY = VALUE` pairs, each passed as `--config`       |
| `diff`                     | boolean | `false`   | Print the diff each fix would produce instead of applying it               |
| `excluded-paths`           | string  | `""`      | Comma-separated exclusion globs, replaces the built-in list                |
| `exit-non-zero-on-fix`     | boolean | `false`   | Fail the step when any file was modified by fixing                         |
| `exit-zero`                | boolean | `false`   | Exit successfully when violations are reported                             |
| `extend-excluded-paths`    | string  | `""`      | Comma-separated exclusion globs, added to the built-in list               |
| `extend-per-file-ignores`  | string  | `""`      | Comma-separated `pattern:rule` pairs, added to the configured ones          |
| `extend-selected-rules`    | string  | `""`      | Rule codes added to the current selection                                  |
| `extensions`               | string  | `""`      | Whitespace-separated `extension:language` mappings                        |
| `extra-args`               | string  | `""`      | Whitespace-separated additional arguments; shell quoting and glob expansion are not evaluated |
| `fix`                      | enum    | `never`   | Whether Ruff may rewrite files: `never`, `auto`, `safe` or `unsafe`        |
| `fix-only`                 | boolean | `false`   | Apply fixes without reporting the remaining violations                     |
| `fixable`                  | string  | `""`      | Rule codes that may be fixed                                              |
| `force-exclude`            | enum    | `auto`    | Apply exclusions to paths named on the command line                        |
| `ignore-noqa`              | boolean | `false`   | Report violations on `# noqa` lines as well                                |
| `ignored-rules`            | string  | `""`      | Rule codes to disable                                                     |
| `isolated`                 | boolean | `false`   | Ignore every configuration file                                           |
| `line-length`              | string  | `""`      | Maximum line length, applied as a configuration override                   |
| `no-cache`                 | boolean | `false`   | Disable cache reads                                                       |
| `output-file`              | string  | `""`      | Path to write the report to                                               |
| `output-format`            | enum    | `default` | Serialization format for the reported violations                          |
| `per-file-ignores`         | string  | `""`      | Comma-separated `pattern:rule` pairs, replaces the configured ones          |
| `preview`                  | enum    | `auto`    | Enable unstable rules and fixes                                           |
| `respect-gitignore`        | enum    | `auto`    | Honour `.gitignore` and other standard ignore files                        |
| `selected-rules`           | string  | `""`      | Rule codes to enable, or `ALL`; replaces the selection                    |
| `show-fixes`               | enum    | `auto`    | Print an enumeration of the applied fixes                                 |
| `statistics`               | boolean | `false`   | Print a count per rule instead of the individual violations               |
| `target-version`           | enum    | `default` | Minimum Python version the code must support                              |
| `targets`                  | string  | `.`       | Whitespace-separated files or directories; shell glob expansion is not performed |
| `tee`                      | boolean | `true`    | With `output-file`, also print the report to the job log                   |
| `unfixable`                | string  | `""`      | Rule codes that must never be fixed                                       |
| `verbosity`                | enum    | `default` | Log verbosity: `default`, `verbose`, `quiet` or `silent`                  |

The `auto` value of the `force-exclude`, `preview`, `respect-gitignore` and `show-fixes` enums passes no flag, so the configuration file decides. `enabled` and `disabled` pass the `--flag` and `--no-flag` forms respectively, which makes it possible to override a configuration file in either direction.

### `ruff/format`

Runs `ruff format` against the selected source files or directories.

| Parameter                  | Type    | Default   | Description                                                     |
| -------------------------- | ------- | --------- | --------------------------------------------------------------- |
| `cache-dir`                | string  | `""`      | Path to Ruff's cache directory                                  |
| `color`                    | enum    | `auto`    | Colour the output: `auto`, `always` or `never`                  |
| `config-file`              | string  | `""`      | Path of a TOML configuration file                               |
| `config-overrides`         | string  | `""`      | Newline-separated TOML `KEY = VALUE` pairs, each passed as `--config` |
| `excluded-paths`           | string  | `""`      | Comma-separated exclusion globs, replaces the built-in list     |
| `exit-non-zero-on-format`  | boolean | `false`   | Fail the step when any file was reformatted                     |
| `extend-excluded-paths`    | string  | `""`      | Comma-separated exclusion globs, added to the built-in list     |
| `extensions`               | string  | `""`      | Whitespace-separated `extension:language` mappings              |
| `extra-args`               | string  | `""`      | Whitespace-separated additional arguments                       |
| `force-exclude`            | enum    | `auto`    | Apply exclusions to paths named on the command line             |
| `isolated`                 | boolean | `false`   | Ignore every configuration file                                 |
| `line-length`              | string  | `""`      | Maximum line length the formatter wraps to                      |
| `mode`                     | enum    | `check`   | `check`, `diff` or `write`                                      |
| `no-cache`                 | boolean | `false`   | Disable cache reads                                             |
| `output-format`            | enum    | `default` | Serialization format used in `check` mode                       |
| `preview`                  | enum    | `auto`    | Enable unstable formatting                                      |
| `respect-gitignore`        | enum    | `auto`    | Honour `.gitignore` and other standard ignore files             |
| `target-version`           | enum    | `default` | Minimum Python version the code must support                    |
| `targets`                  | string  | `.`       | Whitespace-separated files or directories                       |
| `verbosity`                | enum    | `default` | Log verbosity: `default`, `verbose`, `quiet` or `silent`        |

`ruff format` has no `--output-file`, so there is no `output-file` or `tee` parameter here.

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

Ruff is a Rust binary distributed as a wheel, so it does not run on the Python interpreter of the image. The Python version therefore affects only which interpreter `python -m pip` installs into, not how the checks behave. Use `target-version` to control the Python version the rules assume.

## Changelog

Release history and notable changes are recorded in [CHANGELOG.md](https://github.com/circleci-orbs-mamono210/ruff/blob/main/CHANGELOG.md).

## Development

The Orb source is stored under `src/` in unpacked Orb format.

The CircleCI pipeline performs:

* Orb linting
* Orb packing
* Orb review
* ShellCheck
* Integration tests
* Production publishing from semantic version tags

The Orb slug has to exist in the registry before the first publish:

```console
circleci orb create orbss/ruff --no-prompt
```

Production releases use Semantic Versioning tags:

```console
v0.0.1
```

The `v0.0.1` tag publishes Orb version `0.0.1`.

## License

This project is released under the [MIT License](https://github.com/circleci-orbs-mamono210/ruff/blob/main/LICENSE).
