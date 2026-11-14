"""Compare the shared PARAM_* defaults of the tests with the packed orb.

Usage:

    python3 tests/defaults/compare.py PACKED_ORB [REPOSITORY]

PACKED_ORB is the orb.yml that 'circleci orb pack src' writes. REPOSITORY
defaults to the repository this file belongs to. PyYAML is required.

tests/defaults/check.sh and tests/defaults/format.sh hold the environment
that the published 'check' and 'format' commands give their script when every
parameter is left at its default. The tests that run src/scripts/check.sh and
src/scripts/format.sh directly source them and set only the parameters they
are about, so a wrong default there would make those tests run a
configuration that no user of the Orb gets.

For each command this script renders that environment from the packed orb.
It takes every variable of the command's 'run' step and replaces each
'<<parameters.NAME>>' with the default of NAME, written the way CircleCI puts
it into the environment: 'true' or 'false' for a boolean, the value itself
otherwise. The file must then hold exactly those variables with exactly those
values. Every variable that is missing, extra or different is reported, so a
change on either side alone fails. A parameter without a default cannot be
rendered and fails as well.

The format of the files is checked too. Apart from comments and empty lines,
every line must be export PARAM_<NAME>='<value>', with no quote inside the
value, and each name may appear once. Bash and this script then read the same
values.

Agreement is all this proves. A default changed on both sides in the same way
passes here. The tests that run the published commands and compare their
results with the expected ones are what catch that.

It prints the SHA-256 of the packed orb and of each file, and exits 1 if any
check fails.
"""

import hashlib
import pathlib
import re
import sys

import yaml

COMMANDS = ("check", "format")
LINE = re.compile(r"export (PARAM_[A-Z0-9_]+)='([^']*)'")
PARAMETER = re.compile(r"<<\s*parameters\.([A-Za-z0-9_-]+)\s*>>")


def render(value):
    """Write a parameter value the way CircleCI puts it into the environment."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def expected_environment(name, command, failures):
    """The environment of the command's step with every default filled in.

    Returns the rendered variables and the names of all variables the step
    sets, or None when the step cannot be found. A variable whose parameter
    has no default is reported and left out of the rendered ones.
    """
    runs = [
        step["run"]
        for step in command.get("steps") or []
        if isinstance(step, dict) and isinstance(step.get("run"), dict)
    ]

    if len(runs) != 1:
        failures.append(f"{name}: expected one 'run' step, found {len(runs)}")
        return None, None

    environment = runs[0].get("environment") or {}
    parameters = command.get("parameters") or {}
    expected = {}

    if not environment:
        failures.append(f"{name}: the step sets no environment")

    for variable, template in environment.items():
        unresolved = []

        def default_of(match, unresolved=unresolved):
            parameter = parameters.get(match.group(1))

            if not isinstance(parameter, dict) or "default" not in parameter:
                unresolved.append(match.group(1))
                return ""

            return render(parameter["default"])

        value = PARAMETER.sub(default_of, str(template))

        if unresolved:
            failures.append(
                f"{name}: {variable} is set from '{', '.join(unresolved)}', "
                "which has no default, so the file cannot hold it"
            )
            continue

        expected[variable] = value

    return expected, set(environment)


def read_defaults(path, failures):
    """The PARAM_* assignments of a defaults file, checked line by line."""
    values = {}

    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        match = LINE.fullmatch(line)

        if not match:
            failures.append(
                f"{path.name}: line {number} is not export PARAM_<NAME>='<value>': "
                f"{line!r}"
            )
            continue

        variable, value = match.groups()

        if variable in values:
            failures.append(f"{path.name}: {variable} is set again on line {number}")

        values[variable] = value

    return values


def compare(name, expected, variables, actual, path, failures):
    """Report every difference between the rendered and the file's values."""
    for variable in sorted(variables | set(actual)):
        if variable in variables and variable not in expected:
            # Reported by expected_environment already.
            continue

        if variable not in actual:
            failures.append(
                f"{name}: {variable} is missing from {path.name}; "
                f"the packed command's default is '{expected[variable]}'"
            )
        elif variable not in expected:
            failures.append(
                f"{name}: {variable} is set in {path.name}, "
                "but the packed command does not set it"
            )
        elif actual[variable] != expected[variable]:
            failures.append(
                f"{name}: {variable} is '{actual[variable]}' in {path.name}, "
                f"but the packed command's default is '{expected[variable]}'"
            )


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2

    packed_path = pathlib.Path(sys.argv[1])
    repository = (
        pathlib.Path(sys.argv[2])
        if len(sys.argv) == 3
        else pathlib.Path(__file__).resolve().parents[2]
    )
    packed_bytes = packed_path.read_bytes()
    commands = (yaml.safe_load(packed_bytes) or {}).get("commands") or {}
    failures = []

    print(f"Packed orb: {packed_path}")
    print(f"SHA-256: {hashlib.sha256(packed_bytes).hexdigest()}")

    for name in COMMANDS:
        path = repository / "tests" / "defaults" / f"{name}.sh"
        print(f"Command '{name}' and tests/defaults/{name}.sh:")

        if name not in commands:
            failures.append(f"{name}: the packed orb has no such command")
            continue

        if not path.is_file():
            failures.append(f"{name}: {path} does not exist")
            continue

        print(f"  SHA-256 of the file: {hashlib.sha256(path.read_bytes()).hexdigest()}")
        before = len(failures)
        expected, variables = expected_environment(name, commands[name], failures)
        actual = read_defaults(path, failures)

        if expected is None:
            continue

        compare(name, expected, variables, actual, path, failures)

        if len(failures) == before:
            print(f"  all {len(expected)} PARAM_ variables match the packed defaults")

    if failures:
        print()
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("The shared defaults match the defaults of the packed commands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
