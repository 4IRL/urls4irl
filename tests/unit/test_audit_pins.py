"""Unit tests for `scripts/audit_pins.py` (run by `make audit-pins`).

Each check is a pure `(text, path) -> findings` function fed inline text, so
nothing reads the real repo except `test_repo_is_clean`, which skips inside
`web` (no `frontend/`, `.github/` or `.mise.toml` mount) and runs for real on
the host and in CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from scripts import audit_pins

pytestmark = pytest.mark.unit

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SAMPLE_PATH: str = "sample"


def _dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


def _package_json(dependencies: dict[str, str]) -> str:
    return json.dumps({"name": "sample", "devDependencies": dependencies}, indent=2)


# --- requirements ---------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "pkg==1.2.3",
        "pkg[extra]==1.2.3",
        "pycparser==3.0",
        "-r requirements-prod.txt",
        "# a comment",
        "",
        "pkg==1.2.3  # trailing comment",
    ],
)
def test_requirements_accepts_exact_pins(line: str) -> None:
    """
    GIVEN a requirements line that is an exact pin, an include, a comment or blank
    WHEN check_requirements scans it
    THEN nothing is reported
    """
    assert audit_pins.check_requirements(line + "\n", SAMPLE_PATH) == []


@pytest.mark.parametrize(
    "line",
    ["pkg>=1.2.3", "pkg~=1.2.3", "pkg<=1.2.3", "pkg==1.*", "pkg"],
)
def test_requirements_flags_ranges(line: str) -> None:
    """
    GIVEN a requirements line with a range, a wildcard or no version
    WHEN check_requirements scans it
    THEN one finding names the path and line
    """
    findings = audit_pins.check_requirements("ok==1.0.0\n" + line + "\n", SAMPLE_PATH)

    assert len(findings) == 1
    assert findings[0].startswith(f"{SAMPLE_PATH}:2: ")


# --- package.json ---------------------------------------------------------------


@pytest.mark.parametrize("version", ["1.2.3", "1.2.3-beta.1"])
def test_package_json_accepts_exact_versions(version: str) -> None:
    """
    GIVEN a package.json dependency pinned to an exact (pre)release
    WHEN check_package_json scans it
    THEN nothing is reported
    """
    text = _package_json({"pkg": version})
    assert audit_pins.check_package_json(text, SAMPLE_PATH) == []


@pytest.mark.parametrize(
    "version",
    [
        "^1.2.3",
        "~1.2.3",
        ">=1.2.3",
        "*",
        "latest",
        "1.x",
        "1.2.3 || 2.0.0",
        "git+https://github.com/owner/repo.git",
        "https://example.com/pkg.tgz",
    ],
)
def test_package_json_flags_non_exact_versions(version: str) -> None:
    """
    GIVEN a package.json dependency with a range, tag, or git/url spec
    WHEN check_package_json scans it
    THEN one finding names the package on its own line
    """
    text = _package_json({"ok": "1.0.0", "pkg": version})

    findings = audit_pins.check_package_json(text, SAMPLE_PATH)

    assert len(findings) == 1
    assert findings[0].startswith(f"{SAMPLE_PATH}:5: ")
    assert "pkg" in findings[0]


def test_package_json_checks_every_dependency_section() -> None:
    """
    GIVEN dependencies, devDependencies and optionalDependencies each with a caret
    WHEN check_package_json scans them
    THEN all three are reported
    """
    text = json.dumps(
        {
            "dependencies": {"one": "^1.0.0"},
            "devDependencies": {"two": "^1.0.0"},
            "optionalDependencies": {"three": "^1.0.0"},
        },
        indent=2,
    )

    assert len(audit_pins.check_package_json(text, SAMPLE_PATH)) == 3


def test_package_json_reports_the_line_inside_its_section() -> None:
    """
    GIVEN a scripts entry that shares its key with a ranged devDependency
    WHEN check_package_json scans it
    THEN the finding points at the devDependencies line, not the scripts one
    """
    text = json.dumps(
        {"scripts": {"vite": "vite"}, "devDependencies": {"vite": "^7.3.5"}},
        indent=2,
    )

    findings = audit_pins.check_package_json(text, SAMPLE_PATH)

    assert findings == [
        f"{SAMPLE_PATH}:6: devDependencies vite: ^7.3.5 is not an exact version"
    ]


@pytest.mark.parametrize(
    "text", ['["not", "an", "object"]', '{"devDependencies": null}']
)
def test_package_json_reports_malformed_shapes(text: str) -> None:
    """
    GIVEN valid JSON whose root or dependency section is not an object
    WHEN check_package_json scans it
    THEN a finding is reported instead of raising
    """
    assert len(audit_pins.check_package_json(text, SAMPLE_PATH)) == 1


# --- pnpm-workspace.yaml --------------------------------------------------------


PNPM_WORKSPACE_CLEAN: str = _dedent(
    """
    packages:
      - "."

    overrides:
      # a security pin
      esbuild: 0.28.2
      postcss: 8.5.23 # trailing comment

    peerDependencyRules:
      allowedVersions:
        openapi-typescript>typescript: "6.0.2"

    minimumReleaseAge: 129600

    minimumReleaseAgeExclude:
      - esbuild@0.28.2
      - "@esbuild/linux-x64@0.28.2"

    allowBuilds:
      esbuild: true
    """
)


def test_pnpm_workspace_accepts_exact_entries() -> None:
    """
    GIVEN a pnpm-workspace.yaml whose overrides, allowedVersions and
        minimumReleaseAgeExclude entries are all exact
    WHEN check_pnpm_workspace scans it
    THEN nothing is reported (packages/allowBuilds are not version fields)
    """
    assert audit_pins.check_pnpm_workspace(PNPM_WORKSPACE_CLEAN, SAMPLE_PATH) == []


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("esbuild: 0.28.2", "esbuild: ^0.28.2"),
        ("postcss: 8.5.23", "postcss: '*'"),
        ('typescript: "6.0.2"', 'typescript: ">=6.0.2"'),
        ("- esbuild@0.28.2", "- esbuild@*"),
        ('"@esbuild/linux-x64@0.28.2"', '"@esbuild/*"'),
    ],
)
def test_pnpm_workspace_flags_ranges(original: str, replacement: str) -> None:
    """
    GIVEN a pnpm-workspace.yaml with one ranged or wildcard version entry
    WHEN check_pnpm_workspace scans it
    THEN exactly that entry is reported
    """
    text = PNPM_WORKSPACE_CLEAN.replace(original, replacement)
    assert text != PNPM_WORKSPACE_CLEAN

    findings = audit_pins.check_pnpm_workspace(text, SAMPLE_PATH)

    assert len(findings) == 1
    assert replacement.split()[-1].strip("\"'-") in findings[0]


@pytest.mark.parametrize(
    "text",
    [
        "minimumReleaseAgeExclude:\n- esbuild@*\n",
        "overrides: {esbuild: ^0.28.2}\n",
        'peerDependencyRules:\n    allowedVersions:\n        pkg>dep: "^6.0.2"\n',
        "peerDependencyRules:\n  allowedVersions: {pkg>dep: ^6}\n",
    ],
)
def test_pnpm_workspace_flags_unindented_flow_and_wide_indent_forms(text: str) -> None:
    """
    GIVEN a range written as a column-0 list item, in flow style, or under a
        4-space-indented allowedVersions
    WHEN check_pnpm_workspace scans it
    THEN it is reported instead of silently skipped
    """
    assert len(audit_pins.check_pnpm_workspace(text, SAMPLE_PATH)) == 1


# --- .mise.toml -----------------------------------------------------------------


def test_mise_toml_accepts_exact_tools() -> None:
    """
    GIVEN a .mise.toml whose [tools] are all exact X.Y.Z
    WHEN check_mise_toml scans it
    THEN nothing is reported
    """
    text = (
        'min_version = "2026.6.14"\n\n[tools]\npython = "3.11.14"\nnode = "24.18.0"\n'
    )
    assert audit_pins.check_mise_toml(text, SAMPLE_PATH) == []


def test_mise_toml_flags_partial_version() -> None:
    """
    GIVEN a .mise.toml with `node = "24"`
    WHEN check_mise_toml scans it
    THEN node is reported on its own line
    """
    text = '[tools]\npython = "3.11.14"\nnode = "24"\n'

    findings = audit_pins.check_mise_toml(text, SAMPLE_PATH)

    assert len(findings) == 1
    assert findings[0].startswith(f"{SAMPLE_PATH}:3: ")
    assert "node" in findings[0]


def test_mise_toml_reports_non_table_tools() -> None:
    """
    GIVEN a .mise.toml whose `tools` key is not a table
    WHEN check_mise_toml scans it
    THEN a finding is reported instead of raising
    """
    assert len(audit_pins.check_mise_toml('tools = "24"\n', SAMPLE_PATH)) == 1


# --- Dockerfile -----------------------------------------------------------------


@pytest.mark.parametrize(
    "dockerfile",
    [
        "FROM python:3.11.14-slim-bookworm\n",
        "FROM node:24.18.0-bookworm-slim AS builder\nFROM builder\n",
        "FROM --platform=linux/amd64 node:24.18.0-bookworm-slim\n",
        "FROM debian:12.15-slim\n",
        "FROM postgres:16.3-bookworm\n",
        "FROM node@sha256:" + "a" * 64 + "\n",
        "FROM ghcr.io/4irl/u4i-prod:latest\n",
        "ARG PLAYWRIGHT_VERSION=1.60.0\n"
        "FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble\n"
        "ARG PLAYWRIGHT_VERSION\n",
        "FROM scratch\n",
        "# syntax=docker/dockerfile:1.5\nFROM python:3.11.14-slim\n",
        "FROM python:3.11.14-slim\nARG RCLONE_VERSION=v1.72.1\n",
        "FROM python:3.11.14-slim\nRUN pip install pip==26.2.1\n",
        "FROM python:3.11.14-slim\nRUN pip install --no-cache-dir --upgrade pip==26.2.1"
        " -r requirements.txt -e .\n",
        "FROM python:3.11.14-slim\n"
        "RUN /venv/bin/pip install --no-cache-dir \\\n"
        "    redis==5.0.1 \\\n"
        "    psycopg2-binary==2.9.9\n",
        "ARG NODE_VERSION=24.18.0\nFROM node:$NODE_VERSION-bookworm-slim\n",
        'ARG NODE_VERSION="24.18.0"\nFROM node:${NODE_VERSION}-bookworm-slim\n',
        "FROM node:${NODE_VERSION:-24.18.0}-bookworm-slim\n",
        "FROM python:3.11.14-slim\n"
        "RUN pip install \\\n"
        "    # pip install commented-out \\\n"
        "    redis==5.0.1\n",
    ],
)
def test_dockerfile_accepts_pinned(dockerfile: str) -> None:
    """
    GIVEN a Dockerfile whose FROM images, *_VERSION args and pip installs are exact
    WHEN check_dockerfile scans it
    THEN nothing is reported
    """
    assert audit_pins.check_dockerfile(dockerfile, SAMPLE_PATH) == []


@pytest.mark.parametrize(
    ("dockerfile", "flagged_line"),
    [
        ("FROM node:22-bookworm-slim AS builder\n", 1),
        ("FROM node\n", 1),
        ("FROM node:latest\n", 1),
        ("FROM python:3.11-slim\n", 1),
        ("FROM debian:12-slim\n", 1),
        ("FROM mcr.microsoft.com/playwright:v${UNKNOWN}-noble\n", 1),
        ("FROM python:3.11.14-slim\nARG PNPM_VERSION=11\n", 2),
        ("FROM python:3.11.14-slim\nRUN pip install --upgrade pip\n", 2),
        ("FROM python:3.11.14-slim\nRUN python3 -m pip install -U pip\n", 2),
        ("FROM python:3.11.14-slim\nRUN pip install redis>=5.0\n", 2),
        (
            "FROM python:3.11.14-slim\n"
            "RUN python3 -m venv /venv \\\n"
            "    && /venv/bin/pip install --no-cache-dir --upgrade pip \\\n"
            "    && /venv/bin/pip install redis==5.0.1\n",
            3,
        ),
        ("FROM redis AS redis\n", 1),
        ("FROM python:3.11.14-slim\nRUN pip3.11 install redis\n", 2),
        (
            "FROM python:3.11.14-slim\n"
            "RUN pip install \\\n"
            "    # a note between continued lines\n"
            "    redis\n",
            2,
        ),
    ],
)
def test_dockerfile_flags_unpinned(dockerfile: str, flagged_line: int) -> None:
    """
    GIVEN a Dockerfile with a floating FROM tag, a non-exact *_VERSION arg or an
        unpinned pip install package
    WHEN check_dockerfile scans it
    THEN exactly one finding points at the offending physical line
    """
    findings = audit_pins.check_dockerfile(dockerfile, SAMPLE_PATH)

    assert len(findings) == 1
    assert findings[0].startswith(f"{SAMPLE_PATH}:{flagged_line}: ")


# --- compose --------------------------------------------------------------------


@pytest.mark.parametrize(
    "image",
    [
        "postgres:16.3-bookworm",
        "redis:6.2.16",
        "cloudflare/cloudflared:2026.6.1",
        "ghcr.io/4irl/u4i-prod:latest",
        "u4i-playwright:1.60.0",
        "'redis:6.2.16-alpine'",
        "redis@sha256:" + "b" * 64,
    ],
)
def test_compose_accepts_pinned_images(image: str) -> None:
    """
    GIVEN a compose service image that is exact, own-registry or a local u4i-* tag
    WHEN check_compose scans it
    THEN nothing is reported
    """
    text = f"services:\n  svc:\n    image: {image}\n"
    assert audit_pins.check_compose(text, SAMPLE_PATH) == []


@pytest.mark.parametrize(
    "image", ["redis:6.2", "redis", "redis:latest", "u4i-playwright:latest"]
)
def test_compose_flags_floating_images(image: str) -> None:
    """
    GIVEN a compose service image with a floating or missing tag
    WHEN check_compose scans it
    THEN it is reported on its line
    """
    text = f"services:\n  svc:\n    image: {image}\n"

    findings = audit_pins.check_compose(text, SAMPLE_PATH)

    assert len(findings) == 1
    assert findings[0].startswith(f"{SAMPLE_PATH}:3: ")


# --- workflows ------------------------------------------------------------------


WORKFLOW_CLEAN: str = _dedent(
    """
    jobs:
      build:
        runs-on: ubuntu-latest
        strategy:
          matrix:
            include:
              - image: u4i-dev
        container: node:24.18.0-bookworm-slim
        services:
          redis:
            image: 'redis:6.2.16-alpine'
        steps:
          - uses: ./.github/actions/setup-pnpm
            with:
              image: u4i-dev
          - name: Checkout
            uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
          - run: |
              # pip install anything is a comment here
              python3.11 -m pip install --upgrade pip==26.2.1;
              pip install -r requirements/requirements-test.txt;
      reuse:
        uses: ./.github/workflows/lint.yml
    """
)


def test_workflow_accepts_pinned_refs() -> None:
    """
    GIVEN a workflow with local/SHA-pinned uses:, an exact service image, an
        exact pip install and a matrix `image:` key outside services:
    WHEN check_workflow scans it
    THEN nothing is reported
    """
    assert audit_pins.check_workflow(WORKFLOW_CLEAN, SAMPLE_PATH) == []


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (
            "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
            "actions/checkout@v6",
        ),
        (
            "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
            "actions/checkout@main",
        ),
        ("'redis:6.2.16-alpine'", "redis:6.2-alpine"),
        ("--upgrade pip==26.2.1;", "--upgrade pip;"),
        (
            "--upgrade pip==26.2.1;",
            "--upgrade pip==26.2.1 \\\n          redis;",
        ),
        ("container: node:24.18.0-bookworm-slim", "container: node:24"),
        (
            "container: node:24.18.0-bookworm-slim",
            "container:\n      image: node:24",
        ),
        (
            "container: node:24.18.0-bookworm-slim",
            "container: {image: node:24}",
        ),
        (
            "- uses: ./.github/actions/setup-pnpm",
            "- {uses: actions/checkout@v4}",
        ),
    ],
)
def test_workflow_flags_unpinned(original: str, replacement: str) -> None:
    """
    GIVEN a workflow with a tag/branch action ref, a floating service or job
        container image, an unpinned (possibly `\\`-continued) pip install, or
        flow-style YAML in an audited key
    WHEN check_workflow scans it
    THEN exactly one finding is reported
    """
    text = WORKFLOW_CLEAN.replace(original, replacement)
    assert text != WORKFLOW_CLEAN

    assert len(audit_pins.check_workflow(text, SAMPLE_PATH)) == 1


# --- main -----------------------------------------------------------------------


def _write(root: Path, relative_path: str, text: str) -> None:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def _clean_repo(root: Path) -> None:
    _write(root, "requirements/requirements-prod.txt", "Flask==3.1.3\n")
    _write(root, "frontend/package.json", _package_json({"vite": "7.3.5"}))
    _write(root, "frontend/pnpm-workspace.yaml", PNPM_WORKSPACE_CLEAN)
    _write(root, ".mise.toml", '[tools]\nnode = "24.18.0"\n')
    _write(root, "docker/Dockerfile", "FROM python:3.11.14-slim\n")
    _write(root, "docker/compose.yaml", "services:\n  r:\n    image: redis:6.2.16\n")
    _write(root, ".github/workflows/ci.yml", WORKFLOW_CLEAN)
    _write(
        root,
        ".github/actions/setup/action.yml",
        "runs:\n  steps:\n    - uses: ./.github/actions/other\n",
    )


def test_main_exits_zero_on_clean_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a repo layout where every dependency surface is exactly pinned
    WHEN main runs from its root
    THEN it returns without exiting non-zero
    """
    _clean_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    audit_pins.main()


