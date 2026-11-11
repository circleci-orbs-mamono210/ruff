# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

* `ruff/check` no longer shows or keeps an earlier run's report when `output-file` is set. Ruff leaves the file untouched when it stops on a configuration or command-line error (exit 2), so the old report used to be printed as `Report written to …` and stored as if it were the new result. The Orb now creates the parent directory and empties the file before Ruff runs, and `tee` prints the report only when this run wrote something to it. An empty report is announced as `Report <path> is empty.` instead.

### Changed

* `ruff/check` exits 2 without running Ruff when it cannot create the parent directory of `output-file` or empty the file. A non-zero status from Ruff is always returned unchanged, including when printing the report fails. When Ruff exits 0 but `tee` cannot read the report back, the step exits 2; previously a missing report passed silently.

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
