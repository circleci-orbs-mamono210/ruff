# Test fixtures

Fixtures used by `.circleci/test-deploy.yml`. Ruff exits 0 when it finds no
Python files, so the tests need real sources to be meaningful.

Every job pins Ruff to the version named in `.circleci/test-deploy.yml`. The
default rule set changed substantially in 0.16.0, so an unpinned Ruff would
change what these fixtures report and make the assertions fail for reasons
unrelated to the orb.

- `clean/compliant.py` reports no violations under Ruff's default rule set and
  is already formatted, so both `ruff/check` and `ruff/format` must pass on it
  with the default parameters. It reports exactly four `E501` lines at
  `line_length: "40"` with `extend_selected_rules: E501`. The `ruff/check`
  `line_length` test and the report-replacement test both depend on that
  count. It is also not formatted at `line_length: "40"`, which the format
  `line_length` test depends on. Keep both in mind when editing the fixture.
- `line-length/formatted_at_40.py` reports no violations under the default
  rule set. It is formatted at `line_length: "40"` but not at Ruff's default
  of 88, the reverse of `clean/compliant.py`. The format `line_length` test
  uses the two together, so do not reformat it at the default length.
- `violations/unused_import.py` reports `F401` and nothing else. It backs the
  `output_file`, `tee`, `ignored_rules` and `exit_zero` tests, and it must stay
  reported under `selected_rules: F`.
- `violations/unsorted_imports.py` reports `I001` and nothing else. It must
  stay silent under `selected_rules: F` and under the pre-0.16.0 default set
  `E4,E7,E9,F`, which is what proves the selection actually narrowed.
- `violations/undefined_name.py` reports `F821` and nothing else. It is part
  of the pre-0.16.0 default set, so it backs the assertion that restoring that
  set still reports the pyflakes rules.
- `unformatted/spacing.py` reports no violations under the default rule set
  but is not formatted, which is what separates the `ruff/check` gate from the
  `ruff/format` gate. The `write` mode test rewrites it and then restores it.

`F401` and `I001` are both fixable, which is what makes the fixtures usable
for asserting that `fix: never` leaves the checkout untouched.

Do not introduce any other violation into these files. Several tests assert on
the absence of a rule as well as its presence, so an extra violation would
make them pass or fail for the wrong reason.

## Fixture snapshot

`fixtures.sh` keeps the files under `tests/` as the commit has them while the
tests run. Every job that uses the fixtures runs the `record-fixtures`
command of `.circleci/test-deploy.yml` right after checkout, and
`verify-fixtures-unchanged` after its last test.

- `bash tests/fixtures.sh record SNAPSHOT` fails unless each of the six
  fixtures above exists and has content. It then writes the SHA-256 of every
  file under `tests/` to `SNAPSHOT`, `/tmp/fixtures.sha256` in CircleCI. It
  refuses to overwrite an existing snapshot, so a later `record` cannot
  replace the reference with fixtures that a test has changed.
- `bash tests/fixtures.sh verify SNAPSHOT` fails when a file under `tests/`
  was changed, removed or added since then, and shows which one.

The tests that rewrite a fixture restore it themselves. `parameter-tests`
verifies the snapshot right after its `fix` tests, and `format-tests` after
its `write` mode test and its `exit_non_zero_on_format` test, so a fixture
that was not restored fails there, before a later test can pass because of
it. Every job verifies again at the end, which also catches a file left
behind under `tests/`.

## Format line_length test

`format-tests` exercises `line_length` through both `src/scripts/format.sh`
and the `ruff/format` command. With Ruff 0.16.2, the two fixtures above give
opposite answers at the default line length of 88 and at `40`. This detects
a dropped `line_length: "40"` value that falls back to 88, or a supplied
value that is forced to 88.

These cases do not detect every incorrect line length. For example, replacing
40 with 41 produces the same asserted results for these fixtures. The tests
check the expected formatting behavior for the selected cases; proving that
the exact requested value reaches Ruff also requires checking the arguments
passed to Ruff.