def test_main_exits_non_zero_listing_every_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a repo layout with an unpinned surface in several files
    WHEN main runs from its root
    THEN it exits non-zero and lists every finding with its relative path
    """
    _clean_repo(tmp_path)
    _write(tmp_path, "docker/compose.yaml", "services:\n  r:\n    image: redis:6.2\n")
    _write(tmp_path, "requirements/requirements-test.txt", "pytest>=9\n")
    _write(tmp_path, ".github/actions/setup/action.yml", "- uses: owner/repo@v1\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        audit_pins.main()

    message = str(exit_info.value.code)
    assert exit_info.value.code not in (0, None)
    assert "docker/compose.yaml:3: " in message
    assert "requirements/requirements-test.txt:1: " in message
    assert ".github/actions/setup/action.yml:1: " in message


def test_main_reports_unparseable_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a repo layout whose frontend/package.json is not valid JSON
    WHEN main runs from its root
    THEN it exits non-zero naming the file as unparseable
    """
    _clean_repo(tmp_path)
    _write(tmp_path, "frontend/package.json", "{not json")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        audit_pins.main()

    assert "frontend/package.json: could not parse" in str(exit_info.value.code)


def test_main_reports_missing_required_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a repo layout without .mise.toml
    WHEN main runs from its root
    THEN it exits non-zero naming the missing manifest
    """
    _clean_repo(tmp_path)
    (tmp_path / ".mise.toml").unlink()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        audit_pins.main()

    assert ".mise.toml: missing" in str(exit_info.value.code)


def test_main_exits_non_zero_when_nothing_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a directory with no dependency manifests (run from the wrong cwd)
    WHEN main runs there
    THEN it exits non-zero instead of silently passing
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        audit_pins.main()

    assert exit_info.value.code not in (0, None)


@pytest.mark.skipif(
    not (REPO_ROOT / "frontend" / "package.json").exists(),
    reason="manifests not mounted in web",
)
def test_repo_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN the real repository
    WHEN main audits it from the repo root
    THEN every dependency surface is exactly pinned
    """
    monkeypatch.chdir(REPO_ROOT)

    audit_pins.main()


def test_audit_pins_module_is_stdlib_only() -> None:
    """
    GIVEN audit_pins.py, which runs on the host under bare mise python
    WHEN it is loaded in a fresh interpreter without the project root
    THEN no third-party or backend module is imported (stdlib only)
    """
    probe_script = (
        "import importlib.util\n"
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', PROJECT_ROOT)]\n"
        "spec = importlib.util.spec_from_file_location('audit_pins_leaf', MODULE_FILE)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "forbidden = [name for name in sys.modules "
        "if name.split('.')[0] in ('flask', 'sqlalchemy', 'redis', 'yaml', 'backend')]\n"
        "assert forbidden == [], forbidden\n"
    )
    module_file = Path(audit_pins.__file__).resolve()
    project_root = module_file.parents[1]
    preamble = (
        f"PROJECT_ROOT = {str(project_root)!r}\nMODULE_FILE = {str(module_file)!r}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", preamble + probe_script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"audit_pins module pulled in a non-stdlib import:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
