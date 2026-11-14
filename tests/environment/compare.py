"""Check that the executor tests ran where their configuration put them.

Usage:

    python3 tests/environment/compare.py PACKED_ORB CONFIG RECORDS OUTPUT

PACKED_ORB is the orb.yml that orb-tools/pack built from this commit, CONFIG
is .circleci/test-deploy.yml, and RECORDS is a directory holding the records
that tests/environment/record.py wrote in the jobs. The comparison is printed
and written to OUTPUT/executors.json. PyYAML is required.

1. The 'default' executor of the packed orb must start a single image, given
   by its 'image' parameter, with the resource class given by its
   'resource_class' parameter. These two parameters therefore decide where a
   job runs, and their defaults are read from the packed orb.
2. Each record must come from a job in CONFIG that uses that executor. What
   the job asked for is the executor's defaults with the job's own arguments
   on top, which is the configuration as CircleCI processes it.
3. The records must include a job that leaves both parameters at their
   defaults, one that passes a different image and one that passes a
   different resource class. They must come from one commit and one
   pipeline, and from the commit and pipeline of the job running this script
   when CIRCLE_SHA1 and CIRCLE_PIPELINE_ID are set. The workflow is not
   compared, because rerunning failed jobs starts a new workflow in the same
   pipeline.
4. Every image must be cimg/python:<version>, and the Python version a job
   recorded must start with that version, so a job that started another image
   is caught.
5. The CPU and memory limits must follow the resource classes: equal within a
   class, and larger for a larger class. The CPU limit has to be visible in
   every record. The memory limit is compared when every record shows one,
   and the output says so when none does. The values themselves are not
   compared with fixed numbers, because they depend on the CircleCI plan.

It exits 1 if any check fails.
"""

import itertools
import json
import os
import pathlib
import re
import sys

import yaml

EXECUTOR = "ruff/default"
# CircleCI's Docker resource classes, smallest first.
RESOURCE_CLASSES = (
    "small",
    "medium",
    "medium+",
    "large",
    "xlarge",
    "2xlarge",
    "2xlarge+",
)
IMAGE = re.compile(r"cimg/python:(\d+(?:\.\d+){1,2})(?:-[A-Za-z0-9.]+)?")


def parameter_of(value):
    """Return NAME for a value that is exactly '<<parameters.NAME>>'."""
    match = re.fullmatch(r"<<\s*parameters\.([A-Za-z0-9_-]+)\s*>>", str(value))
    return match.group(1) if match else None


def executor_defaults(orb, failures):
    """Check 1. Returns the defaults of 'image' and 'resource_class'."""
    executor = (orb.get("executors") or {}).get("default")

    if not isinstance(executor, dict):
        failures.append("the packed orb has no 'default' executor")
        return None

    docker = executor.get("docker")

    if (
        not isinstance(docker, list)
        or len(docker) != 1
        or not isinstance(docker[0], dict)
    ):
        failures.append("the 'default' executor does not start exactly one image")
    elif parameter_of(docker[0].get("image")) != "image":
        failures.append(
            f"the image of the 'default' executor is {docker[0].get('image')!r}, "
            "not the 'image' parameter"
        )

    if parameter_of(executor.get("resource_class")) != "resource_class":
        failures.append(
            "the resource class of the 'default' executor is "
            f"{executor.get('resource_class')!r}, not the 'resource_class' parameter"
        )

    parameters = executor.get("parameters") or {}
    defaults = {}

    for name in ("image", "resource_class"):
        if "default" not in (parameters.get(name) or {}):
            failures.append(f"the 'default' executor has no default for '{name}'")
            return None

        defaults[name] = str(parameters[name]["default"])

    return defaults


