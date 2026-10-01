"""Shared probe for the host-only scripts that must stay stdlib-only."""

import subprocess
import sys
from pathlib import Path

_PROBE_SCRIPT = (
    "import importlib.util\n"
    "import sys\n"
    "sys.path = [path_entry for path_entry in sys.path if path_entry not in ('', PROJECT_ROOT)]\n"
    "spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_FILE)\n"
    "module = importlib.util.module_from_spec(spec)\n"
    # Register before exec so frozen dataclasses can resolve their own module
    # under `from __future__ import annotations`.
    "sys.modules[spec.name] = module\n"
    "spec.loader.exec_module(module)\n"
    "forbidden = [name for name in sys.modules "
    "if name.split('.')[0] in FORBIDDEN_MODULES]\n"
    "assert forbidden == [], forbidden\n"
)


def assert_module_is_stdlib_only(
    module_path: Path, forbidden_modules: tuple[str, ...]
) -> None:
    """Load `module_path` in a fresh interpreter without the project root on
    `sys.path` and assert none of `forbidden_modules` (top-level names) was
    imported. A third-party or `backend` import either fails to resolve or
    shows up in `sys.modules`.
    """
    module_file = module_path.resolve()
    project_root = module_file.parents[1]
    preamble = (
        f"PROJECT_ROOT = {str(project_root)!r}\n"
        f"MODULE_FILE = {str(module_file)!r}\n"
        f"MODULE_NAME = {module_file.stem + '_leaf'!r}\n"
        f"FORBIDDEN_MODULES = {forbidden_modules!r}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", preamble + _PROBE_SCRIPT],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{module_file.stem} module pulled in a non-stdlib import:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
