"""Keep every Python version literal in agreement with the `.mise.toml` pin.

`find_violations` is a pure function over `{relative path: text}`, so the negative tests feed it
synthetic files. Only `test_repo_python_versions_agree` reads the real repo; it skips inside `web`
(no `.mise.toml`, `.github/` or `Makefile` mount) and runs for real on the host and in CI.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT: Path = Path(__file__).resolve().parents[2]

MISE_PATH: str = ".mise.toml"
PYPROJECT_PATH: str = "pyproject.toml"
PROD_REQUIREMENTS_PATH: str = "requirements/requirements-prod.txt"
WORKFLOW_DOCKERFILE_PATH: str = "docker/Dockerfile.Workflow"
MAKEFILE_PATH: str = "Makefile"
PYTHON_IMAGE_DOCKERFILES: tuple[str, ...] = (
    "docker/Dockerfile",
    "docker/Dockerfile.Local",
    WORKFLOW_DOCKERFILE_PATH,
)

MISE_PYTHON_PATTERN: re.Pattern[str] = re.compile(
    r'^python\s*=\s*"(\d+\.\d+\.\d+)"', re.MULTILINE
)
FROM_PYTHON_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*FROM\s+(?:--platform=\S+\s+)?python:(\S+)", re.IGNORECASE
)
SETUP_PYTHON_PATTERN: re.Pattern[str] = re.compile(
    r"""python-version:\s*['"]?([^'"\s#]+)"""
)
PYTHON_BINARY_PATTERN: re.Pattern[str] = re.compile(r"python3\.(\d+)")
SITE_PACKAGES_PATTERN: re.Pattern[str] = re.compile(
    r"lib/python(\d+)\.(\d+)/site-packages"
)
PSYCOPG2_BINARY_PATTERN: re.Pattern[str] = re.compile(
    r"psycopg2-binary==([0-9][0-9A-Za-z.]*)"
)
TARGET_VERSION_PATTERN: re.Pattern[str] = re.compile(
    r'^target-version\s*=\s*"([^"]*)"', re.MULTILINE
)


def _numbered(text: str) -> list[tuple[int, str]]:
    return list(enumerate(text.splitlines(), start=1))


def _is_dockerfile(path: str) -> bool:
    return path.startswith("docker/Dockerfile")


def _in_scan_scope(path: str) -> bool:
    """Files whose `python3.N` / `lib/pythonA.B` tokens must follow the pin."""
    return (
        path.startswith(".github/")
        or path.startswith("docker/")
        or path == MAKEFILE_PATH
    )


def _check_mise(files: Mapping[str, str]) -> tuple[str | None, list[str]]:
    text = files.get(MISE_PATH)
    if text is None:
        return None, [f"{MISE_PATH}: missing, cannot read the python pin"]
    match = MISE_PYTHON_PATTERN.search(text)
    if match is None:
        return None, [f'{MISE_PATH}: no `python = "X.Y.Z"` line found']
    return match.group(1), []


def _check_dockerfiles(files: Mapping[str, str], full: str) -> list[str]:
    violations: list[str] = []
    expected_tag = f"{full}-slim-bookworm"
    for path in sorted(files):
        if not _is_dockerfile(path):
            continue
        found_python_base = False
        for line_number, line in _numbered(files[path]):
            match = FROM_PYTHON_PATTERN.match(line)
            if match is None:
                continue
            found_python_base = True
            if match.group(1) != expected_tag:
                violations.append(
                    f"{path}:{line_number}: `FROM python:{match.group(1)}` "
                    f"should be `python:{expected_tag}`"
                )
        if path in PYTHON_IMAGE_DOCKERFILES and not found_python_base:
            violations.append(
                f"{path}: no `FROM python:{expected_tag}` base (a Python-image "
                "Dockerfile must start from the python image)"
            )
    for path in PYTHON_IMAGE_DOCKERFILES:
        if path not in files:
            violations.append(f"{path}: missing, cannot check its python base")
    return violations


