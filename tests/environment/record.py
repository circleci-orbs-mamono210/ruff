"""Record the environment a CircleCI job of this repository ran in.

Usage:

    python3 tests/environment/record.py [--ruff-version VERSION] DIRECTORY

Writes DIRECTORY/<CIRCLE_JOB>.json and prints the same facts. The record ties
the results and artifacts of a job to the commit and the job they came from,
and says what the job ran on:

- the commit, the job and its URL, the workflow and the pipeline, from the
  CIRCLE_* variables that CircleCI sets;
- the image: the Python version, PYTHON_VERSION as the cimg/python images set
  it, and the operating system from /etc/os-release. The 'Spin up
  environment' step of the job, behind the job URL, names the image itself;
- Ruff: the output of 'ruff --version' and where Ruff was found;
- the CPU and memory limits of the container, read from its cgroup, which is
  where a resource class takes effect, and the CPU count and memory of the
  host, which a resource class does not change.

Only the variables named in CIRCLE_VARIABLES and PYTHON_VERSION are read from
the environment. Nothing else is copied, so no secret can reach the record.

With --ruff-version, it exits 1 unless 'ruff --version' prints exactly
'ruff VERSION'. The record is written in either case.
tests/environment/compare.py compares the records of the executor tests with
the configuration that asked for them.
"""

import argparse
import hashlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys

CIRCLE_VARIABLES = (
    "CIRCLE_BRANCH",
    "CIRCLE_BUILD_NUM",
    "CIRCLE_BUILD_URL",
    "CIRCLE_JOB",
    "CIRCLE_PIPELINE_ID",
    "CIRCLE_PROJECT_REPONAME",
    "CIRCLE_PROJECT_USERNAME",
    "CIRCLE_SHA1",
    "CIRCLE_TAG",
    "CIRCLE_WORKFLOW_ID",
    "CIRCLE_WORKFLOW_JOB_ID",
)
CGROUP_ROOT = pathlib.Path("/sys/fs/cgroup")
# cgroup v1 reports "no limit" as a number close to 2**63.
NO_LIMIT_V1 = 2**62


def read(path):
    """The stripped text of a file, or None when it cannot be read."""
    try:
        return pathlib.Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def parse_cpu_max(text):
    """CPUs from a cgroup v2 cpu.max such as '200000 100000', or None."""
    fields = (text or "").split()

    if len(fields) != 2 or not all(field.isdigit() for field in fields):
        return None

    quota, period = (int(field) for field in fields)
    return quota / period if quota > 0 and period > 0 else None


