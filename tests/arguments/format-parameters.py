"""Every public parameter of ruff/format, from the packed command to Ruff.

Usage:

    python3 tests/arguments/format-parameters.py PACKED_ORB [--report DIR]
    python3 tests/arguments/format-parameters.py --regression-log SCRIPT LOG ...

PACKED_ORB is the orb.yml that 'circleci orb pack src' writes, and PyYAML is
required to read it. The cases run the packed 'format' command the way
CircleCI runs its step: every '<<parameters.NAME>>' in the step's environment
is replaced with the value the case gives, or with the default, and the
step's script is run with bash. A case names public parameters only, so a
parameter that does not reach the script, or reaches it under another
variable, fails its case.

Argument cases put tests/arguments/record-ruff.sh first on PATH as 'ruff' and
compare what it receives with what the case expects:

- the options before '--' as a whole, in any order. An option and its value
  form one item, so '--line-length 40' and '--line-length 88' differ;
- the paths after '--', in their order;
- the order where it matters. 'extra_args' comes after every option the
  command builds, and the '--config' values come as 'config_file', then the
  'config_overrides' lines in their order. Of several overrides of one
  setting, Ruff 0.16.2 applies the first;
- the 'Command:' line, which must show exactly the arguments received, and
  that Ruff was started twice, 'ruff --version' first.

Every parameter needs an argument case with a value other than its default,
every value of an enum needs a case of its own, and
tests/arguments/format-parameters.md needs one row per parameter.

Ruff cases run Ruff 0.16.2 in a temporary directory that holds an empty
ruff.toml, or the configuration the case writes, so no other configuration
applies. tests/arguments/record-real-ruff.sh stands first on PATH as 'ruff':
it records the arguments of every run and then runs the real Ruff. Each run
requires an exact exit status, and the case checks the arguments Ruff
received, what Ruff printed on standard output and on standard error,
separately, and the file contents before and after. They cover the
parameters whose effect is checked with the real Ruff, as
tests/arguments/format-parameters.md lists them.

With --regression-log, the script instead compares the case names that a run
of a regression script printed with the names that
tests/arguments/format-parameters.md lists for that script, both ways.

It prints every case and exits 1 if any check fails. With --report, the
results are also written to DIR/results.json.
"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

HERE = pathlib.Path(__file__).resolve().parent
TABLE = HERE / "format-parameters.md"
RECORDER = HERE / "record-ruff.sh"
REAL_RECORDER = HERE / "record-real-ruff.sh"
RUFF_VERSION = "0.16.2"

# Ruff options that take the next argument as their value.
VALUE_OPTIONS = {
    "--cache-dir",
    "--color",
    "--config",
    "--exclude",
    "--extend-exclude",
    "--extension",
    "--line-length",
    "--output-format",
    "--target-version",
}

# What 'mode: check', the default, passes.
CHECK = ["--check"]

OUTPUT_FORMATS = (
    "concise",
    "full",
    "json",
    "json-lines",
    "junit",
    "grouped",
    "github",
    "gitlab",
    "pylint",
    "rdjson",
    "azure",
    "sarif",
)

TARGET_VERSIONS = (
    "py37",
    "py38",
    "py39",
    "py310",
    "py311",
    "py312",
    "py313",
    "py314",
    "py315",
)


def expect(*tokens):
    """The arguments of the defaults plus TOKENS."""
    return [*CHECK, *tokens]


def case(name, parameters, options, paths=(".",)):
    return {
        "name": name,
        "parameters": parameters,
        "options": list(options),
        "paths": list(paths),
    }


ARGUMENT_CASES = [
    case("defaults", {}, expect()),
    case(
        "cache_dir",
        {"cache_dir": "build/ruff cache"},
        expect("--cache-dir", "build/ruff cache"),
    ),
    case("color=auto", {"color": "auto"}, expect()),
    case("color=always", {"color": "always"}, expect("--color", "always")),
    case("color=never", {"color": "never"}, expect("--color", "never")),
    case(
        "config_file",
        {"config_file": "configs/ruff.toml"},
        expect("--config", "configs/ruff.toml"),
    ),
    case(
        "config_overrides",
        {"config_overrides": 'format.quote-style = "single"\n\nline-length = 100\n'},
        expect(
            "--config",
            'format.quote-style = "single"',
            "--config",
            "line-length = 100",
        ),
    ),
    case("config_overrides=blank", {"config_overrides": " \n\t\n"}, expect()),
    case(
        "excluded_paths",
        {"excluded_paths": "build/*,docs/conf.py"},
        expect("--exclude", "build/*,docs/conf.py"),
    ),
    case(
        "exit_non_zero_on_format=true",
        {"exit_non_zero_on_format": True, "mode": "write"},
        ["--exit-non-zero-on-format"],
    ),
    case(
        "extend_excluded_paths",
        {"extend_excluded_paths": "generated/*"},
        expect("--extend-exclude", "generated/*"),
    ),
    case(
        "extensions",
        {"extensions": "pya:python\nipy:ipynb"},
        expect("--extension", "pya:python", "--extension", "ipy:ipynb"),
    ),
    case(
        "extra_args",
        {"extra_args": "--range 1-2\n--show-settings"},
        expect("--range", "1-2", "--show-settings"),
    ),
    case("force_exclude=auto", {"force_exclude": "auto"}, expect()),
    case(
        "force_exclude=enabled",
        {"force_exclude": "enabled"},
        expect("--force-exclude"),
    ),
    case(
        "force_exclude=disabled",
        {"force_exclude": "disabled"},
        expect("--no-force-exclude"),
    ),
    case("isolated=true", {"isolated": True}, expect("--isolated")),
    case("line_length", {"line_length": "100"}, expect("--line-length", "100")),
    case("mode=check", {"mode": "check"}, ["--check"]),
    case("mode=diff", {"mode": "diff"}, ["--diff"]),
    case("mode=write", {"mode": "write"}, []),
    case("no_cache=true", {"no_cache": True}, expect("--no-cache")),
    case("output_format=default", {"output_format": "default"}, expect()),
    *[
        case(
            f"output_format={value}",
            {"output_format": value},
            expect("--output-format", value),
        )
        for value in OUTPUT_FORMATS
    ],
    case("preview=auto", {"preview": "auto"}, expect()),
    case("preview=enabled", {"preview": "enabled"}, expect("--preview")),
    case("preview=disabled", {"preview": "disabled"}, expect("--no-preview")),
    case("respect_gitignore=auto", {"respect_gitignore": "auto"}, expect()),
    case(
        "respect_gitignore=enabled",
        {"respect_gitignore": "enabled"},
        expect("--respect-gitignore"),
    ),
    case(
        "respect_gitignore=disabled",
        {"respect_gitignore": "disabled"},
        expect("--no-respect-gitignore"),
    ),
    case("target_version=default", {"target_version": "default"}, expect()),
    *[
        case(
            f"target_version={value}",
            {"target_version": value},
            expect("--target-version", value),
        )
        for value in TARGET_VERSIONS
    ],
    case(
        "targets",
        {"targets": "src tests\n-x"},
        expect(),
        paths=["src", "tests", "./-x"],
    ),
    case("verbosity=default", {"verbosity": "default"}, expect()),
    case("verbosity=verbose", {"verbosity": "verbose"}, expect("--verbose")),
    case("verbosity=quiet", {"verbosity": "quiet"}, expect("--quiet")),
    case("verbosity=silent", {"verbosity": "silent"}, expect("--silent")),
    # Values are passed as they are: not split, and nothing is evaluated.
    case(
        "values-not-evaluated",
        {
            "cache_dir": "*",
            "config_overrides": 'format.indent-style = "$(id)"',
            "excluded_paths": "$(echo x) y",
            "extend_excluded_paths": "`id`",
        },
        expect(
            "--cache-dir",
            "*",
            "--config",
            'format.indent-style = "$(id)"',
            "--exclude",
            "$(echo x) y",
            "--extend-exclude",
            "`id`",
        ),
    ),
    # Every '--config' in its place, and extra_args after everything else.
    case(
        "config-order-and-extra-args",
        {
            "config_file": "ruff.toml",
            "config_overrides": 'line-length = 50\nformat.quote-style = "single"',
            "extra_args": "--range 1-2",
            "line_length": "40",
            "mode": "diff",
            "output_format": "concise",
        },
        [
            "--diff",
            "--config",
            "ruff.toml",
            "--config",
            "line-length = 50",
            "--config",
            'format.quote-style = "single"',
            "--line-length",
            "40",
            "--output-format",
            "concise",
            "--range",
            "1-2",
        ],
    ),
]

# The command refuses these before Ruff is started, in every mode.
REFUSED_INTRO = (
    "'extra_args' contains items that are not accepted, so Ruff was not run:"
)
REFUSED_CASES = [
    {
        "name": "extra_args=--",
        "parameters": {"extra_args": "--", "mode": "write"},
        "message": "  '--': the paths come from 'targets', and '--' is added for them",
    },
    {
        "name": "extra_args=@args",
        "parameters": {"extra_args": "@args", "mode": "diff"},
        "message": "  '@args': Ruff would read an item that starts with '@' "
        "as an argument file",
    },
]


# ---------------------------------------------------------------------------
# The packed command
# ---------------------------------------------------------------------------


class Command:
    """The packed 'format' command: its parameters, environment and script."""

    def __init__(self, packed_path):
        import yaml

        orb = yaml.safe_load(pathlib.Path(packed_path).read_text(encoding="utf-8"))
        command = (orb.get("commands") or {}).get("format")

        if not isinstance(command, dict):
            raise SystemExit("The packed orb has no 'format' command.")

        runs = [s["run"] for s in command.get("steps") or [] if "run" in s]

        if len(runs) != 1 or not isinstance(runs[0], dict):
            raise SystemExit("The packed 'format' command is not a single 'run' step.")

        self.parameters = command.get("parameters") or {}
        self.environment = runs[0].get("environment") or {}
        # 'circleci orb pack' writes every '<<' of an included script as '\<<'.
        self.script = str(runs[0].get("command", "")).replace("\\<<", "<<")

    def validate(self, name, parameters):
        """The problems with a case's parameters, as CircleCI would see them."""
        problems = []

        for key, value in parameters.items():
            spec = self.parameters.get(key)

            if spec is None:
                problems.append(f"'{key}' is not a parameter of ruff/format")
            elif spec.get("type") == "boolean" and not isinstance(value, bool):
                problems.append(f"'{key}' needs a boolean")
            elif spec.get("type") == "enum" and value not in spec.get("enum", []):
                problems.append(f"'{key}' does not accept {value!r}")
            elif spec.get("type") == "string" and not isinstance(value, str):
                problems.append(f"'{key}' needs a string")

        return [f"{name}: {problem}" for problem in problems]

    def render(self, parameters):
        """The step's environment for these parameters and the defaults."""

        def value_of(match):
            name = match.group(1)
            value = parameters.get(name, self.parameters[name].get("default"))

            if isinstance(value, bool):
                return "true" if value else "false"

            return str(value)

        return {
            variable: re.sub(
                r"<<\s*parameters\.([A-Za-z0-9_-]+)\s*>>", value_of, str(template)
            )
            for variable, template in self.environment.items()
        }