- `Verify line_length reaches the formatter through format.sh` runs
  `src/scripts/format.sh` on each fixture with and without
  `line_length: "40"`. It asserts the exact exit status and a summary line,
  and that the fixture is unchanged afterwards. A `diff` case also asserts a
  complete added line from the expected diff at 40. This distinguishes that
  case from check-mode diagnostics, but does not uniquely identify the line
  length used.
- The `ruff/format` step after it passes `line_length: "40"` through the Orb
  command, so the mapping in `src/commands/format.yml` is covered as well.
- `Verify the fixtures are unchanged after the exit_non_zero_on_format test`
  runs right before the `format.sh` step, so that step starts from the
  fixtures as checked out. See "Fixture snapshot" above.

To confirm that the test still catches a dropped value, break it on a
throwaway branch. Removing the `--line-length` handling from
`src/scripts/format.sh` fails both line_length steps. Removing
`PARAM_LINE_LENGTH` from the environment in `src/commands/format.yml` fails
the `ruff/format` step. Do not merge either change.

## Report regression

`report/regression.sh` checks how `src/scripts/check.sh` handles `output_file`
and `tee`. It calls the script directly, because several cases must fail. The
`parameter-tests` job runs it. Every case starts from the shared defaults in
`defaults/check.sh`; see "Shared defaults" below.

- Most cases seed the report with the line `ORB-TEST-STALE-REPORT-MARKER`
  first. That marker must never appear in the log or in a report afterwards.
- The cases rely on `clean/compliant.py` passing and on
  `violations/unused_import.py` reporting a single `F401`.
- The cases that run the real Ruff keep their reports under
  `reports/report-regression`, so they are stored as artifacts with the other
  reports. See "Reports stored as artifacts" below.
- `report/mock-ruff.sh` stands in for Ruff where a failure has to be injected,
  such as a report that cannot be read back. A temporary copy named `ruff` is
  put first on `PATH`. It records every call except `ruff --version`, which
  `check.sh` runs once its input checks have passed, so a case can assert
  that `ruff check` was not started.
- The read-only report case is skipped when the script runs as root, because
  root can write to a read-only file. The CircleCI convenience images run as
  an ordinary user, so the case runs in CI.

`parameter-tests` keeps the log of the run, and the job compares the cases
it ran with the list in `arguments/check-parameters.md`; see "ruff/check
parameters" below.

To run the cases outside CircleCI, install Ruff 0.16.2 and run
`bash tests/report/regression.sh`.

## Reports stored as artifacts

The `parameter-tests` job writes its reports under `reports/`. Its last step,
`store_artifacts`, stores that whole directory, so every report has been
written by then. The step before it, `Verify the reports to be stored`, checks
the directory first:

- The files must match the list in that step one to one.
- The reports listed as empty must be empty, and all others must have content.
- No report may carry the stale-report marker of `report/regression.sh`.

The step then prints the commit, the job URL, and the size and SHA-256 of every
report. The job's environment record is stored apart from the reports, as
`environment/parameter-tests.json`; see "Execution environment" below.

`store_artifacts` runs even after an earlier step has failed, so a failed job
can still store reports that failed the check or never reached it. Treat the
stored reports as verified only when `Verify the reports to be stored` and the
whole job have both succeeded.

Change the list in that step and the table below together whenever a step
adds, renames or removes a report.