def requested(config, defaults, failures):
    """Check 2. What every job that uses the executor asked for."""
    jobs = {}

    for name, job in (config.get("jobs") or {}).items():
        executor = job.get("executor") if isinstance(job, dict) else None

        if executor == EXECUTOR:
            arguments = {}
        elif isinstance(executor, dict) and executor.get("name") == EXECUTOR:
            arguments = {k: str(v) for k, v in executor.items() if k != "name"}
        else:
            continue

        unknown = set(arguments) - set(defaults)

        if unknown:
            failures.append(f"{name}: unknown executor arguments {sorted(unknown)}")

        jobs[name] = {
            "arguments": arguments,
            "image": arguments.get("image", defaults["image"]),
            "resource_class": arguments.get(
                "resource_class", defaults["resource_class"]
            ),
        }

    return jobs


def load_records(directory, failures):
    records = {}

    for path in sorted(pathlib.Path(directory).glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            failures.append(f"{path.name}: cannot be read: {error}")
            continue

        job = (record.get("circleci") or {}).get("CIRCLE_JOB")

        if job != path.stem:
            failures.append(f"{path.name}: the record is for job {job!r}")
            continue

        records[job] = record

    return records


def check_origin(records, failures):
    """Check 3, second half: one commit and one pipeline."""
    for key, variable in (
        ("commit", "CIRCLE_SHA1"),
        ("pipeline", "CIRCLE_PIPELINE_ID"),
    ):
        values = {
            job: record["circleci"].get(variable) for job, record in records.items()
        }
        found = set(values.values())
        current = os.environ.get(variable)

        if None in found or len(found) != 1:
            failures.append(f"the records do not share one {key}: {values}")
        elif current and found != {current}:
            failures.append(
                f"the records are from {key} {found.pop()}, "
                f"but this job runs for {current}"
            )


def check_python(job, wanted, record, failures):
    """Check 4."""
    match = IMAGE.fullmatch(wanted["image"])
    observed = record["python"].get("version") or ""

    if not match:
        failures.append(
            f"{job}: cannot tell which Python {wanted['image']} has; "
            "use a cimg/python image"
        )
        return False

    expected = match.group(1).split(".")

    if observed.split(".")[: len(expected)] != expected:
        failures.append(
            f"{job}: asked for {wanted['image']}, "
            f"but ran Python {observed or 'unknown'}"
        )
        return False

    return True


def check_limits(jobs, records, failures, notes):
    """Check 5."""
    classes = {}

    for job, record in records.items():
        resource_class = jobs[job]["resource_class"]

        if resource_class not in RESOURCE_CLASSES:
            failures.append(f"{job}: unknown resource class {resource_class!r}")
            continue

        limits = record.get("limits") or {}

        if limits.get("cpu_limit") is None:
            failures.append(
                f"{job}: the CPU limit is not visible in the cgroup: "
                f"{json.dumps(limits.get('files'))}"
            )

        classes.setdefault(resource_class, []).append(
            (job, limits.get("cpu_limit"), limits.get("memory_limit"))
        )

    memories = [memory for entries in classes.values() for _, _, memory in entries]

    if memories and all(memory is None for memory in memories):
        notes.append(
            "No record shows a memory limit, so only the CPU limits were compared."
        )
        compare_memory = False
    elif any(memory is None for memory in memories):
        failures.append(
            "some records show a memory limit and some do not: "
            + ", ".join(
                f"{job}={memory}"
                for entries in classes.values()
                for job, _, memory in entries
            )
        )
        compare_memory = False
    else:
        compare_memory = True

    ordered = sorted(classes, key=RESOURCE_CLASSES.index)
    kinds = [("CPU", 1)] + ([("memory", 2)] if compare_memory else [])

    for kind, index in kinds:
        for resource_class in ordered:
            values = {entry[0]: entry[index] for entry in classes[resource_class]}

            if None not in values.values() and len(set(values.values())) != 1:
                failures.append(
                    f"the {kind} limits differ within resource class "
                    f"{resource_class}: {values}"
                )

        for smaller, larger in itertools.pairwise(ordered):
            low = [
                entry[index] for entry in classes[smaller] if entry[index] is not None
            ]
            high = [
                entry[index] for entry in classes[larger] if entry[index] is not None
            ]

            if low and high and not max(low) < min(high):
                failures.append(
                    f"the {kind} limit of resource class {larger} ({min(high)}) is "
                    f"not larger than that of {smaller} ({max(low)})"
                )

    return ordered


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        return 2

    orb_path, config_path, records_path, output = (
        pathlib.Path(a) for a in sys.argv[1:]
    )
    failures = []
    notes = []

    orb = yaml.safe_load(orb_path.read_text(encoding="utf-8")) or {}
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    defaults = executor_defaults(orb, failures)

    if defaults is None:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(
        f"Packed executor '{EXECUTOR}': image from 'image' (default {defaults['image']}), "
        f"resource class from 'resource_class' (default {defaults['resource_class']})"
    )

    jobs = requested(config, defaults, failures)
    records = load_records(records_path, failures)

    for job in sorted(set(records) - set(jobs)):
        failures.append(f"{job}: no job of that name in {config_path} uses {EXECUTOR}")
        del records[job]

    wanted = {job: jobs[job] for job in records}
    coverage = {
        "the default image and resource class": [
            job
            for job, entry in wanted.items()
            if entry["image"] == defaults["image"]
            and entry["resource_class"] == defaults["resource_class"]
        ],
        "a non-default image": [
            job for job, entry in wanted.items() if entry["image"] != defaults["image"]
        ],
        "a non-default resource class": [
            job
            for job, entry in wanted.items()
            if entry["resource_class"] != defaults["resource_class"]
        ],
    }

    for description, covered in coverage.items():
        if not covered:
            failures.append(f"no record of a job with {description}")

    if records:
        check_origin(records, failures)

    summary = []

    for job in sorted(records):
        record = records[job]
        python_ok = check_python(job, wanted[job], record, failures)
        limits = record.get("limits") or {}
        summary.append(
            {
                "job": job,
                "build_url": record["circleci"].get("CIRCLE_BUILD_URL"),
                "commit": record["circleci"].get("CIRCLE_SHA1"),
                "arguments": wanted[job]["arguments"],
                "image": wanted[job]["image"],
                "resource_class": wanted[job]["resource_class"],
                "python": record["python"].get("version"),
                "python_matches_image": python_ok,
                "os": (record.get("image") or {})
                .get("os_release", {})
                .get("PRETTY_NAME"),
                "ruff": (record.get("ruff") or {}).get("version"),
                "cpu_limit": limits.get("cpu_limit"),
                "memory_limit": limits.get("memory_limit"),
            }
        )

    ordered = check_limits(wanted, records, failures, notes) if records else []

    print()
    print("Job, arguments, processed image and resource class, what the job recorded:")

    for entry in summary:
        print(f"- {entry['job']} ({entry['build_url']})")
        print(f"    arguments:      {entry['arguments'] or 'none'}")
        print(
            f"    image:          {entry['image']} -> Python {entry['python']}, {entry['os']}"
        )
        print(
            f"    resource class: {entry['resource_class']} -> CPU limit "
            f"{entry['cpu_limit']}, memory limit {entry['memory_limit']}"
        )
        print(f"    Ruff:           {entry['ruff']}")

    print()
    print(f"Resource classes, smallest first: {', '.join(ordered) or 'none'}")

    for description, covered in coverage.items():
        print(f"Covers {description}: {', '.join(covered) or 'no job'}")

    for note in notes:
        print(f"Note: {note}")

    output.mkdir(parents=True, exist_ok=True)
    (output / "executors.json").write_text(
        json.dumps(
            {
                "executor_defaults": defaults,
                "jobs": summary,
                "notes": notes,
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if failures:
        print()
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("Every executor test ran on the image and resource class it asked for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
