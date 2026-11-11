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
  `line-length: "40"` with `extend-selected-rules: E501`. The `ruff/check`
  `line-length` test and the report-replacement test both depend on that
  count. It is also not formatted at `line-length: "40"`, which the format
  `line-length` test depends on. Keep both in mind when editing the fixture.
- `line-length/formatted_at_40.py` reports no violations under the default
  rule set. It is formatted at `line-length: "40"` but not at Ruff's default
  of 88, the reverse of `clean/compliant.py`. The format `line-length` test
  uses the two together, so do not reformat it at the default length.
- `violations/unused_import.py` reports `F401` and nothing else. It backs the
  `output-file`, `tee`, `ignored-rules` and `exit-zero` tests, and it must stay
  reported under `selected-rules: F`.
- `violations/unsorted_imports.py` reports `I001` and nothing else. It must
  stay silent under `selected-rules: F` and under the pre-0.16.0 default set
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

## Format line-length test

`format-tests` exercises `line-length` through both `src/scripts/format.sh`
and the `ruff/format` command. With Ruff 0.16.2, the two fixtures above give
opposite answers at the default line length of 88 and at `40`. This detects
a dropped `line-length: "40"` value that falls back to 88, or a supplied
value that is forced to 88.

These cases do not detect every incorrect line length. For example, replacing
40 with 41 produces the same asserted results for these fixtures. The tests
check the expected formatting behavior for the selected cases; proving that
the exact requested value reaches Ruff also requires checking the arguments
passed to Ruff.

- `Verify line-length reaches the formatter through format.sh` runs
  `src/scripts/format.sh` on each fixture with and without
  `line-length: "40"`. It asserts the exact exit status and a summary line,
  and that the fixture is unchanged afterwards. A `diff` case also asserts a
  complete added line from the expected diff at 40. This distinguishes that
  case from check-mode diagnostics, but does not uniquely identify the line
  length used.
- The `ruff/format` step after it passes `line-length: "40"` through the Orb
  command, so the mapping in `src/commands/format.yml` is covered as well.
- `Record the fixtures` takes a SHA-256 snapshot of `tests/` after checkout.
  `Verify the fixtures are unchanged` compares against it at the end of the
  job.

To confirm that the test still catches a dropped value, break it on a
throwaway branch. Removing the `--line-length` handling from
`src/scripts/format.sh` fails both line-length steps. Removing
`PARAM_LINE_LENGTH` from the environment in `src/commands/format.yml` fails
the `ruff/format` step. Do not merge either change.

## Report regression

`report/regression.sh` checks how `src/scripts/check.sh` handles `output-file`
and `tee`. It calls the script directly, because several cases must fail. The
`parameter-tests` job runs it after `write-check-defaults` and reuses the
`PARAM_*` defaults that command writes to `/tmp/check-defaults.sh`.

- Most cases seed the report with the line `ORB-TEST-STALE-REPORT-MARKER`
  first. That marker must never appear in the log or in a report afterwards.
- The cases rely on `clean/compliant.py` passing and on
  `violations/unused_import.py` reporting a single `F401`.
- The cases that run the real Ruff keep their reports under
  `reports/report-regression`, so they are stored as artifacts with the other
  reports. See "Reports stored as artifacts" below.
- `report/mock-ruff.sh` stands in for Ruff where a failure has to be injected,
  such as a report that cannot be read back. A temporary copy named `ruff` is
  put first on `PATH`. It records every call, so a case can assert that Ruff
  was not started.
- The read-only report case is skipped when the script runs as root, because
  root can write to a read-only file. The CircleCI convenience images run as
  an ordinary user, so the case runs in CI.

To run the cases outside CircleCI, install Ruff 0.16.2 and write the defaults
with the shell commands of `write-check-defaults` in
`.circleci/test-deploy.yml`. Then run `bash tests/report/regression.sh`. Set
`CHECK_DEFAULTS` when the defaults are not in `/tmp/check-defaults.sh`.

## Reports stored as artifacts

The `parameter-tests` job writes its reports under `reports/`. Its last step,
`store_artifacts`, stores that whole directory, so every report has been
written by then. The step before it, `Verify the reports to be stored`, checks
the directory first:

- The files must match the list in that step one to one.
- The reports listed as empty must be empty, and all others must have content.
- No report may carry the stale-report marker of `report/regression.sh`.

The step then prints the commit, the job URL, and the size and SHA-256 of every
report.

`store_artifacts` runs even after an earlier step has failed, so a failed job
can still store reports that failed the check or never reached it. Treat the
stored reports as verified only when `Verify the reports to be stored` and the
whole job have both succeeded.

Change the list in that step and the table below together whenever a step
adds, renames or removes a report.

| Report | Written by | Content |
| ------ | ---------- | ------- |
| `reports/line-length.txt` | `ruff/check` with `line-length: "40"`, run twice into the same file | Four `E501` lines |
| `reports/select.txt` | `ruff/check` with `selected-rules: F` | `F401` and `F821`, no `I001` |
| `reports/legacy-defaults.txt` | `ruff/check` with `selected-rules: E4,E7,E9,F` | `F401` and `F821`, no `I001` |
| `reports/config-overrides.txt` | `ruff/check` with `config-overrides` | Four `E501` lines |
| `reports/no-tee.txt` | `check.sh` with `tee: false` | `F401` |
| `reports/tee.txt` | `check.sh` with `tee: true` | `F401` |
| `reports/isolated-line-length.txt` | `ruff/check` with `isolated: true` and `line-length: "40"` | Four `E501` lines |
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

The six empty reports are empty by design. `check.sh` empties `output-file`
before Ruff runs, and in these cases Ruff writes nothing. CircleCI's upload
may skip an empty file and log `SKIPPED, file is empty`, so an empty report
can be missing from the Artifacts tab even though the job wrote it.

To compare a run with the table, use the manifest that `Verify the reports to
be stored` prints and the log of the `store_artifacts` step. Every report with
content must appear as an artifact. Every empty report must appear either as
an artifact or as skipped. Anything else is a mismatch.