def base_environment(home):
    """A minimal environment, so no RUFF_* variable of the caller applies."""
    return {
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "XDG_CONFIG_HOME": str(home / ".config"),
    }


def run_step(command, parameters, directory, environment):
    """Run the packed step's script from DIRECTORY.

    Returns (status, stdout, stderr), with the two streams kept apart.
    """
    script = directory.parent / f".{directory.name}.step.sh"
    script.write_text(command.script, encoding="utf-8")
    env = {**environment, **command.render(parameters)}

    with open(os.devnull, "rb") as stdin:
        result = subprocess.run(
            ["bash", "-eo", "pipefail", str(script)],
            cwd=directory,
            env=env,
            stdin=stdin,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

    return result.returncode, result.stdout, result.stderr


def quoted_command(arguments):
    """The 'Command:' line format.sh prints for these arguments."""
    result = subprocess.run(
        ["bash", "-c", 'printf "Command:"; printf " %q" "$@"', "bash", *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def items(tokens):
    """Group options with their values: ['--color', 'never'] -> one item."""
    grouped = []
    index = 0

    while index < len(tokens):
        if tokens[index] in VALUE_OPTIONS and index + 1 < len(tokens):
            grouped.append((tokens[index], tokens[index + 1]))
            index += 2
        else:
            grouped.append((tokens[index],))
            index += 1

    return grouped


def config_values(tokens):
    return [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t == "--config"]


def read_argv(path):
    if not path.exists():
        return None

    return [a.decode("utf-8") for a in path.read_bytes().split(b"\0")[:-1]]


# ---------------------------------------------------------------------------
# Argument cases
# ---------------------------------------------------------------------------


def stand_in(directory, recorder):
    """A bin directory under DIRECTORY with RECORDER as 'ruff'."""
    (directory / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copy(recorder, directory / "bin" / "ruff")
    (directory / "bin" / "ruff").chmod(0o755)
    environment = base_environment(directory)
    environment["PATH"] = f"{directory / 'bin'}:{environment['PATH']}"
    environment["RECORD_RUFF_ARGV"] = str(directory / "argv")
    environment["RECORD_RUFF_CALLS"] = str(directory / "calls")
    return environment


def run_argument_case(command, spec, scratch):
    failures = command.validate(spec["name"], spec["parameters"])

    if failures:
        return failures, {}

    directory = scratch / "argument"
    shutil.rmtree(directory, ignore_errors=True)
    work = directory / "work"
    work.mkdir(parents=True)
    environment = stand_in(directory, RECORDER)

    status, stdout, stderr = run_step(command, spec["parameters"], work, environment)
    lines = stdout.splitlines()
    record = {"status": status, "stdout": stdout, "stderr": stderr}

    if status != 0:
        failures.append(f"expected exit status 0, got {status}")

    argv = read_argv(directory / "argv")

    if argv is None:
        failures.append("Ruff was not started for the formatting")
        return failures, record

    record["argv"] = argv

    if not argv or argv[0] != "format":
        failures.append(f"the first argument is not 'format': {argv[:1]}")
        return failures, record

    if argv.count("--") != 1:
        failures.append(f"expected one '--', found {argv.count('--')}")
        return failures, record

    separator = argv.index("--")
    options, paths = argv[1:separator], argv[separator + 1 :]

    if sorted(items(options)) != sorted(items(spec["options"])):
        failures.append(f"options {options} differ from {spec['options']}")

    if paths != spec["paths"]:
        failures.append(f"paths {paths} differ from {spec['paths']}")

    # extra_args is appended after every option the command builds.
    extra = spec["parameters"].get("extra_args", "").split()

    if extra and options[len(options) - len(extra) :] != extra:
        failures.append(f"extra_args {extra} are not the last options: {options}")

    # config_file, then the overrides in their order.
    expected_config = [
        *(
            [spec["parameters"]["config_file"]]
            if spec["parameters"].get("config_file")
            else []
        ),
        *[
            line
            for line in spec["parameters"].get("config_overrides", "").split("\n")
            if line.strip()
        ],
    ]

    if config_values(options) != expected_config:
        failures.append(
            f"the --config values are {config_values(options)}, "
            f"expected {expected_config} in this order"
        )

    if quoted_command(["ruff", *argv]) not in lines:
        failures.append("the 'Command:' line does not show the arguments received")

    calls = (directory / "calls").read_text(encoding="utf-8").splitlines()

    if len(calls) != 2 or calls[0] != "ruff --version ":
        failures.append(f"expected 'ruff --version' and one more call, got {calls}")

    if any(line.startswith("PARAM_") for line in lines + stderr.splitlines()):
        failures.append("the log prints a PARAM_ line")

    return failures, record


def run_refused_case(command, spec, scratch):
    failures = command.validate(spec["name"], spec["parameters"])
    directory = scratch / "refused"
    shutil.rmtree(directory, ignore_errors=True)
    work = directory / "work"
    work.mkdir(parents=True)
    (work / "target.py").write_text("x=1\n", encoding="utf-8")
    environment = stand_in(directory, RECORDER)
    parameters = {**spec["parameters"], "targets": "target.py"}

    status, stdout, stderr = run_step(command, parameters, work, environment)
    errors = stderr.splitlines()

    if status != 1:
        failures.append(f"expected exit status 1, got {status}")

    for line in (REFUSED_INTRO, spec["message"]):
        if line not in errors:
            failures.append(f"standard error has no line {line!r}")

    if stdout:
        failures.append(f"standard output is not empty: {stdout!r}")

    if (directory / "calls").exists():
        failures.append("Ruff was started")

    if (work / "target.py").read_text(encoding="utf-8") != "x=1\n":
        failures.append("target.py changed")

    return failures, {"status": status, "stdout": stdout, "stderr": stderr}


# ---------------------------------------------------------------------------
# Ruff cases
# ---------------------------------------------------------------------------

# Not formatted; Ruff joins the list onto one line.
UNFORMATTED = "VALUES = [1,\n     2,\n   3]\n"
UNFORMATTED_RESULT = "VALUES = [1, 2, 3]\n"
FORMATTED = "x = 1\n"
# Formatted at Ruff's default line length of 88, but not at 40.
LONG_CALL = "TOTAL = max(1234567890, 2345678901, 3456789012)\n"
# Formatted at 40, but not at 88.
NARROW_CALL = "TOTAL = max(\n    1234567890, 2345678901, 3456789012\n)\n"
DOUBLE_QUOTED = 'x = "a"\n'
# Formatted for py37 and py38. From py39 on, which includes Ruff's default of
# py310, Ruff puts the two context managers in parentheses instead.
WITH_STATEMENT = (
    'with open("a_long_file_name_aaaaaaaaaaaaaaaaaaaaa.txt") as first_file, open(\n'
    '    "b_long_file_name_bbbbbbbbbbbbbbbbbbbbb.txt"\n'
    ") as second_file:\n"
    "    pass\n"
)
# Formatted by the stable style. Ruff 0.16.2's preview style hugs the sole
# dictionary argument instead.
HUGGABLE = (
    "handle_event(\n"
    "    {\n"
    '        "message": "an error occurred while closing the stream",\n'
    '        "exception": None,\n'
    "    }\n"
    ")\n"
)
SUMMARY_WOULD = "1 file would be reformatted"


class Run:
    """One run of the step: Ruff's own output, apart from the script's lines."""

    def __init__(self, status, out, err, argv):
        self.status = status
        self.out = out
        self.err = err
        self.argv = argv


class RuffCase:
    """Helpers for one Ruff case. Every problem is collected in failures."""

    def __init__(self, command, scratch, name, real_ruff):
        self.command = command
        self.root = scratch / "ruff" / name
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        self.home = self.root / "home"
        self.home.mkdir()
        self.environment = stand_in(self.home, REAL_RECORDER)
        self.environment["RECORD_RUFF_REAL"] = real_ruff
        self.failures = []
        self.runs = []

    def directory(self, name, files, config=""):
        """A directory with FILES and a ruff.toml that holds CONFIG."""
        directory = self.root / name
        directory.mkdir(parents=True)
        (directory / "ruff.toml").write_text(config, encoding="utf-8")

        for path, text in files.items():
            (directory / path).parent.mkdir(parents=True, exist_ok=True)
            (directory / path).write_text(text, encoding="utf-8")

        return directory

    def run(self, directory, label, expected_status, *, started=True, **parameters):
        """Run the step. STARTED says whether Ruff is expected to start."""
        self.failures += self.command.validate(label, parameters)

        for name in ("argv", "calls"):
            (self.home / name).unlink(missing_ok=True)

        status, stdout, stderr = run_step(
            self.command, parameters, directory, self.environment
        )
        lines = stdout.splitlines()
        argv = read_argv(self.home / "argv")
        self.runs.append(
            {
                "run": label,
                "parameters": parameters,
                "status": status,
                "argv": argv,
                "stdout": stdout,
                "stderr": stderr,
            }
        )

        if status != expected_status:
            self.failures.append(
                f"{label}: expected exit status {expected_status}, got {status}"
            )

        if not started:
            if (self.home / "calls").exists():
                self.failures.append(f"{label}: Ruff was started")

            return Run(status, lines, stderr.splitlines(), argv)

        # format.sh prints the version and the command before Ruff's output.
        if lines[:1] != [f"ruff {RUFF_VERSION}"]:
            self.failures.append(f"{label}: the output does not start with the version")
        elif argv is None or quoted_command(["ruff", *argv]) not in lines[1:2]:
            self.failures.append(
                f"{label}: the 'Command:' line does not show the arguments received"
            )

        return Run(status, lines[2:], stderr.splitlines(), argv)

    def has_option(self, label, run, option):
        if option not in (run.argv or []):
            self.failures.append(f"{label}: Ruff did not receive {option}")

    def lacks_option(self, label, run, option):
        if option in (run.argv or []):
            self.failures.append(f"{label}: Ruff received {option}")

    def has_line(self, label, lines, line, stream="standard output"):
        if line not in lines:
            self.failures.append(f"{label}: {stream} has no line {line!r}")

    def lacks_line(self, label, lines, line, stream="standard output"):
        if line in lines:
            self.failures.append(f"{label}: {stream} has the line {line!r}")

    def has_match(self, label, lines, pattern, stream="standard output"):
        if not any(re.search(pattern, line) for line in lines):
            self.failures.append(f"{label}: no line of {stream} matches {pattern!r}")

    def lacks_match(self, label, lines, pattern, stream="standard output"):
        if any(re.search(pattern, line) for line in lines):
            self.failures.append(f"{label}: a line of {stream} matches {pattern!r}")

    def empty(self, label, lines, stream):
        if lines:
            self.failures.append(f"{label}: {stream} is not empty: {lines}")

    def same(self, label, actual, expected, what):
        if actual != expected:
            self.failures.append(
                f"{label}: {what} is {actual!r}, expected {expected!r}"
            )

    def content(self, label, path, expected):
        self.same(label, path.read_text(encoding="utf-8"), expected, path.name)

    def snapshot(self, directory):
        return {
            str(path.relative_to(directory)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(directory.rglob("*"))
            if path.is_file() and ".ruff_cache" not in path.parts
        }

    def unchanged(self, label, directory, before):
        if self.snapshot(directory) != before:
            self.failures.append(f"{label}: files in {directory.name} changed")


def ruff_modes(c):
    """check, diff and write, told apart by more than a common string."""
    d = c.directory("modes", {"a.py": UNFORMATTED, "ok.py": FORMATTED})
    before = c.snapshot(d)

    check = c.run(d, "check", 1, mode="check", targets="a.py")
    c.has_option("check", check, "--check")
    c.lacks_option("check", check, "--diff")
    c.has_line("check", check.out, "unformatted: File would be reformatted")
    c.has_line("check", check.out, " --> a.py:1:13")
    c.has_line("check", check.out, "1 + VALUES = [1, 2, 3]")
    c.has_line("check", check.out, SUMMARY_WOULD)
    c.lacks_line("check", check.out, "--- a.py")
    c.lacks_line("check", check.out, "+VALUES = [1, 2, 3]")
    c.lacks_match("check", check.out, r"^@@ ")
    c.empty("check", check.err, "standard error")
    c.unchanged("check", d, before)

    diff = c.run(d, "diff", 1, mode="diff", targets="a.py")
    c.has_option("diff", diff, "--diff")
    c.lacks_option("diff", diff, "--check")

    for line in ("--- a.py", "+++ a.py", "@@ -1,3 +1 @@", "-VALUES = [1,"):
        c.has_line("diff", diff.out, line)

    c.has_line("diff", diff.out, "+VALUES = [1, 2, 3]")
    c.lacks_line("diff", diff.out, "unformatted: File would be reformatted")
    c.lacks_match("diff", diff.out, r"^ *--> ")
    c.lacks_line("diff", diff.out, SUMMARY_WOULD)
    c.has_line("diff", diff.err, SUMMARY_WOULD, "standard error")
    c.unchanged("diff", d, before)

    write = c.run(d, "write", 0, mode="write", targets="a.py")
    c.lacks_option("write", write, "--check")
    c.lacks_option("write", write, "--diff")
    c.same("write", write.out, ["1 file reformatted"], "standard output")
    c.empty("write", write.err, "standard error")
    c.content("write", d / "a.py", UNFORMATTED_RESULT)

    # A formatted file: exit 0 in every mode, and only write says so on
    # standard output with other words.
    expected = {
        "check": (["1 file already formatted"], []),
        "diff": ([], ["1 file already formatted"]),
        "write": (["1 file left unchanged"], []),
    }

    for mode, (out, err) in expected.items():
        label = f"{mode} on a formatted file"
        run = c.run(d, label, 0, mode=mode, targets="ok.py")
        c.same(label, run.out, out, "standard output")
        c.same(label, run.err, err, "standard error")

    c.content("formatted file", d / "ok.py", FORMATTED)


def ruff_exit_non_zero_on_format(c):
    d = c.directory("enzof", {"a.py": UNFORMATTED, "ok.py": FORMATTED})
    before = c.snapshot(d)

    for mode in ("check", "diff"):
        c.run(d, f"{mode}, unformatted", 1, mode=mode, exit_non_zero_on_format=True)
        c.run(
            d,
            f"{mode}, formatted",
            0,
            mode=mode,
            exit_non_zero_on_format=True,
            targets="ok.py",
        )

    c.unchanged("check and diff", d, before)

    # The result and the exit status separately: the file is rewritten, and
    # the step fails because it was.
    run = c.run(d, "write, unformatted", 1, mode="write", exit_non_zero_on_format=True)
    c.has_line(
        "write, unformatted", run.out, "1 file reformatted, 1 file left unchanged"
    )
    c.content("write, unformatted", d / "a.py", UNFORMATTED_RESULT)

    run = c.run(d, "write, formatted", 0, mode="write", exit_non_zero_on_format=True)
    c.has_line("write, formatted", run.out, "2 files left unchanged")

    (d / "a.py").write_text(UNFORMATTED, encoding="utf-8")
    c.run(d, "write without it", 0, mode="write")
    c.content("write without it", d / "a.py", UNFORMATTED_RESULT)


def ruff_configuration_errors(c):
    """Exit 2 for a setting Ruff cannot use, in every mode, never 1."""
    files = {"a.py": UNFORMATTED, "bad.toml": "line-length = \n", "other.toml": ""}
    d = c.directory("errors", files)
    before = c.snapshot(d)
    errors = [
        (
            "missing config_file",
            {"config_file": "missing.toml"},
            r"^error: invalid value 'missing\.toml' for '--config <CONFIG_OPTION>'$",
        ),
        (
            "invalid config_file",
            {"config_file": "bad.toml"},
            r"Failed to parse .*bad\.toml$",
        ),
        (
            "invalid config_overrides",
            {"config_overrides": 'format.quote-style = "no-such-style"'},
            (
                r"^error: invalid value 'format\.quote-style = \"no-such-style\"' "
                r"for '--config <CONFIG_OPTION>'$"
            ),
        ),
        (
            "isolated with config_file",
            {"config_file": "other.toml", "isolated": True},
            r"cannot be used with `--isolated`",
        ),
        (
            "line_length and extra_args --line-length",
            {"extra_args": "--line-length 40", "line_length": "88"},
            r"'--line-length <LINE_LENGTH>' cannot be used multiple times",
        ),
    ]

    for mode in ("check", "diff", "write"):
        for name, parameters, pattern in errors:
            label = f"{name} ({mode})"
            run = c.run(d, label, 2, mode=mode, targets="a.py", **parameters)
            c.has_match(label, run.err, pattern, "standard error")
            c.empty(label, run.out, "standard output")
            c.lacks_match(label, run.err, r"reformatted", "standard error")

    c.unchanged("configuration errors", d, before)


def ruff_config_file(c):
    files = {
        "long.py": LONG_CALL,
        "quoted.py": DOUBLE_QUOTED,
        "configs/forty.toml": "line-length = 40\n",
        "configs/eighty-eight.toml": "line-length = 88\n",
        "configs/single.toml": '[format]\nquote-style = "single"\n',
    }
    d = c.directory("config-file", files)
    c.run(d, "without config_file", 0, targets="long.py quoted.py")
    c.run(d, "line-length = 40", 1, config_file="configs/forty.toml", targets="long.py")
    c.run(
        d,
        "quote-style single",
        1,
        config_file="configs/single.toml",
        targets="quoted.py",
    )

    # The named file replaces the ruff.toml that Ruff would find.
    found = c.directory("config-file-found", files, "line-length = 40\n")
    c.run(found, "the ruff.toml found", 1, targets="long.py")
    c.run(
        found,
        "config_file over the ruff.toml found",
        0,
        config_file="configs/eighty-eight.toml",
        targets="long.py",
    )


def ruff_config_overrides(c):
    files = {
        "long.py": LONG_CALL,
        "quoted.py": DOUBLE_QUOTED,
        "forty.toml": "line-length = 40\n",
    }
    d = c.directory("overrides", files)
    single = 'format.quote-style = "single"'
    c.run(
        d, "line-length = 40", 1, config_overrides="line-length = 40", targets="long.py"
    )
    c.run(d, "quote-style single", 1, config_overrides=single, targets="quoted.py")
    c.run(d, "write", 0, config_overrides=single, mode="write", targets="quoted.py")
    c.content("write", d / "quoted.py", "x = 'a'\n")
    c.run(
        d,
        "over config_file",
        0,
        config_file="forty.toml",
        config_overrides="line-length = 88",
        targets="long.py",
    )
    # Of two overrides of one setting, Ruff applies the first.
    c.run(
        d,
        "the first of two",
        1,
        config_overrides="line-length = 40\nline-length = 88",
        targets="long.py",
    )
    c.run(
        d,
        "the first of two, reversed",
        0,
        config_overrides="line-length = 88\nline-length = 40",
        targets="long.py",
    )

    found = c.directory("overrides-found", {"long.py": LONG_CALL}, "line-length = 40\n")
    c.run(
        found,
        "over the ruff.toml found",
        0,
        config_overrides="line-length = 88",
        targets="long.py",
    )


def ruff_isolated(c):
    files = {"long.py": LONG_CALL, "quoted.py": DOUBLE_QUOTED}
    config = 'line-length = 40\n\n[format]\nquote-style = "single"\n'
    d = c.directory("isolated", files, config)
    c.run(d, "the ruff.toml found", 1, targets="long.py")
    c.run(d, "the ruff.toml found, quote-style", 1, targets="quoted.py")
    c.run(d, "isolated", 0, isolated=True, targets="long.py quoted.py")
    # Inline settings are not configuration files, so they still apply.
    c.run(
        d,
        "isolated with config_overrides",
        1,
        config_overrides="line-length = 40",
        isolated=True,
        targets="long.py",
    )
    c.run(
        d,
        "isolated with line_length",
        1,
        isolated=True,
        line_length="40",
        targets="long.py",
    )


def ruff_line_length(c):
    d = c.directory("line-length", {"long.py": LONG_CALL, "narrow.py": NARROW_CALL})
    c.run(d, "long at the default", 0, targets="long.py")
    c.run(d, "long at 40", 1, line_length="40", targets="long.py")
    c.run(d, "narrow at the default", 1, targets="narrow.py")
    c.run(d, "narrow at 40", 0, line_length="40", targets="narrow.py")
    # '--line-length' wins over a 'line-length' in config_overrides, in
    # either direction.
    c.run(
        d,
        "over config_overrides",
        0,
        config_overrides="line-length = 40",
        line_length="88",
        targets="long.py",
    )
    c.run(
        d,
        "over config_overrides, reversed",
        1,
        config_overrides="line-length = 88",
        line_length="40",
        targets="long.py",
    )

    found = c.directory(
        "line-length-found", {"long.py": LONG_CALL}, "line-length = 40\n"
    )
    c.run(found, "over the ruff.toml found", 0, line_length="88", targets="long.py")


# What can go wrong when a report is not in the format a case expects.
REPORT_ERRORS = (
    AttributeError,
    ElementTree.ParseError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
)


def json_findings(text):
    """(file, code, line, column) of each finding of the 'json' report."""
    return [
        (
            pathlib.Path(f["filename"]).name,
            f["code"],
            f["location"]["row"],
            f["location"]["column"],
        )
        for f in json.loads(text)
    ]


def json_lines_findings(text):
    return [
        finding for line in text.splitlines() for finding in json_findings(f"[{line}]")
    ]


def gitlab_findings(text):
    return [
        (
            f["location"]["path"],
            f["check_name"],
            f["location"]["positions"]["begin"]["line"],
            f["location"]["positions"]["begin"]["column"],
        )
        for f in json.loads(text)
    ]


def rdjson_findings(text):
    return [
        (
            pathlib.Path(f["location"]["path"]).name,
            f["code"]["value"],
            f["location"]["range"]["start"]["line"],
            f["location"]["range"]["start"]["column"],
        )
        for f in json.loads(text)["diagnostics"]
    ]


def sarif_findings(text):
    results = []

    for r in json.loads(text)["runs"][0]["results"]:
        location = r["locations"][0]["physicalLocation"]
        results.append(
            (
                pathlib.Path(location["artifactLocation"]["uri"]).name,
                r["ruleId"],
                location["region"]["startLine"],
                location["region"]["startColumn"],
            )
        )

    return results


def junit_cases(text):
    return [
        (case.get("name"), case.find("failure").get("message"))
        for case in ElementTree.fromstring(text).iter("testcase")
    ]


def ruff_output_format_check(c):
    """Every output_format in check mode, the only mode that reports in it."""
    d = c.directory("output-format", {"a.py": UNFORMATTED, "ok.py": FORMATTED})
    before = c.snapshot(d)
    finding = ("a.py", "unformatted", 1, 13)
    runs = {
        value: c.run(d, value, 1, output_format=value, targets="a.py")
        for value in ("default", *OUTPUT_FORMATS)
    }

    for value, run in runs.items():
        c.has_option(value, run, "--check")
        c.empty(value, run.err, "standard error")

    c.same("default", runs["default"].out, runs["full"].out, "the default report")
    c.has_line("full", runs["full"].out, " --> a.py:1:13")
    c.has_line(
        "concise",
        runs["concise"].out,
        "a.py:1:13: unformatted: File would be reformatted",
    )
    c.has_line("grouped", runs["grouped"].out, "a.py:")
    c.has_line(
        "grouped", runs["grouped"].out, "  1:13 unformatted: File would be reformatted"
    )
    c.has_line(
        "pylint", runs["pylint"].out, "a.py:1: [unformatted] File would be reformatted"
    )
    c.has_match(
        "github",
        runs["github"].out,
        r"^::error title=ruff \(unformatted\),file=/\S*/a\.py,line=1,endLine=3::"
        r"a\.py:1:13: unformatted: File would be reformatted$",
    )
    c.has_match(
        "azure",
        runs["azure"].out,
        r"^##vso\[task\.logissue type=error;sourcepath=/\S*/a\.py;linenumber=1;"
        r"columnnumber=13;code=unformatted;\]File would be reformatted$",
    )

    # The machine-readable reports are parsed, and only what a case expects
    # is compared, so a report in another format is a failure, not a crash.
    for value, read, expected in (
        ("json", json_findings, [finding]),
        ("json-lines", json_lines_findings, [finding]),
        ("gitlab", gitlab_findings, [finding]),
        ("rdjson", rdjson_findings, [finding]),
        ("sarif", sarif_findings, [finding]),
        ("junit", junit_cases, [("org.ruff.unformatted", "File would be reformatted")]),
    ):
        try:
            found = read("\n".join(runs[value].out))
        except REPORT_ERRORS as error:
            c.failures.append(f"{value}: the report cannot be read: {error!r}")
        else:
            c.same(value, found, expected, "the findings")

    clean = c.run(d, "json, formatted", 0, output_format="json", targets="ok.py")

    try:
        found = json_findings("\n".join(clean.out))
    except REPORT_ERRORS as error:
        c.failures.append(f"json, formatted: the report cannot be read: {error!r}")
    else:
        c.same("json, formatted", found, [], "the findings")

    c.unchanged("output formats", d, before)


def ruff_output_format_other_modes(c):
    """diff ignores output_format, and write reports nothing in it."""
    d = c.directory("output-format-modes", {"a.py": UNFORMATTED})
    before = c.snapshot(d)
    plain = c.run(d, "diff", 1, mode="diff", targets="a.py")

    for value in ("json", "concise", "github"):
        label = f"diff with {value}"
        run = c.run(d, label, 1, mode="diff", output_format=value, targets="a.py")
        c.has_option(label, run, "--output-format")
        c.same(label, run.out, plain.out, "standard output")
        c.same(label, run.err, plain.err, "standard error")

    c.unchanged("diff", d, before)

    run = c.run(
        d, "write with json", 0, mode="write", output_format="json", targets="a.py"
    )
    c.empty("write with json", run.out, "standard output")
    c.content("write with json", d / "a.py", UNFORMATTED_RESULT)

    (d / "a.py").write_text(UNFORMATTED, encoding="utf-8")
    run = c.run(
        d,
        "write with concise",
        0,
        mode="write",
        output_format="concise",
        targets="a.py",
    )
    c.same("write with concise", run.out, ["1 file reformatted"], "standard output")
    c.content("write with concise", d / "a.py", UNFORMATTED_RESULT)


def ruff_excluded_paths(c):
    files = {"skip.py": UNFORMATTED, "venv/inside.py": UNFORMATTED, "ok.py": FORMATTED}
    d = c.directory("excluded", files)
    before = c.snapshot(d)
    concise = {"output_format": "concise"}
    run = c.run(d, "default exclusions", 1, **concise)
    c.has_match("default exclusions", run.out, r"^skip\.py:")
    c.lacks_match("default exclusions", run.out, r"^venv/inside\.py:")
    run = c.run(d, "excluded_paths", 1, excluded_paths="skip.py", **concise)
    c.lacks_match("excluded_paths", run.out, r"^skip\.py:")
    c.has_match("excluded_paths", run.out, r"^venv/inside\.py:1:13: unformatted")
    c.run(d, "extend_excluded_paths", 0, extend_excluded_paths="skip.py")
    c.unchanged("exclusions", d, before)


def ruff_extensions(c):
    d = c.directory("extensions", {"module.pya": UNFORMATTED})
    c.run(d, "without extensions", 0)
    run = c.run(
        d, "with extensions", 1, extensions="pya:python", output_format="concise"
    )
    c.has_line(
        "with extensions",
        run.out,
        "module.pya:1:13: unformatted: File would be reformatted",
    )


def ruff_force_exclude(c):
    parameters = {"extend_excluded_paths": "skip.py", "targets": "skip.py"}
    d = c.directory("force-exclude", {"skip.py": UNFORMATTED})
    c.run(d, "auto", 1, **parameters)
    c.run(d, "enabled", 0, force_exclude="enabled", **parameters)
    configured = c.directory(
        "force-exclude-config", {"skip.py": UNFORMATTED}, "force-exclude = true\n"
    )
    c.run(configured, "auto with the config", 0, **parameters)
    c.run(
        configured,
        "disabled with the config",
        1,
        force_exclude="disabled",
        **parameters,
    )


def ruff_respect_gitignore(c):
    if shutil.which("git") is None:
        c.failures.append("git is needed for a repository with a .gitignore")
        return

    files = {
        ".gitignore": "ignored.py\n",
        "ignored.py": UNFORMATTED,
        "kept.py": FORMATTED,
    }

    for name, config in (
        ("gitignore", ""),
        ("gitignore-config", "respect-gitignore = false\n"),
    ):
        directory = c.directory(name, files, config)
        subprocess.run(["git", "init", "-q", str(directory)], check=True)

    d = c.root / "gitignore"
    configured = c.root / "gitignore-config"
    c.run(d, "auto", 0)
    c.run(d, "disabled", 1, respect_gitignore="disabled")
    c.run(configured, "auto with the config", 1)
    c.run(configured, "enabled with the config", 0, respect_gitignore="enabled")


def ruff_target_version(c):
    d = c.directory("target-version", {"with.py": WITH_STATEMENT})
    c.run(d, "default", 1)

    for value, status in (("py37", 0), ("py38", 0), ("py39", 1), ("py315", 1)):
        c.run(d, value, status, target_version=value)

    # 'default' passes nothing, so 'requires-python' decides.
    inferred = c.directory(
        "target-version-inferred",
        {
            "with.py": WITH_STATEMENT,
            "pyproject.toml": '[project]\nrequires-python = ">=3.8"\n',
        },
    )
    c.run(inferred, "default with requires-python >=3.8", 0)
    c.run(inferred, "py39 over requires-python", 1, target_version="py39")


def ruff_preview(c):
    d = c.directory("preview", {"a.py": HUGGABLE})
    c.run(d, "auto", 0)
    run = c.run(d, "enabled", 1, mode="diff", preview="enabled")
    c.has_line("enabled", run.out, "+handle_event({")
    c.run(d, "disabled", 0, preview="disabled")
    configured = c.directory("preview-config", {"a.py": HUGGABLE}, "preview = true\n")
    c.run(configured, "auto with the config", 1)
    c.run(configured, "disabled with the config", 0, preview="disabled")


def ruff_cache(c):
    d = c.directory("cache-default", {"a.py": FORMATTED})
    c.run(d, "default", 0)

    if not (d / ".ruff_cache" / "CACHEDIR.TAG").is_file():
        c.failures.append("default: no .ruff_cache in the project")

    elsewhere = c.root / "elsewhere"
    d = c.directory("cache-dir", {"a.py": FORMATTED})
    c.run(d, "cache_dir", 0, cache_dir=str(elsewhere))

    if not (elsewhere / "CACHEDIR.TAG").is_file():
        c.failures.append("cache_dir: no cache in the named directory")

    if (d / ".ruff_cache").exists():
        c.failures.append("cache_dir: a .ruff_cache was still written in the project")

    d = c.directory("no-cache", {"a.py": FORMATTED})
    c.run(d, "no_cache", 0, no_cache=True)

    if (d / ".ruff_cache").exists():
        c.failures.append("no_cache: a .ruff_cache was written")


def ruff_verbosity(c):
    d = c.directory("verbosity", {"a.py": UNFORMATTED})
    line = "a.py:1:13: unformatted: File would be reformatted"
    concise = {"output_format": "concise"}

    run = c.run(d, "default", 1, **concise)
    c.same("default", run.out, [line, SUMMARY_WOULD], "standard output")
    c.empty("default", run.err, "standard error")

    run = c.run(d, "verbose", 1, verbosity="verbose", **concise)
    c.same("verbose", run.out, [line, SUMMARY_WOULD], "standard output")
    c.has_match(
        "verbose",
        run.err,
        r"\[ruff::resolve\]\[DEBUG\] Using configuration file .* at: /\S*/ruff\.toml$",
        "standard error",
    )

    run = c.run(d, "quiet", 1, verbosity="quiet", **concise)
    c.same("quiet", run.out, [line], "standard output")
    c.empty("quiet", run.err, "standard error")

    run = c.run(d, "quiet, diff", 1, mode="diff", verbosity="quiet")
    c.has_line("quiet, diff", run.out, "+VALUES = [1, 2, 3]")
    c.empty("quiet, diff", run.err, "standard error")

    for mode in ("check", "diff"):
        label = f"silent, {mode}"
        run = c.run(d, label, 1, mode=mode, verbosity="silent")
        c.empty(label, run.out, "standard output")
        c.empty(label, run.err, "standard error")


def ruff_color(c):
    d = c.directory("color", {"a.py": UNFORMATTED})

    for mode in ("check", "diff"):
        for value, coloured in (("auto", False), ("always", True), ("never", False)):
            label = f"{mode}, {value}"
            run = c.run(d, label, 1, mode=mode, color=value)

            if any("\x1b[" in line for line in run.out) != coloured:
                c.failures.append(
                    f"{label}: expected {'' if coloured else 'no '}ANSI colour codes"
                )


def ruff_extra_args(c):
    d = c.directory("extra-args", {"long.py": LONG_CALL, "a.py": UNFORMATTED})
    before = c.snapshot(d)
    # no_cache gives the command an option of its own to put first.
    run = c.run(
        d,
        "--line-length 40",
        1,
        extra_args="--line-length 40",
        no_cache=True,
        targets="long.py",
    )

    if (run.argv or [])[-5:] != ["--no-cache", "--line-length", "40", "--", "long.py"]:
        c.failures.append(f"--line-length 40: not last before the paths: {run.argv}")

    for value, message in (
        ("--", "  '--': the paths come from 'targets', and '--' is added for them"),
        (
            "@args",
            (
                "  '@args': Ruff would read an item that starts with '@' "
                "as an argument file"
            ),
        ),
    ):
        label = f"refused {value}"
        run = c.run(
            d, label, 1, started=False, extra_args=value, mode="write", targets="a.py"
        )
        c.has_line(label, run.err, REFUSED_INTRO, "standard error")
        c.has_line(label, run.err, message, "standard error")
        c.empty(label, run.out, "standard output")

    c.unchanged("extra_args", d, before)


RUFF_CASES = [
    ("ruff-modes", ruff_modes),
    ("ruff-exit-non-zero-on-format", ruff_exit_non_zero_on_format),
    ("ruff-configuration-errors", ruff_configuration_errors),
    ("ruff-config-file", ruff_config_file),
    ("ruff-config-overrides", ruff_config_overrides),
    ("ruff-isolated", ruff_isolated),
    ("ruff-line-length", ruff_line_length),
    ("ruff-output-format-check", ruff_output_format_check),
    ("ruff-output-format-other-modes", ruff_output_format_other_modes),
    ("ruff-excluded-paths", ruff_excluded_paths),
    ("ruff-extensions", ruff_extensions),
    ("ruff-force-exclude", ruff_force_exclude),
    ("ruff-respect-gitignore", ruff_respect_gitignore),
    ("ruff-target-version", ruff_target_version),
    ("ruff-preview", ruff_preview),
    ("ruff-cache", ruff_cache),
    ("ruff-verbosity", ruff_verbosity),
    ("ruff-color", ruff_color),
    ("ruff-extra-args", ruff_extra_args),
]


# ---------------------------------------------------------------------------
# Coverage and the table
# ---------------------------------------------------------------------------


def coverage(command):
    """Every parameter needs a non-default case, every enum value a case."""
    failures = []
    set_values = {}

    for spec in ARGUMENT_CASES:
        for key, value in spec["parameters"].items():
            set_values.setdefault(key, []).append(value)

    for name, spec in sorted(command.parameters.items()):
        values = set_values.get(name, [])
        default = spec.get("default")

        if spec.get("type") == "enum":
            for value in spec.get("enum", []):
                if value not in values:
                    failures.append(f"coverage: no argument case sets {name}={value}")
        elif not any(value != default for value in values):
            failures.append(
                f"coverage: no argument case sets {name} to a non-default value"
            )

    return failures


def parameter_rows(text):
    """The names in the first column of the table headed 'Parameter'."""
    rows = []
    inside = False

    for line in text.splitlines():
        if line.startswith("| Parameter |"):
            inside = True
        elif inside and not line.startswith("|"):
            break
        elif inside and (match := re.match(r"^\|\s*`([a-z_]+)`\s*\|", line)):
            rows.append(match.group(1))

    return rows


def table(command):
    if not TABLE.is_file():
        return [f"table: {TABLE.name} does not exist"]

    failures = []
    rows = parameter_rows(TABLE.read_text(encoding="utf-8"))

    if not rows:
        return [f"table: {TABLE.name} has no table headed 'Parameter'"]

    for name in sorted({row for row in rows if rows.count(row) > 1}):
        failures.append(f"table: {name} has more than one row")

    for name in sorted(set(command.parameters) - set(rows)):
        failures.append(f"table: {name} has no row in {TABLE.name}")

    for name in sorted(set(rows) - set(command.parameters)):
        failures.append(f"table: {name} is not a parameter of ruff/format")

    return failures


def regression(pairs):
    """Compare the cases a regression run printed with the table's list."""
    if not TABLE.is_file():
        return [f"{TABLE.name} does not exist"]

    text = TABLE.read_text(encoding="utf-8")
    listed = {
        script: block.split()
        for script, block in re.findall(
            r"^```text (\S+)\n(.*?)^```$", text, re.MULTILINE | re.DOTALL
        )
    }
    header = re.compile(r"^----- (?:format )?(\S+) \(exit status \d+\) -----$")
    failures = []

    for script, log in pairs:
        if script not in listed:
            failures.append(f"{TABLE.name} lists no cases for {script}")
            continue

        ran = [
            m.group(1)
            for line in pathlib.Path(log).read_text(encoding="utf-8").splitlines()
            if (m := header.match(line))
        ]
        print(f"{script}: {len(ran)} cases ran, {len(listed[script])} listed")

        for name in sorted(set(ran) - set(listed[script])):
            failures.append(f"{script}: case {name} ran but is not listed")

        for name in sorted(set(listed[script]) - set(ran)):
            failures.append(f"{script}: case {name} is listed but did not run")

        for name in sorted({n for n in listed[script] if listed[script].count(n) > 1}):
            failures.append(f"{script}: case {name} is listed twice")

    return failures


# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("packed_orb", nargs="?")
    parser.add_argument("--report", type=pathlib.Path)
    parser.add_argument(
        "--regression-log", nargs=2, action="append", metavar=("SCRIPT", "LOG")
    )
    arguments = parser.parse_args()

    if arguments.regression_log:
        failures = regression(arguments.regression_log)

        for failure in failures:
            print(f"FAIL: {failure}")

        if not failures:
            print(
                f"Every regression case that ran is listed in {TABLE.name}, and no other."
            )

        return 1 if failures else 0

    if not arguments.packed_orb:
        parser.print_help()
        return 2

    command = Command(arguments.packed_orb)
    failures = []
    results = []
    print(f"Packed orb: {arguments.packed_orb}")
    print(
        "SHA-256 of the format script: "
        f"{hashlib.sha256(command.script.encode()).hexdigest()}"
    )

    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = pathlib.Path(scratch_name)

        print(
            f"\nArgument cases ({len(ARGUMENT_CASES)}), with {RECORDER.name} as Ruff:"
        )

        for spec in ARGUMENT_CASES:
            case_failures, record = run_argument_case(command, spec, scratch)
            results.append(
                {"kind": "argument", **spec, **record, "failures": case_failures}
            )
            print(f"  [{'FAIL' if case_failures else 'ok'}] {spec['name']}")
            failures += [f"{spec['name']}: {f}" for f in case_failures]

        for spec in REFUSED_CASES:
            case_failures, record = run_refused_case(command, spec, scratch)
            results.append(
                {"kind": "refused", **spec, **record, "failures": case_failures}
            )
            print(f"  [{'FAIL' if case_failures else 'ok'}] {spec['name']} (refused)")
            failures += [f"{spec['name']}: {f}" for f in case_failures]

        real_ruff = shutil.which("ruff")
        version = (
            subprocess.run(
                [real_ruff, "--version"], capture_output=True, text=True, check=False
            ).stdout.strip()
            if real_ruff
            else ""
        )
        print(f"\nRuff cases ({len(RUFF_CASES)}) with {version or 'no Ruff'}:")

        if version != f"ruff {RUFF_VERSION}":
            failures.append(
                f"Ruff cases need ruff {RUFF_VERSION} on PATH, found {version!r}"
            )
        else:
            for name, function in RUFF_CASES:
                ruff_case = RuffCase(command, scratch, name, real_ruff)

                try:
                    function(ruff_case)
                except (*REPORT_ERRORS, OSError, subprocess.SubprocessError) as error:
                    ruff_case.failures.append(f"the case stopped: {error!r}")

                results.append(
                    {
                        "kind": "ruff",
                        "name": name,
                        "runs": ruff_case.runs,
                        "failures": ruff_case.failures,
                    }
                )
                print(
                    f"  [{'FAIL' if ruff_case.failures else 'ok'}] {name} "
                    f"({len(ruff_case.runs)} runs)"
                )
                failures += [f"{name}: {f}" for f in ruff_case.failures]

    checks = coverage(command) + table(command)
    print(f"\nCoverage of {len(command.parameters)} parameters and {TABLE.name}:")
    print(f"  [{'FAIL' if checks else 'ok'}] every parameter, enum value and table row")
    failures += checks

    if arguments.report:
        arguments.report.mkdir(parents=True, exist_ok=True)
        (arguments.report / "results.json").write_text(
            json.dumps({"failures": failures, "cases": results}, indent=2) + "\n",
            encoding="utf-8",
        )

    if failures:
        print()
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(
        f"\nAll {len(ARGUMENT_CASES) + len(REFUSED_CASES)} argument cases and "
        f"{len(RUFF_CASES)} Ruff cases passed, and every parameter is covered."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