def _check_setup_python(files: Mapping[str, str], full: str) -> list[str]:
    violations: list[str] = []
    for path in sorted(files):
        if not path.startswith(".github/"):
            continue
        for line_number, line in _numbered(files[path]):
            match = SETUP_PYTHON_PATTERN.search(line)
            # A `${{ ... }}` expression (matrix/env) is not a literal; nothing to compare.
            if (
                match is not None
                and not match.group(1).startswith("$")
                and match.group(1) != full
            ):
                violations.append(
                    f"{path}:{line_number}: `python-version: {match.group(1)}` "
                    f"should be `{full}`"
                )
    return violations


def _check_psycopg2_binary(files: Mapping[str, str]) -> list[str]:
    workflow = PSYCOPG2_BINARY_PATTERN.search(files.get(WORKFLOW_DOCKERFILE_PATH, ""))
    prod = PSYCOPG2_BINARY_PATTERN.search(files.get(PROD_REQUIREMENTS_PATH, ""))
    if workflow is None:
        return [f"{WORKFLOW_DOCKERFILE_PATH}: no `psycopg2-binary==` pin found"]
    if prod is None:
        return [f"{PROD_REQUIREMENTS_PATH}: no `psycopg2-binary==` pin found"]
    if workflow.group(1) == prod.group(1):
        return []
    line_number = next(
        number
        for number, line in _numbered(files[WORKFLOW_DOCKERFILE_PATH])
        if PSYCOPG2_BINARY_PATTERN.search(line)
    )
    return [
        f"{WORKFLOW_DOCKERFILE_PATH}:{line_number}: `psycopg2-binary=={workflow.group(1)}` "
        f"differs from {PROD_REQUIREMENTS_PATH}'s `{prod.group(1)}`"
    ]


def _check_tokens(files: Mapping[str, str], minor: str) -> list[str]:
    violations: list[str] = []
    major_minor = f"3.{minor}"
    for path in sorted(files):
        if not _in_scan_scope(path):
            continue
        for line_number, line in _numbered(files[path]):
            for match in PYTHON_BINARY_PATTERN.finditer(line):
                if match.group(1) != minor:
                    violations.append(
                        f"{path}:{line_number}: `{match.group(0)}` should be "
                        f"`python{major_minor}`"
                    )
            for match in SITE_PACKAGES_PATTERN.finditer(line):
                if f"{match.group(1)}.{match.group(2)}" != major_minor:
                    violations.append(
                        f"{path}:{line_number}: `{match.group(0)}` should be "
                        f"`lib/python{major_minor}/site-packages`"
                    )
    return violations


def _check_target_version(files: Mapping[str, str], full: str) -> list[str]:
    text = files.get(PYPROJECT_PATH)
    if text is None:
        return [f"{PYPROJECT_PATH}: missing, cannot check target-version"]
    expected = "py" + "".join(full.split(".")[:2])
    for line_number, line in _numbered(text):
        match = TARGET_VERSION_PATTERN.match(line)
        if match is not None:
            if match.group(1) == expected:
                return []
            return [
                f'{PYPROJECT_PATH}:{line_number}: `target-version = "{match.group(1)}"` '
                f'should be "{expected}"'
            ]
    return [f"{PYPROJECT_PATH}: no `target-version` line found"]


def find_violations(files: Mapping[str, str]) -> list[str]:
    """Every `file:line: message` where a python version literal disagrees with `.mise.toml`."""
    full, violations = _check_mise(files)
    if full is None:
        return violations
    minor = full.split(".")[1]
    violations += _check_dockerfiles(files, full)
    violations += _check_setup_python(files, full)
    violations += _check_psycopg2_binary(files)
    violations += _check_tokens(files, minor)
    violations += _check_target_version(files, full)
    return violations


# --- real repo ------------------------------------------------------------------


def _read_repo_files() -> dict[str, str]:
    paths = [
        REPO_ROOT / MISE_PATH,
        REPO_ROOT / MAKEFILE_PATH,
        REPO_ROOT / PYPROJECT_PATH,
        REPO_ROOT / PROD_REQUIREMENTS_PATH,
        *(REPO_ROOT / "docker").glob("Dockerfile*"),
        *(REPO_ROOT / ".github").rglob("*.yml"),
        *(REPO_ROOT / ".github").rglob("*.yaml"),
        *(REPO_ROOT / "docker").glob("*.sh"),
        *(REPO_ROOT / "docker").glob("*.yaml"),
    ]
    return {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text()
        for path in paths
        if path.is_file()
    }