| Report | Written by | Content |
| ------ | ---------- | ------- |
| `reports/line-length.txt` | `ruff/check` with `line_length: "40"`, run twice into the same file | Four `E501` lines |
| `reports/select.txt` | `ruff/check` with `selected_rules: F` | `F401` and `F821`, no `I001` |
| `reports/legacy-defaults.txt` | `ruff/check` with `selected_rules: E4,E7,E9,F` | `F401` and `F821`, no `I001` |
| `reports/config-overrides.txt` | `ruff/check` with `config_overrides` | Four `E501` lines |
| `reports/no-tee.txt` | `check.sh` with `tee: false` | `F401` |
| `reports/tee.txt` | `check.sh` with `tee: true` | `F401` |
| `reports/isolated-line-length.txt` | `ruff/check` with `isolated: true` and `line_length: "40"` | Four `E501` lines |
| `reports/output-format.json` | `ruff/check` with `output_format: json` | A JSON list with the `F401`, `F821` and `I001` findings |
| `reports/diff.txt` | `ruff/check` with `diff: true` | `Would fix 1 error.`, Ruff's summary; the diff goes to the log |
| `reports/report-regression/success-tee.txt` | `report/regression.sh`, case `success-tee` | `All checks passed!` |
| `reports/report-regression/success-no-tee.txt` | `report/regression.sh`, case `success-no-tee` | `All checks passed!` |
| `reports/report-regression/violations-tee.txt` | `report/regression.sh`, case `violations-tee` | `F401` |
| `reports/report-regression/violations-no-tee.txt` | `report/regression.sh`, case `violations-no-tee` | `F401` |
| `reports/report-regression/exit-zero-violations.txt` | `report/regression.sh`, case `exit-zero-violations` | `F401` |
| `reports/report-regression/rerun.txt` | `report/regression.sh`, case `rerun-same-result` | `F401`, once |
| `reports/report-regression/rerun-clean.txt` | `report/regression.sh`, case `rerun-clean` | `All checks passed!` |
| `reports/report-regression/config-error-tee.txt` | `report/regression.sh`, case `config-error-tee` | Empty: configuration error |
| `reports/report-regression/config-error-no-tee.txt` | `report/regression.sh`, case `config-error-no-tee` | Empty: configuration error |
| `reports/report-regression/exit-zero-config-error.txt` | `report/regression.sh`, case `exit-zero-config-error` | Empty: configuration error |
| `reports/report-regression/rerun-config-error.txt` | `report/regression.sh`, case `rerun-config-error` | Empty: configuration error |
| `reports/report-regression/rerun-empty-success.txt` | `report/regression.sh`, case `rerun-empty-success` | Empty: `verbosity: quiet` on a clean target |
| `reports/report-regression/rerun-empty-failure.txt` | `report/regression.sh`, case `rerun-empty-failure` | Empty: `verbosity: silent` on a violation |

The six empty reports are empty by design. `check.sh` empties `output_file`
before Ruff runs, and in these cases Ruff writes nothing. CircleCI's upload
may skip an empty file and log `SKIPPED, file is empty`, so an empty report
can be missing from the Artifacts tab even though the job wrote it.

To compare a run with the table, use the manifest that `Verify the reports to
be stored` prints and the log of the `store_artifacts` step. Every report with
content must appear as an artifact. Every empty report must appear either as
an artifact or as skipped. Anything else is a mismatch.

## Argument regression

`arguments/regression.sh` checks how `src/scripts/check.sh` and
`src/scripts/format.sh` pass `targets`, `extensions` and `extra_args` to Ruff,
and what they refuse. `parameter-tests` runs
`bash tests/arguments/regression.sh check` and `format-tests` runs
`bash tests/arguments/regression.sh format`. Every case starts from the shared
defaults of that command; see "Shared defaults" below. `parameter-tests`
keeps the log of the `check` run and compares the cases it ran with the list
in `arguments/check-parameters.md`, and `format-tests` does the same for the
`format` run with `arguments/format-parameters.md`.

- The argument cases put a temporary copy of `arguments/record-ruff.sh`,
  named `ruff`, first on `PATH`. It appends every call to one file, answers
  `ruff --version`, and writes the arguments of any other call to a second
  file, separated by NUL characters. The cases compare the paths after `--`,
  the value of every `--extension` and the arguments that `extra_args` adds
  with the expected lists. They require the `Command:` line to show exactly
  the arguments received, and Ruff to be started twice: `ruff --version`
  first, then the command. They cover one line, several lines, empty lines
  and indentation, tabs, empty and blank values, glob characters, quotes,
  shell syntax, backslashes, and items that start with `-` or `@`. The glob
  cases run next to files that the globs would match.
- The same cases pin what `fix` passes: `--no-fix --no-fix-only` for `never`,
  nothing for `auto`, `--fix --no-unsafe-fixes` for `safe` and
  `--fix --unsafe-fixes` for `unsafe`. They also show that `extra_args`
  outside the refused list arrive as written, for example `-ne`,
  `--output-file=x`, `-ox`, `--fixable F401` and `--show-settings`. That
  proves what is passed on, not what Ruff then does with it.