def own_cgroup_v2():
    """The path of this process in the cgroup v2 hierarchy, '/' if unknown."""
    for line in (read("/proc/self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            return line[3:] or "/"

    return "/"


def cgroup_limits():
    """CPU and memory limits from the cgroup, the tightest one on the path.

    A limit can be set on the job's own cgroup or on one above it, so every
    directory from the own cgroup up to the visible root is read.
    """
    if (CGROUP_ROOT / "cgroup.controllers").exists():
        version = 2
        own = (CGROUP_ROOT / own_cgroup_v2().lstrip("/")).resolve()

        if not own.is_dir() or not own.is_relative_to(CGROUP_ROOT):
            own = CGROUP_ROOT

        directories = [own, *own.parents]
        directories = directories[: directories.index(CGROUP_ROOT) + 1]
        files = []
        cpus = []
        memories = []

        for directory in directories:
            cpu_max = read(directory / "cpu.max")
            memory_max = read(directory / "memory.max")

            if cpu_max is None and memory_max is None:
                continue

            files.append(
                {
                    "directory": str(directory),
                    "cpu.max": cpu_max,
                    "memory.max": memory_max,
                }
            )

            if parse_cpu_max(cpu_max) is not None:
                cpus.append(parse_cpu_max(cpu_max))

            if memory_max is not None and memory_max.isdigit():
                memories.append(int(memory_max))
    else:
        version = 1
        quota = read(CGROUP_ROOT / "cpu" / "cpu.cfs_quota_us")
        period = read(CGROUP_ROOT / "cpu" / "cpu.cfs_period_us")
        limit = read(CGROUP_ROOT / "memory" / "memory.limit_in_bytes")
        files = [
            {
                "cpu.cfs_quota_us": quota,
                "cpu.cfs_period_us": period,
                "memory.limit_in_bytes": limit,
            }
        ]
        cpus = [parse_cpu_max(f"{quota} {period}")]
        cpus = [cpu for cpu in cpus if cpu is not None]
        memories = [int(limit)] if limit and limit.isdigit() else []
        memories = [memory for memory in memories if memory < NO_LIMIT_V1]

    return {
        "cgroup_version": version,
        "cpu_limit": min(cpus) if cpus else None,
        "memory_limit": min(memories) if memories else None,
        "files": files,
    }


def os_release():
    """NAME, ID, VERSION_ID and PRETTY_NAME from /etc/os-release."""
    fields = {}

    for line in (read("/etc/os-release") or "").splitlines():
        key, separator, value = line.partition("=")

        if separator and key in ("ID", "NAME", "PRETTY_NAME", "VERSION_ID"):
            fields[key] = value.strip().strip('"')

    return fields


def host():
    """The CPU count and memory of the machine, not of the container."""
    memory = None

    for line in (read("/proc/meminfo") or "").splitlines():
        if line.startswith("MemTotal:") and line.split()[1].isdigit():
            memory = int(line.split()[1]) * 1024

    return {"cpu_count": os.cpu_count(), "memory_total": memory}


def ruff():
    """The output of 'ruff --version' and the path of the Ruff found."""
    path = shutil.which("ruff")

    if path is None:
        return {"path": None, "version": None}

    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"path": path, "version": None, "error": str(error)}

    return {"path": path, "version": result.stdout.strip() or None}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("directory", type=pathlib.Path)
    parser.add_argument("--ruff-version", default=None)
    arguments = parser.parse_args()

    circle = {name: os.environ.get(name) for name in CIRCLE_VARIABLES}
    job = circle["CIRCLE_JOB"] or "local"
    record = {
        "circleci": circle,
        "image": {
            "PYTHON_VERSION": os.environ.get("PYTHON_VERSION"),
            "os_release": os_release(),
        },
        "python": {
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "ruff": ruff(),
        "limits": cgroup_limits(),
        "host": host(),
    }

    arguments.directory.mkdir(parents=True, exist_ok=True)
    path = arguments.directory / f"{job}.json"
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")

    limits = record["limits"]
    print(f"Commit:   {circle['CIRCLE_SHA1']}")
    print(f"Job:      {job} #{circle['CIRCLE_BUILD_NUM']} {circle['CIRCLE_BUILD_URL']}")
    print(f"Workflow: {circle['CIRCLE_WORKFLOW_ID']}")
    print(
        f"Python:   {record['python']['version']} ({sys.executable}), "
        f"PYTHON_VERSION={record['image']['PYTHON_VERSION']}"
    )
    print(f"System:   {record['image']['os_release'].get('PRETTY_NAME')}")
    print(f"Ruff:     {record['ruff']['version']} ({record['ruff']['path']})")
    cpu = limits["cpu_limit"]
    memory = limits["memory_limit"]
    print(
        f"Limits:   CPU {'not visible' if cpu is None else f'{cpu:g}'}, memory "
        f"{'not visible' if memory is None else f'{memory} bytes'} "
        f"(cgroup v{limits['cgroup_version']})"
    )

    for entry in limits["files"]:
        print(f"          {json.dumps(entry, sort_keys=True)}")

    print(
        f"Host:     {record['host']['cpu_count']} CPUs, "
        f"{record['host']['memory_total']} bytes of memory"
    )
    print(f"Written:  {path} (SHA-256 {hashlib.sha256(text.encode()).hexdigest()})")

    expected = arguments.ruff_version

    if expected is not None and record["ruff"]["version"] != f"ruff {expected}":
        print(
            f"FAIL: expected 'ruff {expected}', "
            f"but 'ruff --version' printed {record['ruff']['version']!r}"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