@pytest.mark.skipif(
    not (
        (REPO_ROOT / MISE_PATH).exists()
        and (REPO_ROOT / ".github").is_dir()
        and (REPO_ROOT / MAKEFILE_PATH).exists()
    ),
    reason=".mise.toml, .github/ and Makefile are not mounted in web",
)
def test_repo_python_versions_agree() -> None:
    """
    GIVEN the real repository
    WHEN every python version literal is compared with the .mise.toml pin
    THEN none disagrees
    """
    assert find_violations(_read_repo_files()) == []


# --- negative tests (synthetic content) -----------------------------------------

GOOD_FILES: dict[str, str] = {
    MISE_PATH: '[tools]\npython = "3.14.10"\nnode = "24.18.0"\n',
    "docker/Dockerfile": (
        "FROM node:22.23.3-bookworm-slim AS frontend-builder\n"
        "FROM python:3.14.10-slim-bookworm AS builder\n"
        "FROM python:3.14.10-slim-bookworm\n"
    ),
    "docker/Dockerfile.Local": "FROM python:3.14.10-slim-bookworm\n",
    WORKFLOW_DOCKERFILE_PATH: (
        "FROM python:3.14.10-slim-bookworm\nRUN pip install psycopg2-binary==2.9.13\n"
    ),
    "docker/Dockerfile.Vite": "FROM node:24.18.0-bookworm-slim\n",
    ".github/workflows/test.yml": (
        "      - uses: actions/setup-python@abc\n"
        "        with:\n"
        "          python-version: '3.14.10'\n"
        "          path: ${{ env.pythonLocation }}/lib/python3.14/site-packages/*\n"
        "      - run: python3.14 -m pytest\n"
    ),
    MAKEFILE_PATH: "test:\n\tpython3.14 -m pytest\n",
    PROD_REQUIREMENTS_PATH: "flask==3.1.0\npsycopg2-binary==2.9.13\n",
    PYPROJECT_PATH: '[tool.ruff]\ntarget-version = "py314"\n',
}


def _with(path: str, text: str) -> dict[str, str]:
    """GOOD_FILES with one file's text replaced."""
    return {**GOOD_FILES, path: text}


def test_good_synthetic_repo_has_no_violations() -> None:
    """
    GIVEN a synthetic repo whose literals all follow the pin
    WHEN find_violations runs
    THEN nothing is reported
    """
    assert find_violations(GOOD_FILES) == []


def test_flags_a_dockerfile_python_tag_that_differs_from_the_pin() -> None:
    """
    GIVEN a Dockerfile base on another python patch
    WHEN find_violations runs
    THEN one finding names the file, the line and the literal
    """
    files = _with("docker/Dockerfile.Local", "FROM python:3.12.4-slim-bookworm\n")

    assert find_violations(files) == [
        "docker/Dockerfile.Local:1: `FROM python:3.12.4-slim-bookworm` "
        "should be `python:3.14.10-slim-bookworm`"
    ]


def test_flags_a_python_dockerfile_on_a_non_slim_bookworm_tag() -> None:
    """
    GIVEN a python base that keeps the patch but drops `-slim-bookworm`
    WHEN find_violations runs
    THEN it is reported
    """
    files = _with("docker/Dockerfile.Local", "FROM python:3.14.10-slim\n")

    assert len(find_violations(files)) == 1


def test_flags_a_workflow_dockerfile_with_a_debian_base() -> None:
    """
    GIVEN a Workflow-style Dockerfile that is based on debian, not the python image
    WHEN find_violations runs
    THEN it is reported as having no python base
    """
    files = _with(
        WORKFLOW_DOCKERFILE_PATH,
        "FROM debian:12-slim\nRUN pip install psycopg2-binary==2.9.13\n",
    )

    violations = find_violations(files)

    assert len(violations) == 1
    assert violations[0].startswith("docker/Dockerfile.Workflow: no `FROM python:")