- The refusal cases run the script as a child process with the same stand-in.
  A case passes only when the script exits 1, names the refused items,
  prints no `Command:` line, did not start the stand-in even for
  `ruff --version`, and left its directory unchanged. That directory holds a
  target and an existing report, which `check.sh` also gets as `output_file`.
  An unexpected exit 0, a start of Ruff or a changed file fails the case. The
  cases cover `--` and items starting with `@` for every value of `fix` and
  every format mode, and under `fix: never` each of `--fix`, `--fix-only`,
  `--add-noqa` and `--add-ignore`, alone, as `NAME=VALUE`, on a later line
  and several at once. A refusal is never a failing step of the job itself.
- The Ruff cases run Ruff 0.16.2 on files named `-`, `--help` and `@args`,
  with other code on standard input and a file named `args` for `@args` to
  expand. Each file must be reported under its own name. They also run
  `extensions` given on several lines with an empty `targets`, compare an
  empty and a blank `targets` with `.`, and pin the exit status: 0, 1 and 2
  for both scripts, `exit_zero` for `check.sh`, and the `diff` and `write`
  modes for `format.sh`. Every log must start with the Ruff version.
- The configuration cases use a configuration that asks for changes, given
  in `ruff.toml`, in `pyproject.toml` and through `config_overrides`. For
  `check.sh` it is `fix-only = true`: under `fix: never` the file must stay
  as it is and `F401` must be reported with exit 1, and with `diff` the fix
  must be printed with exit 1. For `format.sh` it is
  `format.quote-style = "single"`: `check` must report the file and `diff`
  must print the change, both with exit 1 and without changing the file. An
  invalid setting must exit 2. `--show-settings` must reach Ruff and print
  the settings.
- No case may print a line that starts with `PARAM_`, like the debug output
  both scripts used to have.
- Everything runs in a temporary directory with an empty `ruff.toml`, which
  is removed on exit. The cases write nothing to `tests/` or `reports/`, so
  the fixture snapshot of `format-tests` and the report list of
  `parameter-tests` are unaffected, and no Ruff configuration outside that
  directory applies.

The cases compare only what `targets`, `extensions`, `extra_args` and `fix`
decide, not the whole argument list, so a change to an unrelated flag does not
break them. Reading only the first line again, dropping `--` from the Ruff
call, no longer adding `./`, dropping `--no-fix-only`, or accepting a refused
item each makes cases fail.

To run the cases outside CircleCI, install Ruff 0.16.2 and run the two
commands above.

## Packed commands

The cases above run the scripts in `src/scripts` directly. The
`packed-command-tests` job ties them to the published commands. It attaches
the workspace of `orb-tools/pack`, which holds the orb packed from the same
commit, and runs `arguments/packed-commands.py` on it. For `check` and
`format` the script requires that:

- the command is a single `run` step without `when`, `shell`, `background` or
  `working_directory`, so no step starts Ruff earlier and none runs after a
  refusal;
- the step's command is the file in `src/scripts`, apart from trailing
  whitespace and the `\<<` that `circleci orb pack` writes for every `<<` of
  an included script, so nothing wraps the script or hides its exit status;
- every parameter is handed over as `PARAM_<NAME>`, and the script reads no
  `PARAM_` variable that is not set. This holds for all 35 parameters of
  `check` and all 20 of `format`, whether or not an integration test uses
  them;
- in the script, each refusal reaches its `exit 1` before the first line that
  starts Ruff, that line is `ruff --version`, and no earlier line writes a
  file.

It also requires every parameter name of every command and of the executor
to be snake_case. CircleCI rejects an argument that a command does not
declare, so a hyphenated name from 0.0.1 fails when the configuration is
compiled.

It prints the SHA-256 of the packed orb and of each script. The script needs
PyYAML, which the job installs. To run it elsewhere:

```console
circleci orb pack src > /tmp/orb.yml
python tests/arguments/packed-commands.py /tmp/orb.yml
```

The job also runs `defaults/compare.py` on the same file; see "Shared
defaults" below.

