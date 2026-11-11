"""Static check of the packed 'check' and 'format' commands.

Usage:

    python3 tests/arguments/packed-commands.py PACKED_ORB [REPOSITORY]

PACKED_ORB is the orb.yml that 'circleci orb pack src' writes. REPOSITORY
defaults to the repository this file belongs to. PyYAML is required.

tests/arguments/regression.sh proves that src/scripts/check.sh and
src/scripts/format.sh refuse certain input before they start Ruff. That only
says something about the published commands if the packed commands run those
same scripts, hand them every parameter, and start nothing before them. This
script checks exactly that, for both commands:

1. The command has a single step: a 'run' without 'when', 'shell',
   'background' or 'working_directory'. There is no earlier step that could
   start Ruff, such as a separate 'ruff --version', and no later one that
   could run after a refusal.
2. The step's command is the script in src/scripts, character for character
   apart from trailing whitespace and the escaping that packing applies:
   'circleci orb pack' writes every '<<' of an included script as '\\<<', so
   that CircleCI does not read it as the start of a parameter, and CircleCI
   turns it back when it runs the step. Nothing wraps the script, so its exit
   status is the step's.
3. Every parameter of the command is handed to the script as PARAM_<NAME>,
   and the script reads no PARAM_ variable that the step does not set.
4. Inside the script, the block that refuses input ends before the first line
   that starts Ruff, and no line before that point writes a file. 'ruff
   --version' is the first start of Ruff.

It prints what it found, with the SHA-256 of each script, and exits 1 if any
check fails.
"""

import difflib
import hashlib
import pathlib
import re
import sys

import yaml

FORBIDDEN_STEP_KEYS = ("when", "shell", "background", "working_directory")
FILE_COMMANDS = re.compile(r"\b(mkdir|rm|rmdir|cp|mv|tee|touch|dd|install)\b")
REFUSALS = {
    "check": [
        "'fix-only' rewrites files, so it needs 'fix' set to",
        "'extra-args' contains items that are not accepted",
    ],
    "format": [
        "Unknown mode '${PARAM_MODE}'.",
        "'extra-args' contains items that are not accepted",
    ],
}


def normalise(text):
    """Line endings and trailing whitespace are all that packing may change."""
    return text.replace("\r\n", "\n").rstrip()


def unescape(text):
    """Undo the escaping 'circleci orb pack' applies to an included script."""
    return text.replace("\\<<", "<<")


def parameter_of(value):
    """Return NAME for a value that is exactly '<<parameters.NAME>>'."""
    match = re.fullmatch(r"<<\s*parameters\.([A-Za-z0-9_-]+)\s*>>", str(value))
    return match.group(1) if match else None


def check_step(name, command, failures):
    """Checks 1 to 3. Returns the packed script text, or None."""
    steps = command.get("steps") or []

    if len(steps) != 1:
        failures.append(f"{name}: expected a single step, found {len(steps)}")
        return None

    step = steps[0]

    if not isinstance(step, dict) or list(step) != ["run"]:
        failures.append(f"{name}: the step is not a 'run' step")
        return None

    run = step["run"]

    if not isinstance(run, dict):
        failures.append(f"{name}: the 'run' step has no environment")
        return None

    for key in FORBIDDEN_STEP_KEYS:
        if key in run:
            failures.append(f"{name}: the 'run' step sets '{key}'")

    print(f"  step: single 'run' step named '{run.get('name')}'")

    environment = run.get("environment") or {}
    parameters = set(command.get("parameters") or {})
    handed_over = set()

    for variable, value in environment.items():
        parameter = parameter_of(value)

        if parameter is None:
            failures.append(f"{name}: {variable} is not set from a parameter")
            continue

        expected = "PARAM_" + parameter.upper().replace("-", "_")

        if variable != expected:
            failures.append(
                f"{name}: {variable} is set from '{parameter}', "
                f"which belongs in {expected}"
            )

        handed_over.add(parameter)

    for parameter in sorted(parameters - handed_over):
        failures.append(f"{name}: parameter '{parameter}' is not handed over")

    for parameter in sorted(handed_over - parameters):
        failures.append(f"{name}: '{parameter}' is not a parameter")

    script = unescape(str(run.get("command", "")))
    read = set(re.findall(r"\$\{(PARAM_[A-Z0-9_]+)", script))

    for variable in sorted(read - set(environment)):
        failures.append(f"{name}: the script reads {variable}, which is not set")

    for variable in sorted(set(environment) - read):
        failures.append(f"{name}: {variable} is set but the script ignores it")

    print(
        f"  environment: {len(environment)} PARAM_ variables for "
        f"{len(parameters)} parameters"
    )

    return script


