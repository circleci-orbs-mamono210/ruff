# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

* `ruff/check` no longer shows or keeps an earlier run's report when `output_file` is set. Ruff leaves the file untouched when it stops on a configuration or command-line error (exit 2), so the old report used to be printed as `Report written to …` and stored as if it were the new result. The Orb now creates the parent directory and empties the file before Ruff runs, and `tee` prints the report only when this run wrote something to it. An empty report is announced as `Report <path> is empty.` instead.
* The `parameter-tests` integration job now stores every report it writes as a build artifact. `store_artifacts` used to run before four of the reports were written, so `config-overrides.txt`, `no-tee.txt`, `tee.txt` and `isolated-line-length.txt` were never stored. It is now the last step, preceded by a check that the reports match the documented list, that the expected ones are empty and the rest are not, and that none carries the stale-report marker.
* The format `line_length` integration test now runs through the Orb, both `format.sh` and the `ruff/format` command, instead of calling Ruff directly. It uses a pair of fixtures whose result differs between `line_length: "40"` and Ruff's default, so a value that never reaches Ruff fails the test. `format-tests` also checks at the end that every fixture is unchanged.
* `targets` and `extensions` of `ruff/check` and `ruff/format` now take every line. Both used to be read only up to the first newline, so a YAML block with one path or mapping per line silently dropped all but the first. Both are now split on spaces, tabs and newlines without evaluating anything. Empty lines are ignored, and an empty or blank `targets` means `.`.
* `targets` is now always a list of paths. The paths follow `--`, and a relative path that starts with `-` or `@` is passed as `./<path>`. A file named `-`, `--help` or `@args` is now checked or formatted as that file; Ruff used to read standard input for `-`, run `--help` as an option and expand `@args` as an argument file.
* New integration tests, `tests/arguments/regression.sh`, compare the arguments both scripts pass to Ruff with the expected ones and run Ruff 0.16.2 on files named `-`, `--help` and `@args`.
* `fix: never` of `ruff/check` now passes `--no-fix-only` as well as `--no-fix`. `--no-fix` alone did not stop the linter from rewriting files when `fix-only = true` was set in `ruff.toml`, in `pyproject.toml` or through `config_overrides`.
* `extra_args` of `ruff/check` and `ruff/format` now takes every line. It used to be read only up to the first newline. It is split on spaces, tabs and newlines without evaluating anything, like `targets` and `extensions`.
* The integration tests now cover what the commands refuse and what `fix: never` and the format modes `check` and `diff` leave alone. `tests/arguments/regression.sh` runs each refusal as a child process and requires a non-zero status, no start of Ruff and an unchanged target and report. The new `packed-command-tests` job checks with `tests/arguments/packed-commands.py` that the packed commands run those same scripts and check their input before anything else.
* The description of `excluded_paths` of `ruff/check` named `__pycache__` among Ruff's default exclusions, which Ruff 0.16.2 does not list. It now names `.git`, `.venv`, `venv`, `dist` and `node_modules`. The description of `diff` now says that `exit_zero` keeps a diff from failing the step, and that the diff goes to the job log while `output_file` receives only Ruff's summary line.
* The `diff` mode test of `ruff/format` told `diff` from `check` by a line of code that both modes print since Ruff 0.16, so a `diff` mode that ran as `check` mode passed it. It now requires a unified diff on standard output and the summary on standard error, none of the diagnostic of `check` mode, exit 1 and an unchanged file, and the `check` mode test requires the opposite form. The descriptions of `mode` and `output_format` of `ruff/format` and the mode table of the README no longer say that only `diff` shows the change: with Ruff 0.16.2 the default report of `check` shows it too, and `diff` prints it as a unified diff and ignores `output_format`.

### Changed