`packed-commands.py` and the other Python scripts below `tests/` are linted by
one `ruff/check` step of `parameter-tests` with the default rule set. Keep
them free of violations.

## Shared defaults

`defaults/check.sh` and `defaults/format.sh` hold the `PARAM_*` environment
that the published `check` and `format` commands give their script when every
parameter is left at its default: 35 variables for `check` and 20 for
`format`. Every test that runs `src/scripts/check.sh` or
`src/scripts/format.sh` directly sources the matching file and sets only what
it is about: the steps of `parameter-tests` and `format-tests`,
`report/regression.sh` and `arguments/regression.sh`. A parameter that a test
leaves alone therefore has its published default. The `check` mode test of
`format-tests`, for example, does not set `mode`.

`packed-command-tests` runs `defaults/compare.py` on the orb packed from the
same commit. For each command it renders the environment of the command's
step with every default filled in, and requires the file to hold exactly
those variables with exactly those values. A parameter that is added,
removed or renamed, or a default that is changed, in `src/commands` or in the
file alone fails the job, and the message names the variable and both
values. Every line of the files must be `export PARAM_<NAME>='<value>'`, so
the script reads the same values as Bash.

`defaults/compare.py` cannot see a default that was changed the same way on
both sides. The tests see such a change by what it does:

- `command-tests` runs `ruff/check` on `tests/violations` with every
  parameter at its default apart from `targets`, `output_file` and
  `exit_zero`. `Verify the default check against the shared defaults`
  requires the default rule set (`F401`, `F821` and `I001`, three
  violations in all) in Ruff's default `full` output format, and the same
  report from `check.sh` with `defaults/check.sh`. The step after it
  requires the fixtures to be unchanged, so the defaults must not have fixed
  anything. The two reports are stored as the artifacts
  `reports/defaults/orb.txt` and `reports/defaults/script.txt`.
- The steps of `parameter-tests` and `format-tests` that leave `fix` or
  `mode` at its default expect the result of that default.

A default whose change alters none of these results, such as `cache_dir`, is
covered by `defaults/compare.py` alone. To run it elsewhere:

```console
circleci orb pack src > /tmp/orb.yml
python tests/defaults/compare.py /tmp/orb.yml
```

## Execution environment

Every job that runs Ruff records where it ran: `command-tests`,
`parameter-tests`, `format-tests`, `install-tests`, `executor-image-test`,
`resource-class-test`, `check-parameter-tests` and `format-parameter-tests`. The `record-environment` command runs
`environment/record.py` after `ruff/install`, prints the record and stores it
as the artifact `environment/<job>.json`. It holds:

- the commit (`CIRCLE_SHA1`), the job, its number and URL, the workflow and
  the pipeline;
- the Python version, `PYTHON_VERSION` as the `cimg/python` images set it,
  and the operating system. The `Spin up environment` step of the job,
  behind the job URL, names the image that was started;
- the output of `ruff --version` and the path of Ruff. The step fails unless
  it is `ruff 0.16.2`, `ruff_version` of `.circleci/test-deploy.yml`;
- the CPU and memory limits of the container, read from its cgroup
  (`cpu.max` and `memory.max` on cgroup v2), and the CPU count and memory of
  the host, which a resource class does not change.

Only the `CIRCLE_*` variables listed in `record.py` and `PYTHON_VERSION` are
read from the environment, so nothing else, a secret included, reaches the
record. The commit and the job URL in the record tie the job's results and
artifacts to the commit it tested.

## Executor tests

`ruff/default` takes `image` and `resource_class`. Three jobs run on it and
pass their environment record to `executor-comparison` through the
workspace:

| Job | `image` | `resource_class` |
| --- | ------- | ---------------- |
| `command-tests` | default, `cimg/python:3.14` | default, `small` |
| `executor-image-test` | `cimg/python:3.13` | default |
| `resource-class-test` | default | `medium` |

In all three jobs both values reach the executor as its parameters, not as
an image or a resource class written into the job. `install-tests` names its
image directly because it tests `ruff/install` on an image the user chose,
not the executor.

`executor-comparison` runs `environment/compare.py` with the orb packed from
the same commit, `.circleci/test-deploy.yml` and the three records:

