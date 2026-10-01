"""Exact-pin audit, run by `make audit-pins` (and `make lint`) from the repo root.

Fails unless every dependency surface pins an exact version:
requirements/*.txt (`name==X.Y.Z`), frontend/package.json dependency sections,
frontend/pnpm-workspace.yaml (overrides, peerDependencyRules.allowedVersions,
minimumReleaseAgeExclude), .mise.toml [tools], Dockerfile FROM images,
`ARG *_VERSION=` defaults and `pip install` packages, compose `image:` values,
and workflow/composite-action `uses:` refs, `services:`/`container:` images and
`pip install`s. Flow-style YAML in an audited block is reported, not parsed.

Image tags pass when they start with an exact X.Y.Z (optional leading `v`), are
a two-part X.Y for images in TWO_PART_VERSION_IMAGES, or pin `@sha256:`. Our
own registry images (OWN_IMAGE_PREFIXES) are allowlisted.

Deliberately out of scope: apt packages, `runs-on:`, `# syntax=` directives,
pnpm-lock.yaml (already guaranteed by `--frozen-lockfile`), and `.sh` files
such as docker/smoke-test.sh (their image tags are pinned by hand).
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

TWO_PART_VERSION_IMAGES: tuple[str, ...] = ("debian", "postgres")
OWN_IMAGE_PREFIXES: tuple[str, ...] = ("ghcr.io/4irl/",)
PACKAGE_JSON_SECTIONS: tuple[str, ...] = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
)
PNPM_VERSIONED_BLOCKS: tuple[str, ...] = (
    "overrides",
    "peerDependencyRules",
    "minimumReleaseAgeExclude",
)
PIP_OPTIONS_WITH_VALUE: frozenset[str] = frozenset(
    {
        "-r",
        "--requirement",
        "-c",
        "--constraint",
        "-e",
        "--editable",
        "-i",
        "--index-url",
        "--extra-index-url",
        "-f",
        "--find-links",
        "-t",
        "--target",
        "--prefix",
        "--root",
        "--src",
        "--cache-dir",
        "--trusted-host",
        "--platform",
        "--python-version",
        "--implementation",
        "--abi",
        "--upgrade-strategy",
        "--progress-bar",
        "--log",
    }
)

EXACT_SEMVER: re.Pattern[str] = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
EXACT_TOOL_VERSION: re.Pattern[str] = re.compile(r"^\d+\.\d+\.\d+$")
EXACT_ARG_VERSION: re.Pattern[str] = re.compile(r"^v?\d+\.\d+\.\d+$")
EXACT_TAG: re.Pattern[str] = re.compile(r"^v?\d+\.\d+\.\d+(?![.\d])")
TWO_PART_TAG: re.Pattern[str] = re.compile(r"^\d+\.\d+(?![.\d])")
PIP_REQUIREMENT: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9,._-]+\])?==[0-9][0-9A-Za-z.+!_-]*$"
)
PIP_INSTALL: re.Pattern[str] = re.compile(
    r"\bpip(?:\d+(?:\.\d+)?)?\s+install\b(?P<arguments>[^&|;]*)"
)
PNPM_EXCLUDE_ENTRY: re.Pattern[str] = re.compile(r"^(?P<name>@?[^@]+)@(?P<version>.+)$")
ACTION_SHA_REF: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$"
)
DOCKER_ARG: re.Pattern[str] = re.compile(r"^ARG\s+(?P<name>\w+)(?:=(?P<default>\S*))?")
DOCKER_ARG_REFERENCE: re.Pattern[str] = re.compile(
    r"\$\{(?P<braced>\w+)(?::-(?P<fallback>[^}]*))?\}|\$(?P<bare>\w+)"
)
USES_LINE: re.Pattern[str] = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<ref>\S+)")
IMAGE_LINE: re.Pattern[str] = re.compile(r"^\s*(?:-\s+)?image:\s*(?P<image>\S+)")
IMAGE_BLOCK_LINE: re.Pattern[str] = re.compile(
    r"^\s*(?:services|container):\s*(?P<inline>.*)$"
)
FLOW_STYLE_YAML: re.Pattern[str] = re.compile(r"^\s*-?\s*[\[{]")


def _finding(path: str, line_number: int, message: str) -> str:
    return f"{path}:{line_number}: {message}"


def _strip_quotes(value: str) -> str:
    return value.strip().strip("\"'")


def _strip_yaml_comment(line: str) -> str:
    return re.split(r"\s+#", line, maxsplit=1)[0].rstrip()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_code(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def image_problem(image: str) -> str | None:
    """Return why `image` is not exactly pinned, or None when it is."""
    if "@sha256:" in image or image.startswith(OWN_IMAGE_PREFIXES):
        return None
    name, separator, tag = image.rpartition(":")
    if not separator or "/" in tag:
        return f"image {image} has no tag (pin an exact version)"
    short_name = name.removeprefix("docker.io/").removeprefix("library/")
    if EXACT_TAG.match(tag):
        return None
    if short_name in TWO_PART_VERSION_IMAGES and TWO_PART_TAG.match(tag):
        return None
    return f"image {image} is not pinned to an exact version tag"


def pip_install_problems(command: str) -> list[tuple[int, str]]:
    """(offset, message) for every unpinned package in each `pip install` of `command`."""
    problems: list[tuple[int, str]] = []
    for install_match in PIP_INSTALL.finditer(command):
        tokens = install_match.group("arguments").split()
        skip_next = False
        for token in tokens:
            if skip_next:
                skip_next = False
                continue
            if token in PIP_OPTIONS_WITH_VALUE:
                skip_next = True
                continue
            if token.startswith("-"):
                continue
            requirement = _strip_quotes(token)
            if not PIP_REQUIREMENT.match(requirement):
                problems.append(
                    (
                        install_match.start(),
                        f"pip install {requirement} is not an exact pin (use name==X.Y.Z)",
                    )
                )
    return problems


def check_requirements(text: str, path: str) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        requirement = line.split("#", 1)[0].strip()
        if not requirement or requirement.startswith(("-r ", "-c ")):
            continue
        requirement = requirement.split(";", 1)[0].strip()
        if not PIP_REQUIREMENT.match(requirement):
            findings.append(
                _finding(
                    path,
                    line_number,
                    f"{requirement} is not an exact pin (use name==X.Y.Z)",
                )
            )
    return findings


def check_package_json(text: str, path: str) -> list[str]:
    manifest = json.loads(text)
    if not isinstance(manifest, dict):
        return [_finding(path, 1, "top level is not a JSON object")]
    lines = text.splitlines()
    findings: list[str] = []
    for section in PACKAGE_JSON_SECTIONS:
        dependencies = manifest.get(section, {})
        section_key = json.dumps(section) + ":"
        section_line = next(
            (
                index
                for index, line in enumerate(lines, start=1)
                if line.strip().startswith(section_key)
            ),
            1,
        )
        if not isinstance(dependencies, dict):
            findings.append(_finding(path, section_line, f"{section} is not an object"))
            continue
        for package_name, version in dependencies.items():
            if isinstance(version, str) and EXACT_SEMVER.match(version):
                continue
            key = json.dumps(package_name) + ":"
            line_number = next(
                (
                    index
                    for index, line in enumerate(lines, start=1)
                    if index > section_line and line.strip().startswith(key)
                ),
                section_line,
            )
            findings.append(
                _finding(
                    path,
                    line_number,
                    f"{section} {package_name}: {version} is not an exact version",
                )
            )
    return findings


def check_pnpm_workspace(text: str, path: str) -> list[str]:
    findings: list[str] = []
    block = ""
    allowed_versions_indent: int | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_yaml_comment(raw_line)
        if not _is_code(line):
            continue
        if _indent(line) == 0 and not line.startswith("-"):
            block, _, inline_value = line.partition(":")
            block = block.strip()
            allowed_versions_indent = None
            if block in PNPM_VERSIONED_BLOCKS and FLOW_STYLE_YAML.match(inline_value):
                findings.append(
                    _finding(
                        path, line_number, f"{block} uses flow style (use block style)"
                    )
                )
            continue
        if block not in PNPM_VERSIONED_BLOCKS:
            continue
        entry = line.strip()
        if block == "minimumReleaseAgeExclude":
            excluded = _strip_quotes(entry.removeprefix("-"))
            exclude_match = PNPM_EXCLUDE_ENTRY.match(excluded)
            if not exclude_match or not EXACT_SEMVER.match(
                exclude_match.group("version")
            ):
                findings.append(
                    _finding(
                        path,
                        line_number,
                        f"minimumReleaseAgeExclude entry {excluded} is not name@X.Y.Z",
                    )
                )
            continue
        if block == "peerDependencyRules":
            if allowed_versions_indent is not None and (
                _indent(line) <= allowed_versions_indent
            ):
                allowed_versions_indent = None
            if entry.startswith("allowedVersions:"):
                allowed_versions_indent = _indent(line)
                if FLOW_STYLE_YAML.match(entry.removeprefix("allowedVersions:")):
                    findings.append(
                        _finding(
                            path,
                            line_number,
                            "allowedVersions uses flow style (use block style)",
                        )
                    )
                continue
            if allowed_versions_indent is None:
                continue
        name, _, value = entry.rpartition(": ")
        version = _strip_quotes(value)
        if not EXACT_SEMVER.match(version):
            findings.append(
                _finding(
                    path,
                    line_number,
                    f"{block} {_strip_quotes(name)}: {version} is not an exact version",
                )
            )
    return findings


def check_mise_toml(text: str, path: str) -> list[str]:
    tools = tomllib.loads(text).get("tools", {})
    if not isinstance(tools, dict):
        return [_finding(path, 1, "[tools] is not a table")]
    lines = text.splitlines()
    findings: list[str] = []
    for tool_name, version in tools.items():
        if isinstance(version, str) and EXACT_TOOL_VERSION.match(version):
            continue
        line_number = next(
            (
                index
                for index, line in enumerate(lines, start=1)
                if re.match(rf"^\s*{re.escape(tool_name)}\s*=", line)
            ),
            1,
        )
        findings.append(
            _finding(
                path, line_number, f"[tools] {tool_name} = {version!r} is not X.Y.Z"
            )
        )
    return findings


def _logical_lines(text: str) -> list[tuple[str, list[tuple[int, int]]]]:
    """Join `\\`-continued lines: (text, [(offset in text, physical line number)]).

    Comment and blank lines are dropped without ending a continuation, as Docker does.
    """
    logical: list[tuple[str, list[tuple[int, int]]]] = []
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not _is_code(line):
            continue
        offsets.append((sum(len(part) + 1 for part in parts), line_number))
        continued = line.rstrip().endswith("\\")
        parts.append(line.rstrip().removesuffix("\\") if continued else line)
        if not continued:
            logical.append((" ".join(parts), offsets))
            parts, offsets = [], []
    if parts:
        logical.append((" ".join(parts), offsets))
    return logical


def _line_at(offsets: list[tuple[int, int]], position: int) -> int:
    return [line_number for start, line_number in offsets if start <= position][-1]


def _resolve_args(reference: str, arg_defaults: dict[str, str]) -> str | None:
    unresolved = False

    def substitute(arg_match: re.Match[str]) -> str:
        nonlocal unresolved
        arg_name = arg_match.group("braced") or arg_match.group("bare")
        if arg_name in arg_defaults:
            return arg_defaults[arg_name]
        if arg_match.group("fallback") is not None:
            return arg_match.group("fallback")
        unresolved = True
        return arg_match.group(0)

    resolved = DOCKER_ARG_REFERENCE.sub(substitute, reference)
    return None if unresolved else resolved


def check_dockerfile(text: str, path: str) -> list[str]:
    logical_lines = _logical_lines(text)
    arg_defaults = {
        arg_match.group("name"): _strip_quotes(arg_match.group("default"))
        for line, _ in logical_lines
        if (arg_match := DOCKER_ARG.match(line.strip()))
        and arg_match.group("default") is not None
    }
    stage_names: set[str] = {"scratch"}
    findings: list[str] = []
    for line, offsets in logical_lines:
        first_line = offsets[0][1]
        instruction, _, arguments = line.strip().partition(" ")
        if instruction.upper() == "FROM":
            tokens = [
                token for token in arguments.split() if not token.startswith("--")
            ]
            if tokens and tokens[0].lower() not in stage_names:
                image = _resolve_args(tokens[0], arg_defaults)
                problem = (
                    f"image {tokens[0]} references an ARG with no default"
                    if image is None
                    else image_problem(image)
                )
                if problem:
                    findings.append(_finding(path, first_line, problem))
            if len(tokens) >= 3 and tokens[1].upper() == "AS":
                stage_names.add(tokens[2].lower())
        elif instruction.upper() == "ARG":
            arg_match = DOCKER_ARG.match(line.strip())
            default = (
                _strip_quotes(arg_match.group("default"))
                if arg_match and arg_match.group("default") is not None
                else None
            )
            if (
                arg_match
                and arg_match.group("name").endswith("_VERSION")
                and default is not None
                and not EXACT_ARG_VERSION.match(default)
            ):
                findings.append(
                    _finding(
                        path,
                        first_line,
                        f"ARG {arg_match.group('name')}={default} is not an exact version",
                    )
                )
        for position, message in pip_install_problems(line):
            findings.append(_finding(path, _line_at(offsets, position), message))
    return findings


def check_compose(text: str, path: str) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        image_match = IMAGE_LINE.match(line)
        if image_match and (
            problem := image_problem(_strip_quotes(image_match["image"]))
        ):
            findings.append(_finding(path, line_number, problem))
    return findings


def check_workflow(text: str, path: str) -> list[str]:
    findings: list[str] = []
    image_block_indent: int | None = None
    pip_parts: list[str] = []
    pip_line_number = 0
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not _is_code(raw_line):
            continue
        line = _strip_yaml_comment(raw_line)
        if pip_parts or PIP_INSTALL.search(line):
            pip_line_number = pip_line_number if pip_parts else line_number
            continued = line.endswith("\\")
            pip_parts.append(line.removesuffix("\\"))
            if not continued:
                for _, message in pip_install_problems(" ".join(pip_parts)):
                    findings.append(_finding(path, pip_line_number, message))
                pip_parts = []
            continue
        if image_block_indent is not None and _indent(line) <= image_block_indent:
            image_block_indent = None
        block_match = IMAGE_BLOCK_LINE.match(line)
        if block_match:
            inline_value = _strip_quotes(block_match.group("inline"))
            if FLOW_STYLE_YAML.match(inline_value):
                findings.append(
                    _finding(path, line_number, "flow-style block (use block style)")
                )
            elif inline_value:
                problem = image_problem(inline_value)
                if problem:
                    findings.append(_finding(path, line_number, problem))
            else:
                image_block_indent = _indent(line)
            continue
        if re.search(r"[{,]\s*uses:", line):
            findings.append(
                _finding(path, line_number, "flow-style uses: (use block style)")
            )
            continue
        uses_match = USES_LINE.match(line)
        if uses_match:
            reference = _strip_quotes(uses_match.group("ref"))
            if not (reference.startswith("./") or ACTION_SHA_REF.match(reference)):
                findings.append(
                    _finding(
                        path,
                        line_number,
                        f"uses: {reference} is not ./local or owner/repo@<40-hex sha>",
                    )
                )
            continue
        image_match = IMAGE_LINE.match(line)
        if image_block_indent is not None and image_match:
            problem = image_problem(_strip_quotes(image_match.group("image")))
            if problem:
                findings.append(_finding(path, line_number, problem))
    if pip_parts:
        for _, message in pip_install_problems(" ".join(pip_parts)):
            findings.append(_finding(path, pip_line_number, message))
    return findings


AUDITED_GLOBS: tuple[tuple[str, Callable[[str, str], list[str]]], ...] = (
    ("requirements/*.txt", check_requirements),
    ("frontend/package.json", check_package_json),
    ("frontend/pnpm-workspace.yaml", check_pnpm_workspace),
    (".mise.toml", check_mise_toml),
    ("docker/Dockerfile*", check_dockerfile),
    ("docker/compose*.y*ml", check_compose),
    (".github/workflows/*.y*ml", check_workflow),
    (".github/actions/*/action.y*ml", check_workflow),
)
REQUIRED_FILES: tuple[str, ...] = (
    "frontend/package.json",
    "frontend/pnpm-workspace.yaml",
    ".mise.toml",
)


def main() -> None:
    repo_root = Path.cwd()
    findings: list[str] = []
    audited_files = 0
    for pattern, check in AUDITED_GLOBS:
        for file_path in sorted(repo_root.glob(pattern)):
            audited_files += 1
            relative_path = file_path.relative_to(repo_root).as_posix()
            try:
                findings.extend(
                    check(file_path.read_text(encoding="utf-8"), relative_path)
                )
            except ValueError as parse_error:  # JSON/TOML/Unicode decode errors
                findings.append(f"{relative_path}: could not parse ({parse_error})")
    if audited_files == 0:
        sys.exit("audit-pins: no dependency manifests found (run from the repo root)")
    findings.extend(
        f"{required_file}: missing (expected an audited manifest here)"
        for required_file in REQUIRED_FILES
        if not (repo_root / required_file).is_file()
    )
    if findings:
        sys.exit(
            "Dependencies must be pinned to exact versions:\n" + "\n".join(findings)
        )


if __name__ == "__main__":
    main()