* The CircleCI pipeline of this repository uses the Orb Development Kit of `circleci/orb-tools@12.5.0` instead of 11.1. The integration tests now run the Orb packed from the same commit, which `orb-tools/continue` injects into `.circleci/test-deploy.yml`, so no development version is published for a branch or pull request any more. The `CIRCLECI_ORBS` context is used only by the production publish job, which runs for a `vX.Y.Z` tag after every check and test has passed. The review now includes RC010, and RC011 with `orb_name: ruff`, which fails a release tag whose usage examples reference another major version. "Development" in the README describes how to run RC011 before the tag is created.
* **Breaking:** every parameter name made of several words now uses underscores instead of hyphens: 23 parameters of `ruff/check` and 13 of `ruff/format`, 24 distinct names, for example `output-file` → `output_file` and `extra-args` → `extra_args`. Types, defaults, accepted values and behaviour are unchanged, and the `PARAM_*` environment variables the scripts read keep their names. The old names are not accepted as aliases. The README, the examples, the integration tests and the messages of the scripts use the new names, and "Upgrading from 0.0.1" in the README lists every old and new name. Ruff's own command-line options and configuration keys are not affected. The other entries of this release use the new names; the 0.0.1 entries keep the names that release had.
* `ruff/check` exits 2 without running Ruff when it cannot create the parent directory of `output_file` or empty the file. A non-zero status from Ruff is always returned unchanged, including when printing the report fails. When Ruff exits 0 but `tee` cannot read the report back, the step exits 2; previously a missing report passed silently.
* Options can no longer be passed through `targets`. Such an item is now looked up as a file and the option is not applied: `ruff/check` reports a missing file (`E902`, exit 1, which `exit_zero` masks) and `ruff/format` exits 2. Use `extra_args` for options. A path that contains whitespace still cannot be given, and quotes are still not interpreted.
* `ruff/check` and `ruff/format` now refuse some `extra_args` items and exit 1 before Ruff is started: `--` and any item that starts with `@`, always, and under `fix: never` of `ruff/check` also `--fix`, `--fix-only`, `--add-noqa` and `--add-ignore`, each alone or followed by `=` and a value. Everything else is still passed on as written, including `--show-settings`. See "Extra Arguments" in the README.
* `ruff/check` and `ruff/format` are now a single step each. The step checks its input, prints `ruff --version` and then runs Ruff, so the separate `Show Ruff version` step is gone and a refused input starts nothing. `src/scripts/show-version.sh` was removed.
* The README and the command descriptions no longer promise without conditions that `fix: never` and the format modes `check` and `diff` leave the checkout untouched. They now state what is verified: Ruff 0.16.2, runs set up through the Orb's own parameters, and the refused `extra_args` items. Other `extra_args`, other Ruff versions, and the report and cache files are outside that statement.
* The `Command:` line in the job log now shows the `--` before the paths and the `./` added in front of a path. `ruff/check` no longer prints a `PARAM_EXIT_ZERO=…` line and `ruff/format` no longer prints a `PARAM_MODE=…` line before it.
* The integration tests that run `check.sh` and `format.sh` directly now start from shared defaults, `tests/defaults/check.sh` and `tests/defaults/format.sh`, instead of the `write-check-defaults` command and the `PARAM_*` lists repeated in `format-tests` and `tests/arguments/regression.sh`. `packed-command-tests` compares both files with the defaults of the packed commands, so a parameter or a default that changes on one side only fails it. `command-tests` also runs `ruff/check` with its defaults on the violation fixtures and checks the reported rules, the output format, that nothing was fixed, and that `check.sh` with the shared defaults writes the same report.
* The integration jobs check the fixtures with `tests/fixtures.sh`. Right after checkout each job requires the fixtures to exist and takes a snapshot of `tests/`, and it compares with that snapshot after every test that rewrites and restores a fixture and after its last test.
* The new `executor-image-test` job runs `ruff/default` with `image: cimg/python:3.13`, and `resource-class-test` keeps `resource_class: medium`. Every job that runs Ruff records its commit, job URL, Python, operating system, Ruff version and CPU and memory limits as the artifact `environment/<job>.json`. The new `executor-comparison` job checks with `tests/environment/compare.py` that the Python version that `command-tests`, `executor-image-test` and `resource-class-test` recorded matches the image each of them asked for, and that their CPU and memory limits follow the resource classes they asked for. The executor's defaults are taken from the packed orb. The production publish job requires both new jobs as well.
* The integration tests now check every public parameter of `ruff/check`. The new `check-parameter-tests` job runs the packed command with a recording stand-in for Ruff for every parameter and every value of an enum, and compares the arguments received. With Ruff 0.16.2 it checks `diff`, `output_format: json`, `extensions`, `fixable`, `unfixable`, `fix: safe` against `fix: unsafe`, `ignore_noqa`, `show_fixes`, `preview`, `force_exclude`, `respect_gitignore`, `cache_dir` and `excluded_paths`, and the exit statuses 0, 1 and 2. `parameter-tests` also runs `output_format: json`, `diff`, `excluded_paths`, `force_exclude` and `cache_dir` through `ruff/check`. `tests/arguments/check-parameters.md` lists where each parameter is tested, and the regression cases that `parameter-tests` runs must match the list there.
* The integration tests now check every public parameter of `ruff/format`. The new `format-parameter-tests` job runs the packed command with a recording stand-in for Ruff for every parameter and every value of an enum, and compares the arguments received. With Ruff 0.16.2, run through a stand-in that records the arguments and then runs Ruff, it compares for each mode the arguments, standard output, standard error, the exit status and the files, and checks `line_length`, `config_file`, `config_overrides`, `isolated`, `excluded_paths`, `extend_excluded_paths`, `extensions`, `force_exclude`, `respect_gitignore`, `target_version`, `preview`, `no_cache`, `cache_dir`, `output_format` in every mode, `verbosity`, `extra_args`, `color` and `exit_non_zero_on_format`, configuration errors (exit 2 in every mode) and which setting wins over which. `format-tests` also runs `config_file`, `config_overrides`, `isolated`, `excluded_paths`, `force_exclude`, `target_version`, `preview`, `cache_dir` and `no_cache` through `ruff/format`. `tests/arguments/format-parameters.md` lists where each parameter is tested, and the regression cases that `format-tests` runs must match the list there.

