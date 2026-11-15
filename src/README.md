# Orb Source

This directory holds the Orb in unpacked form. `orb-tools/pack` packs it into a single `orb.yml` with `circleci orb pack`, the integration tests run that packed Orb, and a release tag publishes it. "Development" in the [README](../README.md#development) describes the pipeline and the release steps.

| Path | Content |
| ---- | ------- |
| `@orb.yml` | The Orb's `version`, `description` and `display.source_url` |
| `commands/` | `install`, `check` and `format`: their parameters, descriptions and steps, as the Orb Registry shows them |
| `scripts/` | `install.sh`, `check.sh` and `format.sh`, which the commands include with `<<include(scripts/NAME.sh)>>` |
| `executors/` | `default`, the Python executor |
| `examples/` | The usage examples the Orb Registry shows |

## Commands and scripts

Each command passes its parameters to its script as `PARAM_*` environment variables, for example `output_file` as `PARAM_OUTPUT_FILE`. Parameter names use underscores, which the review check RC010 requires. The variable names did not change with the rename in 1.0.0.

When a parameter or a default changes, change these as well:

* `tests/defaults/check.sh` or `tests/defaults/format.sh`. The `packed-command-tests` job compares them with the packed commands.
* The parameter tables in the README.
* `tests/arguments/check-parameters.md` or `tests/arguments/format-parameters.md`, which list where each parameter is tested.

## Usage examples

Every file in `examples/` references the Orb as `orbss/ruff@1.0.0`. The review check RC011 requires the major version of the release tag there, and it only runs in the pipeline of a `vX.Y.Z` tag. The examples are meant for use once that version is published. Before that, try one with the Orb packed from the same commit; "Development" in the README describes both.
