"""Every public parameter of ruff/check, from the packed command to Ruff.

Usage:

    python3 tests/arguments/check-parameters.py PACKED_ORB [--report DIR]
    python3 tests/arguments/check-parameters.py --regression-log SCRIPT LOG ...

PACKED_ORB is the orb.yml that 'circleci orb pack src' writes, and PyYAML is
required to read it. The cases run the packed 'check' command the way
CircleCI runs its step: every '<<parameters.NAME>>' in the step's environment
is replaced with the value the case gives, or with the default, and the
step's script is run with bash. A case names public parameters only, so a
parameter that does not reach the script, or reaches it under another
variable, fails its case.

Argument cases put tests/arguments/record-ruff.sh first on PATH as 'ruff' and
compare what it receives with what the case expects:

- the options before '--' as a whole, in any order. An option and its value
  form one item, so '--select F' and '--select E' differ;
- the paths after '--', in their order;
- the order where it matters. 'extra_args' comes after every option the
  command builds, and the '--config' values come as 'config_file', then the
  'config_overrides' lines in their order, then 'line_length'. Of several
  overrides of one setting, Ruff 0.16.2 applies the first;
- the 'Command:' line, which must show exactly the arguments received, and
  that Ruff was started twice, 'ruff --version' first.

Every parameter needs an argument case with a value other than its default,
every value of an enum needs a case of its own, and
tests/arguments/check-parameters.md needs one row per parameter.

Ruff cases run Ruff 0.16.2 in a temporary directory that holds an empty
ruff.toml, or the configuration the case writes, so no other configuration
applies. Each requires an exact exit status, and the output lines and file
contents the case names. They cover the parameters whose effect is checked
with the real Ruff, as tests/arguments/check-parameters.md lists them.

With --regression-log, the script instead compares the case names that a run
of a regression script printed with the names that
tests/arguments/check-parameters.md lists for that script, both ways.

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

HERE = pathlib.Path(__file__).resolve().parent
TABLE = HERE / "check-parameters.md"
RECORDER = HERE / "record-ruff.sh"
RUFF_VERSION = "0.16.2"

# Ruff options that take the next argument as their value.
VALUE_OPTIONS = {
    "--cache-dir",
    "--color",
    "--config",
    "--exclude",
    "--extend-exclude",
    "--extend-per-file-ignores",
    "--extend-select",
    "--extension",
    "--fixable",
    "--ignore",
    "--output-file",
    "--output-format",
    "--per-file-ignores",
    "--select",
    "--target-version",
    "--unfixable",
}

# What 'fix: never', the default, passes.
NEVER = ["--no-fix", "--no-fix-only"]


def expect(*tokens):
    """The arguments of the defaults plus TOKENS."""
    return [*NEVER, *tokens]


def case(name, parameters, options, paths=(".",), output=(), no_output=()):
    return {
        "name": name,
        "parameters": parameters,
        "options": list(options),
        "paths": list(paths),
        "output": list(output),
        "no_output": list(no_output),
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
        {"config_overrides": 'lint.ignore = ["F401"]\n\nline-length = 100\n'},
        expect("--config", 'lint.ignore = ["F401"]', "--config", "line-length = 100"),
    ),
    case("config_overrides=blank", {"config_overrides": " \n\t\n"}, expect()),
    case("diff=true", {"diff": True}, expect("--diff")),
    case(
        "excluded_paths",
        {"excluded_paths": "build/*,docs/conf.py"},
        expect("--exclude", "build/*,docs/conf.py"),
    ),
    case(
        "exit_non_zero_on_fix=true",
        {"exit_non_zero_on_fix": True},
        expect("--exit-non-zero-on-fix"),
    ),
    case("exit_zero=true", {"exit_zero": True}, expect("--exit-zero")),
    case(
        "extend_excluded_paths",
        {"extend_excluded_paths": "generated/*"},
        expect("--extend-exclude", "generated/*"),
    ),
    case(
        "extend_per_file_ignores",
        {"extend_per_file_ignores": "tests/*:S101,__init__.py:F401"},
        expect("--extend-per-file-ignores", "tests/*:S101,__init__.py:F401"),
    ),
    case(
        "extend_selected_rules",
        {"extend_selected_rules": "E501,D"},
        expect("--extend-select", "E501,D"),
    ),
    case(
        "extensions",
        {"extensions": "pya:python\nipy:ipynb"},
        expect("--extension", "pya:python", "--extension", "ipy:ipynb"),
    ),
    case(
        "extra_args",
        {"extra_args": "--extend-fixable F401\n--show-settings"},
        expect("--extend-fixable", "F401", "--show-settings"),
    ),
    case("fix=never", {"fix": "never"}, expect()),
    case("fix=auto", {"fix": "auto"}, []),
    case("fix=safe", {"fix": "safe"}, ["--fix", "--no-unsafe-fixes"]),
    case("fix=unsafe", {"fix": "unsafe"}, ["--fix", "--unsafe-fixes"]),
    case(
        "fix_only=true",
        {"fix": "safe", "fix_only": True},
        ["--fix", "--no-unsafe-fixes", "--fix-only"],
    ),
    case("fixable", {"fixable": "F401,I001"}, expect("--fixable", "F401,I001")),
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
    case("ignore_noqa=true", {"ignore_noqa": True}, expect("--ignore-noqa")),
    case(
        "ignored_rules", {"ignored_rules": "E203,D203"}, expect("--ignore", "E203,D203")
    ),
    case("isolated=true", {"isolated": True}, expect("--isolated")),
    case(
        "line_length", {"line_length": "100"}, expect("--config", "line-length = 100")
    ),
    case("no_cache=true", {"no_cache": True}, expect("--no-cache")),
    case(
        "output_file",
        {"output_file": "reports/ruff.txt"},
        expect("--output-file", "reports/ruff.txt"),
        output=["Report reports/ruff.txt is empty."],
    ),
    case("output_format=default", {"output_format": "default"}, expect()),
    *[
        case(
            f"output_format={value}",
            {"output_format": value},
            expect("--output-format", value),
        )
        for value in (
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
    ],
    case(
        "per_file_ignores",
        {"per_file_ignores": "tests/*:S101"},
        expect("--per-file-ignores", "tests/*:S101"),
    ),
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
    case(
        "selected_rules",
        {"selected_rules": "E4,E7,E9,F"},
        expect("--select", "E4,E7,E9,F"),
    ),
    case("show_fixes=auto", {"show_fixes": "auto"}, expect()),
    case("show_fixes=enabled", {"show_fixes": "enabled"}, expect("--show-fixes")),
    case("show_fixes=disabled", {"show_fixes": "disabled"}, expect("--no-show-fixes")),
    case("statistics=true", {"statistics": True}, expect("--statistics")),
    case("target_version=default", {"target_version": "default"}, expect()),
    *[
        case(
            f"target_version={value}",
            {"target_version": value},
            expect("--target-version", value),
        )
        for value in (
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
    ],
    case(
        "targets",
        {"targets": "src tests\n-x"},
        expect(),
        paths=["src", "tests", "./-x"],
    ),
    case(
        "tee=true",
        {"output_file": "report.txt", "tee": True},
        expect("--output-file", "report.txt"),
        output=["Report report.txt is empty."],
    ),
    case(
        "tee=false",
        {"output_file": "report.txt", "tee": False},
        expect("--output-file", "report.txt"),
        no_output=["Report report.txt is empty."],
    ),
    case("unfixable", {"unfixable": "F401"}, expect("--unfixable", "F401")),
    case("verbosity=default", {"verbosity": "default"}, expect()),
    case("verbosity=verbose", {"verbosity": "verbose"}, expect("--verbose")),
    case("verbosity=quiet", {"verbosity": "quiet"}, expect("--quiet")),
    case("verbosity=silent", {"verbosity": "silent"}, expect("--silent")),
    # Values are passed as they are: not split, and nothing is evaluated.
    case(
        "values-not-evaluated",
        {"selected_rules": "$(echo F) E", "ignored_rules": "`id`", "fixable": "*"},
        expect("--select", "$(echo F) E", "--ignore", "`id`", "--fixable", "*"),
    ),
    # Every '--config' in its place, and extra_args after everything else.
    case(
        "config-order-and-extra-args",
        {
            "config_file": "ruff.toml",
            "config_overrides": "lint.ignore = []\nlint.select = []",
            "extra_args": "--extend-select D",
            "line_length": "40",
            "selected_rules": "F",
            "statistics": True,
        },
        expect(
            "--config",
            "ruff.toml",
            "--config",
            "lint.ignore = []",
            "--config",
            "lint.select = []",
            "--config",
            "line-length = 40",
            "--select",
            "F",
            "--statistics",
            "--extend-select",
            "D",
        ),
    ),
]

# The command refuses these before Ruff is started.
REFUSED_CASES = [
    {
        "name": "fix_only=true-with-fix=never",
        "parameters": {"fix_only": True},
        "message": "'fix_only' rewrites files, so it needs 'fix' set to "
        "'auto', 'safe' or 'unsafe'.",
    },
]


# ---------------------------------------------------------------------------
# The packed command
# ---------------------------------------------------------------------------


class Command:
    """The packed 'check' command: its parameters, environment and script."""

    def __init__(self, packed_path):
        import yaml

        orb = yaml.safe_load(pathlib.Path(packed_path).read_text(encoding="utf-8"))
        command = (orb.get("commands") or {}).get("check")

        if not isinstance(command, dict):
            raise SystemExit("The packed orb has no 'check' command.")

        runs = [s["run"] for s in command.get("steps") or [] if "run" in s]

        if len(runs) != 1 or not isinstance(runs[0], dict):
            raise SystemExit("The packed 'check' command is not a single 'run' step.")

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
                problems.append(f"'{key}' is not a parameter of ruff/check")
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
    """Run the packed step's script from DIRECTORY. Returns (status, output)."""
    script = directory.parent / f".{directory.name}.step.sh"
    script.write_text(command.script, encoding="utf-8")
    env = {**environment, **command.render(parameters)}

    with open(os.devnull, "rb") as stdin:
        result = subprocess.run(
            ["bash", "-eo", "pipefail", str(script)],
            cwd=directory,
            env=env,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
            check=False,
        )

    return result.returncode, result.stdout