1. The packed `default` executor must start one image, given by `image`,
   with the resource class given by `resource_class`. The defaults of both
   are read from the packed orb.
2. What a job asked for is those defaults with the job's own arguments on
   top, as CircleCI processes the configuration. The records must cover the
   defaults, a non-default image and a non-default resource class, and come
   from one commit and one pipeline, those of the comparing job. The
   workflow may differ, because rerunning failed jobs starts a new one.
3. The Python version a job recorded must start with the version in the tag
   of its `cimg/python` image, so a job that ran another image fails.
4. The CPU and memory limits must be equal within a resource class and
   larger for a larger one, so `resource-class-test` must get more than the
   two jobs on `small`. Every record must show a CPU limit. Memory is
   compared when every record shows a limit, and the output says so when
   none does. The limits are not compared with fixed numbers, because they
   depend on the CircleCI plan.

The job prints what each job asked for and what it recorded, and stores the
same as the artifact `executor-comparison/executors.json`. To run the
comparison elsewhere, put the three records in one directory:

```console
python tests/environment/compare.py /tmp/orb.yml .circleci/test-deploy.yml RECORDS /tmp/out
```

## ruff/check parameters

`arguments/check-parameters.md` is the table of where each public parameter
of `ruff/check` is tested: its default, the values that are tried and what
reaches Ruff for each, the checks with Ruff 0.16.2, and the regression cases
that cover it. It ends with the full list of the cases that
`report/regression.sh` and `arguments/regression.sh check` run.

The `check-parameter-tests` job runs `arguments/check-parameters.py` on the
orb packed from the same commit. The script runs the packed `check` step the
way CircleCI does: it fills every `<<parameters.NAME>>` of the step's
environment with the value of a case or with the default, and runs the
step's script with bash. A case names public parameters only, so a parameter
that does not reach the script fails its case.

- 77 argument cases run with `arguments/record-ruff.sh` as Ruff, at least one
  per parameter with a value other than its default and one per value of
  each enum. Each compares the options before `--` as a whole, the paths
  after it in their order, and the order where it matters: `extra_args`
  after every other option, and the `--config` values as `config_file`, then
  the `config_overrides` lines, then `line_length`. Of several overrides of
  one setting, Ruff 0.16.2 applies the first, as `ruff check --show-settings`
  shows, so a `line-length` in `config_overrides` takes precedence over
  `line_length`; no Ruff case checks that. The `Command:` line must show the
  arguments received, and Ruff must be started twice, `ruff --version`
  first. One more case checks that `fix_only` under `fix: never` is refused
  before Ruff starts.
- 13 Ruff cases run Ruff 0.16.2 on files they write to a temporary directory
  with an empty `ruff.toml`, or with the setting the case needs, and require
  an exact exit status, output lines and file contents. They cover `diff`,
  `output_format: json`, `extensions`, `fixable`, `unfixable`, `fix: safe`
  against `fix: unsafe`, `ignore_noqa`, `show_fixes`, `preview`,
  `force_exclude`, `respect_gitignore`, `cache_dir` and `excluded_paths`, and
  the exit statuses: 0 for a clean file, 1 for a violation, 2 for a missing
  `config_file`, 1 for refused input without starting Ruff, and 0 for an
  allowed fix. `respect_gitignore` needs `git`, because Ruff applies a
  `.gitignore` only inside a Git repository.
- It fails when a parameter has no case with another value than its default,
  an enum value has no case, or the table has no row, or an extra row, for a
  parameter.

It prints every case and stores the details, with the arguments received and
the output of every run, as the artifact `check-parameters/results.json`.

`parameter-tests` runs some of these parameters through the `ruff/check`
command itself: `output_format: json`, whose report must parse and hold each
finding of `violations/`; `diff: true` with `exit_zero: true`, after which
the fixture must be unchanged; `excluded_paths`, `force_exclude: enabled` and
`cache_dir`. It also keeps the logs of the two regression scripts, stores
them as the artifacts `regression-logs/*.log`, and runs
`arguments/check-parameters.py --regression-log`, which fails unless the
cases that ran are exactly the ones `check-parameters.md` lists. The
read-only report case of `report/regression.sh` is skipped as root, so run
that comparison as an ordinary user, as CircleCI does.

