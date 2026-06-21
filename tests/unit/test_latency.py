"""Unit-scope coverage + purity tests for the latency-metric registry.

Guards the single-source-of-truth invariants of `backend.metrics.latency`:
every `LatencyMetricName` has a registry entry (`flask metrics audit` does NOT
cover this primitive — same as gauges), and the module stays Flask/SQLAlchemy/
backend-free so the side-loaded flush worker can import it by path inside the
workflow container.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from backend.metrics import latency
from backend.metrics.latency import LATENCY_REGISTRY, LatencyMetricName

pytestmark = pytest.mark.unit


def test_latency_registry_covers_every_latency_metric_name() -> None:
    """`LATENCY_REGISTRY` keys and `set(LatencyMetricName)` must be identical.

    Catches drift in either direction: an enum member with no registry entry
    or a registry key whose enum member was removed. This is the latency analog
    of the gauge coverage gate — there is no audit command for this primitive.
    """
    assert set(LATENCY_REGISTRY) == set(LatencyMetricName)


def test_latency_module_is_flask_free() -> None:
    """`latency.py` must pull in no Flask / SQLAlchemy / backend module on side-load.

    The flush worker side-loads this file by absolute path (via
    `importlib.util.spec_from_file_location`, never `import backend...`) inside
    the workflow container, whose venv has only redis + psycopg2. Loading it as
    a package (`import backend.metrics.latency`) would falsely pull in Flask via
    `backend/__init__.py`, so the contract must be checked the same way the
    worker loads it: by file path, in a fresh interpreter with a pruned
    `sys.path` (no project root, so `backend` is not importable as a package),
    then inspecting `sys.modules` for forbidden imports the module itself drags
    in.
    """
    probe = (
        "import importlib.util\n"
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', PROJECT_ROOT)]\n"
        "spec = importlib.util.spec_from_file_location('latency_leaf', LATENCY_FILE)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        # Register before exec so the frozen @dataclass can resolve its own
        # module under `from __future__ import annotations` — the same
        # registration the side-loader must perform for this leaf.
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "forbidden = [name for name in sys.modules "
        "if name == 'flask' or name.startswith('flask.') "
        "or name == 'sqlalchemy' or name.startswith('sqlalchemy.') "
        "or name == 'backend' or name.startswith('backend.')]\n"
        "assert forbidden == [], forbidden\n"
        "assert not hasattr(module, 'db')\n"
    )
    latency_file = Path(latency.__file__).resolve()
    project_root = latency_file.parents[2]
    preamble = (
        f"PROJECT_ROOT = {str(project_root)!r}\n"
        f"LATENCY_FILE = {str(latency_file)!r}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", preamble + probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"latency module pulled in a forbidden import on side-load:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