def quoted_command(arguments):
    """The 'Command:' line check.sh prints for these arguments."""
    result = subprocess.run(
        ["bash", "-c", 'printf "Command:"; printf " %q" "$@"', "bash", *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def items(tokens):
    """Group options with their values: ['--select', 'F'] -> [('--select', 'F')]."""
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


# ---------------------------------------------------------------------------
# Argument cases
# ---------------------------------------------------------------------------


def run_argument_case(command, spec, scratch):
    failures = command.validate(spec["name"], spec["parameters"])

    if failures:
        return failures, {}

    directory = scratch / "argument"
    shutil.rmtree(directory, ignore_errors=True)
    (directory / "bin").mkdir(parents=True)
    work = directory / "work"
    work.mkdir()
    shutil.copy(RECORDER, directory / "bin" / "ruff")
    (directory / "bin" / "ruff").chmod(0o755)
    argv_file = directory / "argv"
    calls_file = directory / "calls"
    environment = base_environment(directory)
    environment["PATH"] = f"{directory / 'bin'}:{environment['PATH']}"
    environment["RECORD_RUFF_ARGV"] = str(argv_file)
    environment["RECORD_RUFF_CALLS"] = str(calls_file)

    status, output = run_step(command, spec["parameters"], work, environment)
    lines = output.splitlines()
    record = {"status": status, "output": output}

    if status != 0:
        failures.append(f"expected exit status 0, got {status}")

    if not argv_file.exists():
        failures.append("Ruff was not started for the check")
        return failures, record

    argv = argv_file.read_bytes().split(b"\0")[:-1]
    argv = [a.decode("utf-8") for a in argv]
    record["argv"] = argv

    if not argv or argv[0] != "check":
        failures.append(f"the first argument is not 'check': {argv[:1]}")
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

    # config_file, then the overrides in their order, then line_length.
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
        *(
            [f"line-length = {spec['parameters']['line_length']}"]
            if spec["parameters"].get("line_length")
            else []
        ),
    ]

    if config_values(options) != expected_config:
        failures.append(
            f"the --config values are {config_values(options)}, "
            f"expected {expected_config} in this order"
        )

    if quoted_command(["ruff", *argv]) not in lines:
        failures.append("the 'Command:' line does not show the arguments received")

    calls = calls_file.read_text(encoding="utf-8").splitlines()

    if len(calls) != 2 or calls[0] != "ruff --version ":
        failures.append(f"expected 'ruff --version' and one more call, got {calls}")

    if any(line.startswith("PARAM_") for line in lines):
        failures.append("the log prints a PARAM_ line")

    for line in spec["output"]:
        if line not in lines:
            failures.append(f"the output has no line {line!r}")

    for line in spec["no_output"]:
        if line in lines:
            failures.append(f"the output has the line {line!r}")

    return failures, record


def run_refused_case(command, spec, scratch):
    failures = command.validate(spec["name"], spec["parameters"])
    directory = scratch / "refused"
    shutil.rmtree(directory, ignore_errors=True)
    (directory / "bin").mkdir(parents=True)
    work = directory / "work"
    work.mkdir()
    (work / "target.py").write_text("import os\n", encoding="utf-8")
    shutil.copy(RECORDER, directory / "bin" / "ruff")
    (directory / "bin" / "ruff").chmod(0o755)
    environment = base_environment(directory)
    environment["PATH"] = f"{directory / 'bin'}:{environment['PATH']}"
    environment["RECORD_RUFF_ARGV"] = str(directory / "argv")
    environment["RECORD_RUFF_CALLS"] = str(directory / "calls")
    parameters = {**spec["parameters"], "targets": "target.py"}

    status, output = run_step(command, parameters, work, environment)

    if status != 1:
        failures.append(f"expected exit status 1, got {status}")

    if spec["message"] not in output.splitlines():
        failures.append(f"the output has no line {spec['message']!r}")

    if (directory / "calls").exists():
        failures.append("Ruff was started")

    if (work / "target.py").read_text(encoding="utf-8") != "import os\n":
        failures.append("target.py changed")

    return failures, {"status": status, "output": output}


# ---------------------------------------------------------------------------
# Ruff cases
# ---------------------------------------------------------------------------

UNUSED = "import os\n"
UNDEFINED = "print(undefined_name)\n"
CLEAN = 'print("clean")\n'
# I001 and F401: the imports are unsorted and 'os' is unused.
FIXABLE = "import sys\nimport os\nimport json\n\nprint(sys.path, json)\n"
# F841, whose fix Ruff counts as unsafe.
UNSAFE = "def f():\n    x = 1\n"
NOQA = "import os  # noqa: F401\n"
# E225, a preview rule in Ruff 0.16.2.
PREVIEW_ONLY = "x=1\n"


class RuffCase:
    """Helpers for one Ruff case. Every problem is collected in failures."""

    def __init__(self, command, scratch, name):
        self.command = command
        self.root = scratch / "ruff" / name
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        self.home = self.root / "home"
        self.home.mkdir()
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

    def run(self, directory, label, expected_status, **parameters):
        self.failures += self.command.validate(label, parameters)
        status, output = run_step(
            self.command, parameters, directory, base_environment(self.home)
        )
        self.runs.append(
            {"run": label, "parameters": parameters, "status": status, "output": output}
        )

        if status != expected_status:
            self.failures.append(
                f"{label}: expected exit status {expected_status}, got {status}"
            )

        return output.splitlines()

    def has_line(self, label, lines, line):
        if line not in lines:
            self.failures.append(f"{label}: the output has no line {line!r}")

    def has_match(self, label, lines, pattern):
        if not any(re.search(pattern, line) for line in lines):
            self.failures.append(f"{label}: no output line matches {pattern!r}")

    def lacks_match(self, label, lines, pattern):
        if any(re.search(pattern, line) for line in lines):
            self.failures.append(f"{label}: an output line matches {pattern!r}")

    def content(self, label, path, expected):
        actual = path.read_text(encoding="utf-8")

        if actual != expected:
            self.failures.append(
                f"{label}: {path.name} is {actual!r}, expected {expected!r}"
            )

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


def ruff_diff(c):
    d = c.directory("diff", {"fix.py": FIXABLE, "undefined.py": UNDEFINED})
    before = c.snapshot(d)
    lines = c.run(d, "diff with fixes", 1, diff=True, targets="fix.py")
    c.has_line("diff with fixes", lines, "--- fix.py")
    c.has_line("diff with fixes", lines, "+++ fix.py")
    c.has_line("diff with fixes", lines, "-import os")
    c.unchanged("diff with fixes", d, before)
    # Only a violation without a fix: there is no diff and nothing fails.
    lines = c.run(d, "diff without fixes", 0, diff=True, targets="undefined.py")
    c.lacks_match("diff without fixes", lines, r"^--- ")
    c.unchanged("diff without fixes", d, before)
    # output_file gets Ruff's summary only; the diff still goes to the log.
    lines = c.run(
        d,
        "diff with output_file",
        1,
        diff=True,
        output_file="diff.txt",
        targets="fix.py",
    )
    c.has_line("diff with output_file", lines, "-import os")
    c.content("diff with output_file", d / "diff.txt", "Would fix 2 errors.\n")
    before["diff.txt"] = c.snapshot(d)["diff.txt"]
    c.unchanged("diff with output_file", d, before)


def ruff_output_format_json(c):
    d = c.directory("json", {"unused.py": UNUSED, "undefined.py": UNDEFINED})
    c.run(d, "json", 1, output_format="json", output_file="report.json")

    try:
        findings = json.loads((d / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        c.failures.append(f"json: report.json is not JSON: {error}")
        return

    found = sorted(
        (
            pathlib.Path(f["filename"]).name,
            f["code"],
            f["location"]["row"],
            f["location"]["column"],
            (f.get("fix") or {}).get("applicability"),
        )
        for f in findings
    )
    expected = [
        ("undefined.py", "F821", 1, 7, None),
        ("unused.py", "F401", 1, 8, "safe"),
    ]

    if found != expected:
        c.failures.append(f"json: the findings are {found}, expected {expected}")

    clean = c.directory("json-clean", {"clean.py": CLEAN})
    c.run(clean, "json without findings", 0, output_format="json", output_file="r.json")

    if json.loads((clean / "r.json").read_text(encoding="utf-8")) != []:
        c.failures.append("json without findings: the report is not an empty list")


def ruff_extensions(c):
    d = c.directory("extensions", {"module.pya": UNUSED})
    c.run(d, "without extensions", 0)
    lines = c.run(
        d, "with extensions", 1, extensions="pya:python", output_format="concise"
    )
    c.has_match("with extensions", lines, r"^module\.pya:1:8: F401 ")


def ruff_fixable_and_unfixable(c):
    d = c.directory("fix-scope", {"a.py": FIXABLE})
    c.run(d, "fix safe", 0, fix="safe")
    c.content(
        "fix safe", d / "a.py", "import json\nimport sys\n\nprint(sys.path, json)\n"
    )
    (d / "a.py").write_text(FIXABLE, encoding="utf-8")
    lines = c.run(
        d, "fixable F401", 1, fix="safe", fixable="F401", output_format="concise"
    )
    c.content(
        "fixable F401", d / "a.py", "import sys\nimport json\n\nprint(sys.path, json)\n"
    )
    c.has_match("fixable F401", lines, r"^a\.py:1:1: I001 ")
    (d / "a.py").write_text(FIXABLE, encoding="utf-8")
    lines = c.run(
        d, "unfixable F401", 1, fix="safe", unfixable="F401", output_format="concise"
    )
    c.content(
        "unfixable F401",
        d / "a.py",
        "import json\nimport os\nimport sys\n\nprint(sys.path, json)\n",
    )
    c.has_match("unfixable F401", lines, r"^a\.py:2:8: F401 ")


def ruff_fix_safety(c):
    d = c.directory("fix-safety", {"v.py": UNSAFE})
    c.run(d, "safe leaves an unsafe fix", 1, fix="safe", selected_rules="F841")
    c.content("safe leaves an unsafe fix", d / "v.py", UNSAFE)
    c.run(d, "unsafe applies it", 0, fix="unsafe", selected_rules="F841")
    c.content("unsafe applies it", d / "v.py", "def f():\n    pass\n")


def ruff_ignore_noqa(c):
    d = c.directory("noqa", {"a.py": NOQA})
    c.run(d, "noqa honoured", 0)
    lines = c.run(d, "ignore_noqa", 1, ignore_noqa=True, output_format="concise")
    c.has_match("ignore_noqa", lines, r"^a\.py:1:8: F401 ")


def ruff_show_fixes(c):
    fixed = r"^Fixed \d+ errors?:$"
    listed = "    1 × I001 (unsorted-imports)"
    d = c.directory("show-fixes", {"a.py": FIXABLE})
    lines = c.run(d, "show_fixes enabled", 0, fix="safe", show_fixes="enabled")
    c.has_match("show_fixes enabled", lines, fixed)
    c.has_line("show_fixes enabled", lines, listed)
    configured = c.directory(
        "show-fixes-config", {"a.py": FIXABLE}, "show-fixes = true\n"
    )
    lines = c.run(configured, "show_fixes auto with the config", 0, fix="safe")
    c.has_match("show_fixes auto with the config", lines, fixed)
    (configured / "a.py").write_text(FIXABLE, encoding="utf-8")
    lines = c.run(
        configured,
        "show_fixes disabled with the config",
        0,
        fix="safe",
        show_fixes="disabled",
    )
    c.lacks_match("show_fixes disabled with the config", lines, fixed)


def ruff_preview(c):
    d = c.directory("preview", {"a.py": PREVIEW_ONLY})
    c.run(d, "preview auto", 0, selected_rules="E225")
    c.run(d, "preview enabled", 1, selected_rules="E225", preview="enabled")
    configured = c.directory(
        "preview-config", {"a.py": PREVIEW_ONLY}, "preview = true\n"
    )
    c.run(configured, "preview auto with the config", 1, selected_rules="E225")
    c.run(
        configured,
        "preview disabled with the config",
        0,
        selected_rules="E225",
        preview="disabled",
    )


def ruff_force_exclude(c):
    parameters = {"extend_excluded_paths": "skip.py", "targets": "skip.py"}
    d = c.directory("force-exclude", {"skip.py": UNUSED})
    c.run(d, "force_exclude auto", 1, **parameters)
    c.run(d, "force_exclude enabled", 0, force_exclude="enabled", **parameters)
    configured = c.directory(
        "force-exclude-config", {"skip.py": UNUSED}, "force-exclude = true\n"
    )
    c.run(configured, "force_exclude auto with the config", 0, **parameters)
    c.run(
        configured,
        "force_exclude disabled with the config",
        1,
        force_exclude="disabled",
        **parameters,
    )


def ruff_respect_gitignore(c):
    if shutil.which("git") is None:
        c.failures.append("git is needed for a repository with a .gitignore")
        return

    files = {".gitignore": "ignored.py\n", "ignored.py": UNUSED, "kept.py": CLEAN}

    for name, config in (
        ("gitignore", ""),
        ("gitignore-config", "respect-gitignore = false\n"),
    ):
        directory = c.directory(name, files, config)
        subprocess.run(["git", "init", "-q", str(directory)], check=True)

    d = c.root / "gitignore"
    configured = c.root / "gitignore-config"
    c.run(d, "respect_gitignore auto", 0)
    c.run(d, "respect_gitignore disabled", 1, respect_gitignore="disabled")
    c.run(configured, "respect_gitignore auto with the config", 1)
    c.run(
        configured,
        "respect_gitignore enabled with the config",
        0,
        respect_gitignore="enabled",
    )


def ruff_cache_dir(c):
    d = c.directory("cache-default", {"a.py": CLEAN})
    c.run(d, "cache default", 0)

    if not (d / ".ruff_cache" / "CACHEDIR.TAG").is_file():
        c.failures.append("cache default: no .ruff_cache in the project")

    elsewhere = c.root / "elsewhere"
    d = c.directory("cache-dir", {"a.py": CLEAN})
    c.run(d, "cache_dir", 0, cache_dir=str(elsewhere))

    if not (elsewhere / "CACHEDIR.TAG").is_file():
        c.failures.append("cache_dir: no cache in the named directory")

    if (d / ".ruff_cache").exists():
        c.failures.append("cache_dir: a .ruff_cache was still written in the project")


def ruff_excluded_paths(c):
    files = {"skip.py": UNUSED, "venv/inside.py": UNUSED, "ok.py": CLEAN}
    d = c.directory("excluded", files)
    lines = c.run(d, "default exclusions", 1, output_format="concise")
    c.has_match("default exclusions", lines, r"^skip\.py:1:8: F401 ")
    c.lacks_match("default exclusions", lines, r"^venv/inside\.py:")
    lines = c.run(
        d, "excluded_paths", 1, excluded_paths="skip.py", output_format="concise"
    )
    c.lacks_match("excluded_paths", lines, r"^skip\.py:")
    c.has_match("excluded_paths", lines, r"^venv/inside\.py:1:8: F401 ")
    c.run(d, "extend_excluded_paths", 0, extend_excluded_paths="skip.py")


def ruff_exit_statuses(c):
    d = c.directory("exit", {"clean.py": CLEAN, "bad.py": UNUSED, "fix.py": FIXABLE})
    before = c.snapshot(d)
    c.run(d, "clean", 0, targets="clean.py")
    c.run(d, "violation", 1, targets="bad.py")
    c.run(d, "configuration error", 2, config_file="missing.toml", targets="clean.py")
    lines = c.run(d, "refused", 1, fix_only=True, targets="fix.py")
    c.lacks_match("refused", lines, rf"^ruff {re.escape(RUFF_VERSION)}")
    c.unchanged("violation, configuration error and refusal", d, before)
    c.run(d, "allowed fix", 0, fix="safe", targets="fix.py")
    c.content(
        "allowed fix",
        d / "fix.py",
        "import json\nimport sys\n\nprint(sys.path, json)\n",
    )


RUFF_CASES = [
    ("ruff-diff", ruff_diff),
    ("ruff-output-format-json", ruff_output_format_json),
    ("ruff-extensions", ruff_extensions),
    ("ruff-fixable-and-unfixable", ruff_fixable_and_unfixable),
    ("ruff-fix-safety", ruff_fix_safety),
    ("ruff-ignore-noqa", ruff_ignore_noqa),
    ("ruff-show-fixes", ruff_show_fixes),
    ("ruff-preview", ruff_preview),
    ("ruff-force-exclude", ruff_force_exclude),
    ("ruff-respect-gitignore", ruff_respect_gitignore),
    ("ruff-cache-dir", ruff_cache_dir),
    ("ruff-excluded-paths", ruff_excluded_paths),
    ("ruff-exit-statuses", ruff_exit_statuses),
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


def table(command):
    if not TABLE.is_file():
        return [f"table: {TABLE.name} does not exist"]

    failures = []
    rows = re.findall(
        r"^\|\s*`([a-z_]+)`\s*\|", TABLE.read_text(encoding="utf-8"), re.MULTILINE
    )

    for name in sorted({row for row in rows if rows.count(row) > 1}):
        failures.append(f"table: {name} has more than one row")

    for name in sorted(set(command.parameters) - set(rows)):
        failures.append(f"table: {name} has no row in {TABLE.name}")

    for name in sorted(set(rows) - set(command.parameters)):
        failures.append(f"table: {name} is not a parameter of ruff/check")

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
    header = re.compile(
        r"^----- (?:(?:check|format) )?(\S+) \(exit status \d+\) -----$"
    )
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
        f"SHA-256 of the check script: {hashlib.sha256(command.script.encode()).hexdigest()}"
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

        version = subprocess.run(
            ["ruff", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip()
        print(f"\nRuff cases ({len(RUFF_CASES)}) with {version}:")

        if version != f"ruff {RUFF_VERSION}":
            failures.append(
                f"Ruff cases need ruff {RUFF_VERSION} on PATH, found {version!r}"
            )
        else:
            for name, function in RUFF_CASES:
                ruff_case = RuffCase(command, scratch, name)
                function(ruff_case)
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
