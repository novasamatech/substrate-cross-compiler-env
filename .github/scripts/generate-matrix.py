#!/usr/bin/env python3
"""Generate a GitHub Actions job matrix from the build profiles in config.yml.

Each selected profile is expanded into the cartesian product of the requested
dimensions; ``code_git_repo`` and ``code_git_ref`` are carried into every entry
so jobs know which source tree the combination belongs to.

The result is written as ``matrix=<json>`` to ``$GITHUB_OUTPUT`` when running in
GitHub Actions, and to stdout otherwise, which makes the script runnable locally:

    ./.github/scripts/generate-matrix.py --dimensions debian-versions,rust-versions
"""

import argparse
import itertools
import json
import os
import sys

import yaml

# Profile fields copied into every matrix entry instead of being expanded
METADATA_KEYS = ["code_git_repo", "code_git_ref"]


def fail(message):
    print(f"::error::{message}", file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config.yml",
        help="path to the build profile config (default: config.yml)",
    )
    parser.add_argument(
        "--builds",
        default="all",
        help="'all' or a comma-separated list of profile names (default: all)",
    )
    parser.add_argument(
        "--dimensions",
        required=True,
        help="comma-separated profile fields to expand into matrix entries",
    )
    return parser.parse_args()


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    except OSError as error:
        fail(f"Cannot read {path}: {error}")
    except yaml.YAMLError as error:
        fail(f"Cannot parse {path}: {error}")

    if not isinstance(config, dict) or not config:
        fail(f"{path} must be a non-empty map of build profiles")

    return config


def select_builds(config, builds):
    requested = (builds or "all").strip()
    if requested == "all":
        selected = list(config.keys())
    else:
        selected = [build.strip() for build in requested.split(",") if build.strip()]

    if not selected:
        fail("No builds selected")

    unknown_builds = [build for build in selected if build not in config]
    if unknown_builds:
        allowed_builds = ",".join(config.keys())
        fail(
            f"Unknown build(s): {','.join(unknown_builds)}. Allowed values: {allowed_builds}"
        )

    return selected


def build_matrix(config, selected_builds, dimensions):
    matrix = []
    for build_name in selected_builds:
        item = config[build_name]
        if not isinstance(item, dict):
            fail(f"Build '{build_name}' must be a map")

        missing_keys = [key for key in METADATA_KEYS + dimensions if key not in item]
        if missing_keys:
            fail(f"Build '{build_name}' is missing keys: {','.join(missing_keys)}")

        for key in dimensions:
            if not isinstance(item[key], list) or not item[key]:
                fail(f"Build '{build_name}' field '{key}' must be a non-empty list")

        for combination in itertools.product(*(item[key] for key in dimensions)):
            entry = {key: item[key] for key in METADATA_KEYS}
            entry.update(dict(zip(dimensions, (str(value) for value in combination))))
            matrix.append(entry)

    return matrix


def main():
    args = parse_args()

    dimensions = [key.strip() for key in args.dimensions.split(",") if key.strip()]
    if not dimensions:
        fail("No dimensions requested")

    config = load_config(args.config)
    selected_builds = select_builds(config, args.builds)
    matrix = build_matrix(config, selected_builds, dimensions)

    payload = f"matrix={json.dumps({'include': matrix}, separators=(',', ':'))}"
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            output.write(f"{payload}\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
