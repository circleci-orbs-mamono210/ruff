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
  `line-length: "40"` with `extend-selected-rules: E501`. The `line-length`
  test and the report-replacement test both depend on that count, so keep it
  in mind when editing the fixture.
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
  reports.
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