To run the script elsewhere, with Ruff 0.16.2 and PyYAML installed:

```console
circleci orb pack src > /tmp/orb.yml
python tests/arguments/check-parameters.py /tmp/orb.yml
```

## ruff/format parameters

`arguments/format-parameters.md` is the same kind of table for `ruff/format`.
It also sets out what each mode prints and which setting wins over which
with Ruff 0.16.2, and it ends with the full list of the cases that
`arguments/regression.sh format` runs.

The `format-parameter-tests` job runs `arguments/format-parameters.py` on the
orb packed from the same commit. Like `check-parameters.py`, it runs the
packed `format` step the way CircleCI does.

- 58 argument cases run with `arguments/record-ruff.sh` as Ruff, at least one
  per parameter with a value other than its default and one per value of
  each enum. Each compares the options before `--` as a whole, the paths
  after it in their order, `extra_args` after every other option, and the
  `--config` values as `config_file`, then the `config_overrides` lines.
  `line_length` is passed as `--line-length`, which Ruff 0.16.2 applies over
  a `line-length` from `config_overrides` in either order, unlike
  `ruff/check`. The `Command:` line must show the arguments received, and
  Ruff must be started twice, `ruff --version` first. Two more cases check
  that `--` and `@args` in `extra_args` are refused before Ruff starts.
- 19 Ruff cases run Ruff 0.16.2 through `arguments/record-real-ruff.sh`,
  which records the arguments of each run and then runs the real Ruff. They
  write their files to a temporary directory with an empty `ruff.toml`, or
  with the setting the case needs. Each run requires an exact exit status,
  and the case checks the arguments received, standard output and standard
  error separately, and the files before and after. They cover
  `line_length`, `config_file`, `config_overrides`, `isolated`,
  `excluded_paths`, `extend_excluded_paths`, `extensions`, `force_exclude`,
  `respect_gitignore`, `target_version`, `preview`, `no_cache`, `cache_dir`,
  `output_format`, `verbosity`, `extra_args`, `color`,
  `exit_non_zero_on_format` and the three modes, settings that Ruff cannot
  use, and which setting wins over which. `respect_gitignore` needs `git`.
- It fails when a parameter has no case with another value than its default,
  an enum value has no case, or the table has no row, or an extra row, for a
  parameter.

It prints every case and stores the details, with the arguments received and
the output of every run, as the artifact `format-parameters/results.json`.

Since Ruff 0.16, `check` mode shows the change as well, in its default `full`
report, so the code of the change appears in both modes and does not tell
them apart. `ruff-modes` requires, for
each mode, the option Ruff received and the form of the output: a diagnostic
per file and the summary on standard output for `check`, a unified diff on
standard output and the summary on standard error for `diff`. `format-tests`
checks the same forms on the fixture: `Verify check mode fails on an
unformatted file` and `Verify diff mode fails without modifying the file` run
`src/scripts/format.sh` and look at standard output and standard error
separately. To confirm that both catch a `diff` mode that runs as `check`
mode, make the `diff` branch of `src/scripts/format.sh` pass `--check` on a
throwaway branch: the diff mode step and `ruff-modes` fail. Do not merge the
change.

`format-tests` also runs some of these parameters through the `ruff/format`
command itself, each on an input that would be reformatted unless the value
reaches Ruff: `config_file`, `config_overrides`, `isolated` together with
`config_overrides`, `excluded_paths`, `force_exclude: enabled`,
`target_version: py38` and `preview: enabled`. `cache_dir` and `no_cache`
are followed by a look at the cache. The inputs that are not fixtures are
written to `/tmp`. The job also keeps the log of
`arguments/regression.sh format`, stores it as the artifact
`regression-logs/arguments-format.log`, and runs
`arguments/format-parameters.py --regression-log`, which fails unless the
cases that ran are exactly the ones `format-parameters.md` lists.

To run the script elsewhere, with Ruff 0.16.2, PyYAML and `git` installed:

```console
circleci orb pack src > /tmp/orb.yml
python tests/arguments/format-parameters.py /tmp/orb.yml
```
