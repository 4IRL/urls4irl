"""Policy lint for .mise.toml, run by `make mise-config-check` from the repo root.

Fails unless .mise.toml is pin-only (min_version + plain `[tools] name = "version"`
pins) and both Dockerfiles' `ARG PNPM_VERSION=` equals the [tools] pnpm pin.
"""

from __future__ import annotations

import re
import sys
import tomllib

MISE_CONFIG_PATH: str = ".mise.toml"
DOCKERFILE_PATHS: tuple[str, ...] = ("docker/Dockerfile.Vite", "docker/Dockerfile")
PNPM_ARG_PATTERN: re.Pattern[str] = re.compile(r"^ARG PNPM_VERSION=(\S+)$", re.M)


def find_non_pin_config(mise_config: dict) -> list[str]:
    tools = mise_config.get("tools", {})
    disallowed_keys = sorted(set(mise_config) - {"min_version", "tools"})
    if not isinstance(tools, dict):
        return disallowed_keys + ["tools"]
    return disallowed_keys + sorted(
        "tools." + tool_name
        for tool_name, tool_version in tools.items()
        if not isinstance(tool_version, str)
    )


def read_pnpm_arg(dockerfile_path: str) -> str:
    with open(dockerfile_path) as dockerfile:
        match = PNPM_ARG_PATTERN.search(dockerfile.read())
    return match.group(1) if match else "MISSING"


def main() -> None:
    with open(MISE_CONFIG_PATH, "rb") as mise_file:
        mise_config = tomllib.load(mise_file)

    non_pin_config = find_non_pin_config(mise_config)
    if non_pin_config:
        sys.exit(
            ".mise.toml has non-version-pin config ("
            + ", ".join(non_pin_config)
            + "); only min_version and plain [tools] version pins are allowed"
        )

    pnpm_pin = mise_config.get("tools", {}).get("pnpm")
    mismatches = {
        dockerfile_path: arg_version
        for dockerfile_path in DOCKERFILE_PATHS
        if (arg_version := read_pnpm_arg(dockerfile_path)) != pnpm_pin
    }
    if mismatches:
        sys.exit(
            "ARG PNPM_VERSION mismatch (.mise.toml pnpm="
            + str(pnpm_pin)
            + "): "
            + ", ".join(
                dockerfile_path + "=" + arg_version
                for dockerfile_path, arg_version in mismatches.items()
            )
        )


if __name__ == "__main__":
    main()