def check_identity(name, script, repository, failures):
    """Check 2: the packed command is the script the tests run."""
    source = repository / "src" / "scripts" / f"{name}.sh"
    expected = normalise(source.read_text(encoding="utf-8"))
    actual = normalise(script)
    digest = hashlib.sha256(expected.encode("utf-8")).hexdigest()

    if actual != expected:
        failures.append(f"{name}: the packed command differs from {source}")
        difference = difflib.unified_diff(
            expected.split("\n"),
            actual.split("\n"),
            f"src/scripts/{name}.sh",
            f"packed command '{name}'",
            lineterm="",
            n=0,
        )
        for line in list(difference)[:40]:
            print(f"    {line!r}")
        return

    print(f"  script: identical to src/scripts/{name}.sh (SHA-256 {digest})")


def check_order(name, script, failures):
    """Check 4: every refusal comes before the first start of Ruff."""
    lines = normalise(script).split("\n")
    code = ["" if line.lstrip().startswith("#") else line for line in lines]

    if "set -eo pipefail" not in code[:5]:
        failures.append(f"{name}: the script does not start with 'set -eo pipefail'")

    starts = [
        index for index, line in enumerate(code) if re.match(r"\s*ruff(\s|$)", line)
    ]

    if not starts or code[starts[0]].strip() != "ruff --version":
        failures.append(f"{name}: 'ruff --version' is not the first start of Ruff")
        return

    first = starts[0]

    if len(starts) != 2:
        failures.append(
            f"{name}: expected Ruff to be started on two lines, found {len(starts)}"
        )

    for text in REFUSALS[name]:
        found = [index for index, line in enumerate(code) if text in line]

        if len(found) != 1:
            failures.append(f'{name}: expected one refusal with "{text}"')
            continue

        # The refusal block is the 'if' or 'case' around the message. It must
        # reach its 'exit 1' before Ruff is started.
        exits = [
            index for index in range(found[0], first) if code[index].strip() == "exit 1"
        ]

        if not exits:
            failures.append(
                f'{name}: the refusal "{text}" does not exit before '
                f"'ruff --version' on line {first + 1}"
            )
            continue

        print(
            f'  refusal: "{text}" on line {found[0] + 1}, '
            f"'exit 1' on line {exits[0] + 1}"
        )

    for index in range(first):
        line = code[index].replace(">&2", "")

        if ">" in line.replace("< <(", "") or FILE_COMMANDS.search(line):
            failures.append(
                f"{name}: line {index + 1} may write a file before the "
                f"input checks have passed: {lines[index].strip()}"
            )

    print(
        f"  order: Ruff is first started on line {first + 1} "
        f"('ruff --version') and nothing before it writes a file"
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
    packed = yaml.safe_load(packed_bytes)
    failures = []

    print(f"Packed orb: {packed_path}")
    print(f"SHA-256: {hashlib.sha256(packed_bytes).hexdigest()}")

    commands = packed.get("commands") or {}

    for name in ("check", "format"):
        print(f"Command '{name}':")

        if name not in commands:
            failures.append(f"{name}: the packed orb has no such command")
            continue

        script = check_step(name, commands[name], failures)

        if script is None:
            continue

        check_identity(name, script, repository, failures)
        check_order(name, script, failures)

    # A leftover step that only prints the version would start Ruff before
    # the input checks of whatever command it sits in.
    for name, command in commands.items():
        for step in command.get("steps") or []:
            run = step.get("run") if isinstance(step, dict) else None
            text = run.get("command") if isinstance(run, dict) else run

            if (
                isinstance(text, str)
                and normalise(text).split("\n")[-1].strip() == "ruff --version"
            ):
                failures.append(f"{name}: a step does nothing but print the version")

    if failures:
        print()
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("The packed commands run the tested scripts, and check their input first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