def test_node_dockerfiles_and_stages_are_exempt_from_the_python_base_rule() -> None:
    """
    GIVEN node-only Dockerfiles and a node stage in a python Dockerfile
    WHEN find_violations runs
    THEN they are not reported (the good repo already has both)
    """
    assert "FROM node:" in GOOD_FILES["docker/Dockerfile"]
    assert find_violations(GOOD_FILES) == []


def test_flags_a_setup_python_version_that_differs_from_the_pin() -> None:
    """
    GIVEN a workflow whose setup-python version is stale
    WHEN find_violations runs
    THEN the finding names the workflow file and line
    """
    stale = GOOD_FILES[".github/workflows/test.yml"].replace("3.14.10", "3.12.4")
    files = _with(".github/workflows/test.yml", stale)

    assert find_violations(files) == [
        ".github/workflows/test.yml:3: `python-version: 3.12.4` should be `3.14.10`"
    ]


def test_flags_a_psycopg2_binary_mismatch_between_workflow_and_prod() -> None:
    """
    GIVEN Dockerfile.Workflow pinning another psycopg2-binary than requirements-prod
    WHEN find_violations runs
    THEN the mismatch is reported at the Dockerfile line
    """
    files = _with(PROD_REQUIREMENTS_PATH, "psycopg2-binary==2.9.9\n")

    violations = find_violations(files)

    assert len(violations) == 1
    assert violations[0].startswith("docker/Dockerfile.Workflow:2:")
    assert "2.9.13" in violations[0] and "2.9.9" in violations[0]


@pytest.mark.parametrize(
    "path, text, token",
    [
        (
            ".github/workflows/test.yml",
            "      - run: python3.10 -m pytest\n",
            "python3.10",
        ),
        ("docker/entrypoint.sh", "exec python3.12 app.py\n", "python3.12"),
        (MAKEFILE_PATH, "test:\n\tpython3.13 -m pytest\n", "python3.13"),
    ],
)
def test_flags_a_python3_n_token_that_differs_from_the_minor(
    path: str, text: str, token: str
) -> None:
    """
    GIVEN a python3.N token under .github, docker or the Makefile with the wrong N
    WHEN find_violations runs
    THEN one finding names that file and the token
    """
    violations = find_violations(_with(path, text))

    assert len(violations) == 1
    assert violations[0].startswith(f"{path}:")
    assert f"`{token}`" in violations[0]


def test_flags_a_site_packages_path_for_another_minor() -> None:
    """
    GIVEN a CI cache path under lib/python3.10/site-packages
    WHEN find_violations runs
    THEN it is reported at that line
    """
    files = dict(GOOD_FILES)
    files[".github/workflows/test.yml"] = (
        "          path: ${{ env.pythonLocation }}/lib/python3.10/site-packages/*\n"
    )

    violations = find_violations(files)

    assert [violation for violation in violations if "site-packages" in violation] == [
        ".github/workflows/test.yml:1: `lib/python3.10/site-packages` should be "
        "`lib/python3.14/site-packages`"
    ]


def test_flags_a_ruff_target_version_that_differs_from_the_pin() -> None:
    """
    GIVEN pyproject.toml targeting py312
    WHEN find_violations runs
    THEN the finding names pyproject.toml, the line and the expected value
    """
    files = _with(PYPROJECT_PATH, '[tool.ruff]\ntarget-version = "py312"\n')

    assert find_violations(files) == [
        'pyproject.toml:2: `target-version = "py312"` should be "py314"'
    ]


def test_fails_closed_without_a_mise_python_pin() -> None:
    """
    GIVEN a repo with no `.mise.toml` python line
    WHEN find_violations runs
    THEN it reports that instead of passing
    """
    files = _with(MISE_PATH, '[tools]\nnode = "24.18.0"\n')

    assert find_violations(files) == ['.mise.toml: no `python = "X.Y.Z"` line found']
