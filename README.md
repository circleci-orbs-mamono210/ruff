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

The default executor uses a CircleCI Python convenience image. Ruff is not preinstalled, so run `ruff/install` before `ruff/check`. This is the minimal configuration:

```yaml
version: 2.1

orbs:
  ruff: orbss/ruff@1.0.0

jobs:
  execute-ruff:
    executor: ruff/default
    steps:
      - checkout
      - ruff/install
      - ruff/check

workflows:
  ruff:
    jobs:
      - execute-ruff
```

`ruff/install` installs Ruff 0.16.2, the version this release of the Orb is tested with; see [Pin the Version](#pin-the-version). `ruff/check` then checks the current working directory recursively with Ruff's default rule set, and the job fails when any violation is reported.

Both `ruff/check` and `ruff/format` first check their input, then print the installed Ruff version using `ruff --version`, and then run Ruff, all in one step. A step whose input is refused does not start Ruff at all; see [Extra Arguments](#extra-arguments).

The examples in this README and in `src/examples/` reference `orbss/ruff@1.0.0`, the release they describe, and are meant for use once that version is published in the Orb Registry. Until then, the same source can only be used as an inline Orb, which is how this repository's pipeline tests it; see [Development](#development).

## Pin the Version

Ruff is pre-1.0 and its releases are not backward compatible in the way a stable tool's are. Version 0.16.0 raised the default rule set **from 59 rules to 413**, which turned many green pipelines red without any change to the repository under test.

`ruff/install` therefore pins Ruff by default. Without `version`, it installs Ruff 0.16.2, the version this release of the Orb is tested with, and what this README describes as verified is the behaviour of Ruff 0.16.2. A later release of the Orb may move the default to a newer Ruff after testing it, and the [changelog](https://github.com/circleci-orbs-mamono210/ruff/blob/main/CHANGELOG.md) says so.

`version` installs any other release as given, for example to keep a version while upgrading the Orb:

```yaml
- ruff/install:
    version: "0.16.2"
```

An empty `version` installs the latest release, as an unset `version` did before 1.0.0:

```yaml
- ruff/install:
    version: ""
```

That is not reproducible, and the Orb's tests do not cover it: a new Ruff release can add rules or change the formatter's output and turn a green pipeline red. The values that `target_version` and `output_format` accept are those of Ruff 0.16.2 as well. Another Ruff version may reject one of them, and the step then fails with exit 2.

If a repository was configured against the older defaults, restoring them is a one-line change:

```yaml
- ruff/check:
    selected_rules: E4,E7,E9,F
```

With Ruff 0.16.2 this selects the same 59 rules that Ruff 0.15 enabled by default.

## Coming from flake8 and isort

Ruff can take over the work of flake8, isort and Black with a single binary, so an Orb that mirrors the flake8 Orb one-to-one would misrepresent the tool. The differences worth planning around, as of flake8 7.5.0 and Ruff 0.16.2:

| Topic | flake8 | Ruff |
| ----- | ------ | ---- |
| Plugins | Separate pip packages | None; every rule is built in and selected with `selected_rules` |
| Default rules | pycodestyle and pyflakes, plus mccabe once `max-complexity` is set | 413 rules from 34 linters; 59 in Ruff 0.15 |
| Line length | `E501` on by default, at 79 | `E501` is **not** in the default set; add it with `extend_selected_rules` |
| Import sorting | `isort` as a separate tool | `I001`, in the default set since Ruff 0.16.0 |
| Formatting | Black as a separate tool | `ruff/format` |
| Per-file ignores | `pattern:CODE,CODE` pairs, separated by whitespace | Comma-separated `pattern:CODE` pairs, one code each; `pattern:F401,E501` is a configuration error |
| Config file | `setup.cfg`, `tox.ini`, `.flake8` | `pyproject.toml`, `ruff.toml`, `.ruff.toml` |
| Ignored files | Its own exclusion list | Also honours `.gitignore` by default |

A migration that keeps each change reviewable usually goes like this:

1. Replace the flake8 and isort steps with `ruff/install` and `ruff/check`, and a Black step with `ruff/format`.
2. Gate on a narrow set first: `E4,E7,E9,F`, the rules Ruff 0.15 enabled by default, plus `E501` and `I` for what flake8's line length check and isort covered. Set `line_length` to flake8's `max-line-length`.
3. Move the settings that matter. `extend-ignore` becomes `ignored_rules`, `per-file-ignores` becomes `per_file_ignores` in Ruff's form, `exclude` becomes `extend_excluded_paths`, and isort's settings go under `[tool.ruff.lint.isort]` in a Ruff configuration file. Ruff does not read flake8's or isort's settings: with Ruff 0.16.2, `max-line-length` in the `[flake8]` section of `setup.cfg` has no effect.
4. Report on Ruff's default set in a second step that does not gate on violations, and store the report.
5. Widen the gate once the report is manageable.

Steps 2 and 4 look like this:

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

The second step shows how much work adopting Ruff's default set would be. `exit_zero` keeps the violations it reports from failing it, but it still fails on a configuration or command-line error (exit 2), on an input the Orb refuses (exit 1) and when `output_file` cannot be prepared (exit 2); see [Exit Codes](#exit-codes). It runs only when the first step passed, because CircleCI skips the ordinary steps after a failed one. `store_artifacts` runs either way.

With Ruff 0.16.2 the default set does not contain all of the old one: 18 rules of `E4,E7,E9,F`, among them `E402`, `E731` and `F403`, are left out. The report of the second step therefore does not show them, and a gate that moves to the default set later drops them unless `extend_selected_rules` adds them back.

The Orb's own tests check how its parameters reach Ruff, on the Orb's test files. They do not compare Ruff's findings with those of flake8 or isort. A Ruff rule with the same code as a flake8 check is Ruff's own implementation and can report differently, so compare the reports on your own code before removing the old steps. Ruff honours flake8-style `# noqa` and `# noqa: CODE` comments.

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

`line_length` is passed as a `--config "line-length = N"` override rather than as a command-line flag, because `ruff check --line-length` is absent from the help output of Ruff 0.16.2 and is not part of its documented interface. The limit is only *reported* when `E501` is selected. On its own it still changes what other rules expect, for example where `I001` wants a long import wrapped. It does not reach `ruff/format`, which takes its own `line_length`. When `config_overrides` sets `line-length` as well, the value from `config_overrides` wins; see [Which setting wins](#which-setting-wins).

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
| `check` | Reports every file that would be reformatted, in `output_format`; with Ruff 0.16.2 the default `full` report also shows the change. Fails the step if there are any |
| `diff` | Prints the changes as a unified diff instead, with the summary on standard error, and ignores `output_format`. Fails the step if there are any |
| `write` | **Rewrites the files in place**; only useful when the job goes on to commit the result |

> Since Ruff 0.16.0 the formatter also reformats Python code blocks inside Markdown files, so `targets: .` reaches every `.md` file in the repository. Add `*.md` to `extend_excluded_paths` when that is not wanted.

Neither `check` nor `diff` rewrites the files it is given. This is verified with Ruff 0.16.2 for runs set up through the Orb's own parameters, including settings that come from a configuration file or from `config_overrides`. It does not cover `extra_args` or other Ruff versions, and Ruff's cache is still written.

`line_length` is a first-class formatter flag here. Keep it in step with the `line_length` given to `ruff/check`, because the two commands configure it independently. Unlike in `ruff/check`, it wins over a `line-length` in `config_overrides`; see [Which setting wins](#which-setting-wins).

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

### Which setting wins

When two places set the same thing, Ruff 0.16.2 resolves it as follows, run through the Orb's commands:

* `config_overrides` wins over the configuration file, including one named by `config_file`.
* A parameter that passes a command-line flag wins over the same setting in `config_overrides`: `selected_rules`, which passes `--select`, over `lint.select`, and `line_length` of `ruff/format`, which passes `--line-length`, over `line-length`.
* When `config_overrides` sets the same key on two lines, the first line wins.
* `line_length` of `ruff/check` is itself a `--config` override, passed after the lines of `config_overrides`. When both set the line length, `ruff/check` therefore uses the value from `config_overrides`, while `ruff/format` uses `line_length`. Set the line length in one place only.

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
* A path that does not exist is passed on like any other. With Ruff 0.16.2, `ruff/check` reports it as `E902` and exits 1, which `exit_zero` turns into 0, and `ruff/format` exits 2 in every mode.
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

`extend_excluded_paths` adds to Ruff's built-in exclusions, which in Ruff 0.16.2 cover `.git`, `.venv`, `venv`, `dist`, `node_modules` and similar directories.

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

`diff` shows fixes, not violations. With Ruff 0.16.2 a violation that has no fix, such as `F821`, produces no diff, so a step whose files have only such violations exits 0. Keep a gating `ruff/check` without `diff`.

With `output_file` as well, the diff still goes to the job log, and the file receives only Ruff's summary, for example `Would fix 1 error.`. When there is nothing to fix, the file stays empty. With `tee: true` the Orb prints the summary after the diff. The step exits 1 when there is something to fix, unless `exit_zero` is set.

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

Being accepted is not a guarantee. An extra argument can still override a parameter, skip checks, change the exit status or send output elsewhere; Ruff decides how the arguments combine, and the Orb does not try to rule that out. With Ruff 0.16.2, for example:

* `--show-settings` replaces the check. Ruff prints its settings, and the step exits 0 even when the files have violations.
* `--exit-zero` turns reported violations into success, like `exit_zero`.
* `--output-file elsewhere.txt` sends the report to that file, and nothing of it reaches the job log. Together with `output_file`, Ruff exits 2, because it accepts the option only once.
* `--check` in `ruff/format` with `mode: write` makes the step report instead of rewriting.

Version 0.0.1 read `extra_args` only up to the first newline and passed every item on. Under `fix: never` it also passed `--no-fix` alone, so `fix-only = true` in a configuration, or `--fix` in `extra_args`, made the linter rewrite files.

## Saving the Report as an Artifact

Use `output_file` to write the report to a file. Before Ruff starts, the Orb creates the parent directory and empties the file, so the file only ever holds what the current run wrote. Ruff never writes colour into it, so the artifact needs no extra settings.

```yaml
version: 2.1

orbs:
  ruff: orbss/ruff@1.0.0

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

`exit_zero: true` keeps the violations it reports from failing the reporting step, so the job goes on to the ordinary steps after it, among them the second run, which decides whether the job passes. Without it, a violation would end the job at the reporting step, because CircleCI skips the ordinary steps after a failed one. `exit_zero` does not decide whether the report is stored: CircleCI runs `store_artifacts` even after an earlier step failed, but not when the job is cancelled or reaches its time limit. That the step runs does not mean every file is stored either; CircleCI may skip an empty file. A configuration error, an input the Orb refuses or a report file it cannot prepare still fails the reporting step; see [Exit Codes](#exit-codes).

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

The Orb never changes a non-zero status from Ruff, so printing the report cannot hide a failure. The status 2 for a file that cannot be prepared matches what Ruff itself returns when it cannot create the output file. In that case the Orb does not delete the file. A later `store_artifacts` step, which CircleCI runs even after the failed step, can therefore store whatever the file already held, including a report from an earlier run.

## Exit Codes

| Code | Meaning |
| ---- | ------- |
| 0 | No violations reported |
| 1 | Violations reported |
| 2 | Configuration error or command-line usage error |

A step also exits 1, before Ruff is started, when the Orb refuses its input: an item in `extra_args` that is [not accepted](#extra-arguments), or `fix_only: true` together with `fix: never`.

`exit_zero` turns reported violations into success, and nothing else. With Ruff 0.16.2, `ruff/check` exits as follows:

| Situation | Without `exit_zero` | With `exit_zero` |
| --------- | ------------------- | ---------------- |
| Violations reported | 1 | 0 |
| A path in `targets` that does not exist, reported as `E902` | 1 | 0 |
| `diff: true` with something to fix | 1 | 0 |
| A `config_file` that does not exist, or a line of `config_overrides` that is not a valid setting | 2 | 2 |
| An option Ruff does not know, given in `extra_args` | 2 | 2 |
| An input the Orb refuses; Ruff is not started | 1 | 1 |
| `output_file` cannot be prepared; Ruff is not run | 2 | 2 |

Because a path that does not exist counts as a violation, `exit_zero` **does** mask a mistyped target. A reporting step that uses `exit_zero` should therefore always be paired with a gating step that does not.

With `output_file`, `ruff/check` also exits 2 when Ruff exited 0 but `tee` cannot read the report back. A non-zero status from Ruff is always passed through unchanged. See [Report handling and exit status](#report-handling-and-exit-status).

`ruff format` has no `--exit-zero`. In `check` and `diff` mode it exits 1 when a file would be reformatted, and in every mode it exits 2 for a path that does not exist.

## Upgrading from 0.0.1

Three kinds of change separate 1.0.0 from 0.0.1: every parameter name made of several words was renamed, `ruff/install` installs a fixed Ruff version by default, and a few bugs were fixed in ways that change what a step does.

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

These changes are independent of the rename. The first is a new default, the others are bug fixes. Each links to the section that describes the current behaviour.

* `ruff/install` without `version` installs Ruff 0.16.2 instead of the latest release. Set `version: ""` to keep installing the latest release. See [Pin the Version](#pin-the-version).
* `output_file` is emptied before Ruff runs, so a report left by an earlier run is no longer shown or stored when Ruff stops on an error. The step exits 2 when the file cannot be prepared. See [Report handling and exit status](#report-handling-and-exit-status).
* `targets`, `extensions` and `extra_args` take every line, not only the first. `targets` is always a list of paths, so options written there are no longer applied. See [Choosing the Files](#choosing-the-files).
* `fix: never` also passes `--no-fix-only`, and some `extra_args` items are refused before Ruff is started. See [Fixing](#fixing) and [Extra Arguments](#extra-arguments).
* `ruff/check` and `ruff/format` are one step each, which prints the Ruff version after checking its input.

## Commands

### `ruff/install`

Installs Ruff using `python -m pip`.

Using `python -m pip` ensures that Ruff is installed into the Python environment associated with the executor's `python` command instead of relying on whichever standalone `pip` executable appears first in `PATH`.

Ruff has no plugin system, so unlike the flake8 Orb there is no `plugins` parameter.

| Parameter | Type   | Default    | Description                                            |
| --------- | ------ | ---------- | ------------------------------------------------------ |
| `version` | string | `"0.16.2"` | Ruff version to install. The default is the version this release of the Orb is tested with; an empty string installs the latest release, which is not tested |

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

### Releasing

A release is a `vX.Y.Z` tag on a commit of `main` whose pipeline has passed. Before creating the tag:

1. Give the release its own section in `CHANGELOG.md`, with the date of the release, and keep the sections of earlier releases as they are. Point the comparison link of `[Unreleased]` at the new tag, and add a link for the release that compares it with the previous tag, for example `v0.0.1...v1.0.0`. A link to a tag that does not exist yet only works once the tag is pushed.
2. Make the Orb references in this README and in `src/examples/` name the release, for example `orbss/ruff@1.0.0`. Leave the old parameter names in "Upgrading from 0.0.1" and the history in `CHANGELOG.md` alone.
3. When the Ruff version changes, follow [Updating the Ruff version](#updating-the-ruff-version).
4. Run RC011 under the conditions of the planned tag; see [Checking the usage examples before a release tag](#checking-the-usage-examples-before-a-release-tag).
5. Push the tag to the final commit, the one that adds the date to `CHANGELOG.md`, once its pipeline has passed. Do not tag an earlier commit whose pipeline passed. `orb-tools/publish` publishes the Orb only after every other job of the tag's pipeline has passed. Nothing deletes or moves the tag automatically, so after a failure, look at the tag, the pipeline and the registry before doing anything else.

### Trying an example before it is published

The examples name a version that is only in the registry once it is published. Before that, try one with the Orb packed from the commit instead: pack it with `circleci orb pack src > orb.yml`, and put the content of `orb.yml` under `orbs:` as `ruff:`, in place of `orbss/ruff@1.0.0`. This is what `orb-tools/continue` does for `.circleci/test-deploy.yml`.

### Updating the Ruff version

Each release of the Orb is tested with one Ruff version, the one `ruff/install` installs by default. These places name it, and the integration tests fail until they agree:

| Where | What |
| ----- | ---- |
| `src/commands/install.yml` | The default of `version` |
| `.circleci/test-deploy.yml` | `ruff_version` at the top. Every job that installs Ruff installs this version: `command-tests` and `install-tests` install Ruff without a version and fail unless they get this one, the others name it |
| `tests/arguments/check-parameters.py` and `tests/arguments/format-parameters.py` | `RUFF_VERSION`, the version their expected Ruff output is written for. They do not run their Ruff cases with another |

Moving to another Ruff version changes what `ruff/install` gives everyone who does not set `version`, so make it a change of its own:

1. Read Ruff's changelog for every release in between. Note changes to the default rule set, to the formatter's style, to the command-line options the commands use and to the values of `--output-format` and `--target-version`.
2. Install the new version and compare `ruff check --help` and `ruff format --help` with `src/scripts/check.sh` and `src/scripts/format.sh`: every option the scripts pass must still exist and mean the same.
3. Change the version in the three places above. Change the enums of `output_format` and `target_version` in `src/commands/check.yml` and `src/commands/format.yml` when Ruff's values changed: `verify-enums` in `check-parameter-tests` and `format-parameter-tests` fails while an enum has a value that Ruff does not list, or lacks one that it does.
4. Run the integration tests. A failing fixture test, regression script or Ruff case of `check-parameters.py` and `format-parameters.py` shows a change in what Ruff does or prints. Decide for each whether the Orb or the expectation has to change.
5. Search the repository for the old version, for example with `git grep -nF 0.16.2`, and update every text that names it as the tested version: this README, the command descriptions, the examples in `src/examples/`, the documents and comments under `tests/` and the comments of `.circleci/test-deploy.yml`. The entries of `CHANGELOG.md` for earlier releases keep the version they had.
6. Weigh the effect on pipelines that do not set `version`: a larger default rule set or a new formatter style changes what they report. Describe it in the changelog and choose the Orb's version number to match.

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