## [0.0.1] - 2026-08-11

Initial release of the Ruff CircleCI Orb.

### Added

* Added the `ruff/install` command for installing Ruff with `python -m pip`.
* Added the `ruff/check` command for running the Ruff linter.
* Added the `ruff/format` command for running the Ruff formatter.
* Added the configurable `ruff/default` Python executor.
* Added rule selection and ignore controls with `selected-rules`, `extend-selected-rules`, `ignored-rules`, `per-file-ignores` and `extend-per-file-ignores`.
* Added exclusion controls with `excluded-paths`, `extend-excluded-paths`, `force-exclude` and `respect-gitignore`.
* Added support for explicit configuration files with `config-file`.
* Added `config-overrides` for inline TOML settings, split on newlines so a `KEY = VALUE` pair keeps its whitespace.
* Added `isolated` support for runs that must ignore every configuration file.
* Added `line-length` and `target-version` for the checks and for the formatter.
* Added `preview` support for unstable rules, fixes and formatting.
* Added fixing controls with `fix`, `fix-only`, `fixable`, `unfixable`, `show-fixes`, `diff` and `exit-non-zero-on-fix`.
* Added reporting controls with `statistics`, `output-format`, `color` and `verbosity`.
* Added `ignore-noqa` for auditing suppressed violations.
* Added `extensions` for mapping file extensions to a language.
* Added cache controls with `no-cache` and `cache-dir`.
* Added `output-file` and `tee` support for saving the report as a CircleCI artifact.
* Added `exit-zero` support for report-generation steps that should not fail when violations are found.
* Added `extra-args` for Ruff command-line options that are not exposed directly by the Orb.
* Added the `mode` parameter to `ruff/format`, covering `check`, `diff` and `write`.
* Added examples for checking, formatting, migrating from flake8 and isort, and artifact reporting.
* Added integration tests covering commands, parameters, formatting, installation and executor resource classes.
* Added Orb linting, packing, review and ShellCheck to the development pipeline.
* Added production publishing from Semantic Versioning tags.
* Added an integration test asserting that Ruff rejects `isolated` together with a `config-file` path, so the documented behaviour cannot go stale unnoticed.
* Added an integration test asserting that `fix: safe` rewrites the checkout and that `exit-non-zero-on-fix` reports it, as the complement to the existing `fix: never` test.
* Added integration tests for the `diff` mode of `ruff/format` and for `exit-non-zero-on-format`.
* Added integration tests asserting that `config-overrides` and `line-length` still reach Ruff under `isolated`, which is the positive counterpart to the `config-file` rejection test.


### Changed

* Corrected the `fix-only` description, which claimed the parameter overrides a `fix` value of `never`. The command refuses that combination instead, as the README already stated.
* Documented that Ruff draws its `isolated` restriction at configuration files rather than at settings, so `config-overrides` and `line-length` still apply under `isolated`.
* Tightened five integration assertions from "did not exit 0" to an exact expected status, so a configuration error can no longer satisfy a test that expects a violation report.
* Clarified that `extra-args` is split on whitespace rather than passed as a single verbatim string, matching the README wording and the actual script behaviour.
* Corrected the comment in the migration example, which described the isort rules and `E501` as absent from Ruff's default set. They are absent from the pre-0.16.0 set the example deliberately restores, not from the current default set.
* `fix` defaults to `never`, which passes `--no-fix` so a run cannot rewrite the checkout even when a configuration file sets `fix = true`.
* `mode` on `ruff/format` defaults to `check`, so the formatter reports rather than rewrites unless a job asks for it.
* `line-length` on `ruff/check` is applied as a `--config "line-length = N"` override, because `ruff check --line-length` is absent from Ruff's help output and is not part of its documented interface.
* `tee` is implemented by printing the report file back to the job log, because Ruff writes to `--output-file` instead of standard output and has no `--tee` of its own.
* `targets`, `extensions` and `extra-args` are parsed as whitespace-separated Bash arrays without pathname expansion.
* Documented the limitations of whitespace-separated `targets` and `extra-args`.
* Documented that `per-file-ignores` and `extend-per-file-ignores` take comma-separated pairs carrying one rule code each, unlike the whitespace-separated form flake8 uses.
* Documented Ruff exit codes used by the Orb, including configuration and command-line errors.
* Documented that `exit-zero` masks a path that does not exist, because Ruff reports it as a violation.
* Documented the 0.16.0 default rule set change from 59 to 413 rules and how to restore the previous set.
* Documented that the formatter reaches Markdown files since 0.16.0.

### Fixed

* Prevented `fix-only` from being combined with `fix: never`, which Ruff accepts while rewriting the checkout anyway.
* Prevented unintended Bash pathname expansion when parsing `targets`, `extensions` and `extra-args`.

[Unreleased]: https://github.com/circleci-orbs-mamono210/ruff/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/circleci-orbs-mamono210/ruff/releases/tag/v0.0.1
