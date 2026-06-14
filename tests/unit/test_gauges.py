"""Unit-scope coverage + SQL-generator tests for the gauge registry.

Guards the single-source-of-truth invariants of `backend.metrics.gauges`:
every `GaugeName` has a registry entry, the pure `build_gauge_sql` generator
emits the expected per-kind clauses, no event-derived gauge ships in this PR,
and the module stays Flask/SQLAlchemy-free so the side-loaded sampler can import
it inside the workflow container.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from backend.metrics import gauges
from backend.metrics.gauges import (
    GAUGE_REGISTRY,
    GaugeKind,
    GaugeName,
    build_gauge_sql,
    value_column_for,
)

pytestmark = pytest.mark.unit


def test_gauge_registry_covers_every_gauge_name() -> None:
    """`GAUGE_REGISTRY` keys and `set(GaugeName)` must be identical.

    Catches drift in either direction: an enum member with no registry entry
    or a registry key whose enum member was removed. Mirrors
    `test_event_registry_keys_match_event_name_enum`.
    """
    assert set(GAUGE_REGISTRY) == set(GaugeName)


def test_build_gauge_sql_volume_count_star() -> None:
    sql = build_gauge_sql(GaugeName.TOTAL_UTUBS)
    assert "COUNT(*)" in sql
    assert 'FROM "Utubs"' in sql
    assert "DISTINCT" not in sql


def test_build_gauge_sql_volume_count_distinct() -> None:
    sql = build_gauge_sql(GaugeName.TOTAL_TAGS)
    assert 'COUNT(DISTINCT "tagString")' in sql
    assert 'FROM "UtubTags"' in sql


def test_build_gauge_sql_distribution_avg() -> None:
    sql = build_gauge_sql(GaugeName.AVG_URLS_PER_UTUB)
    assert "AVG(c)" in sql
    assert 'GROUP BY "utubID"' in sql
    assert 'FROM "UtubUrls"' in sql
    # AVG gauges carry no k-anonymity suppression.
    assert "CASE" not in sql


def test_build_gauge_sql_distribution_avg_uses_count_column() -> None:
    sql = build_gauge_sql(GaugeName.AVG_MEMBERS_PER_UTUB)
    assert 'COUNT("userID")' in sql
    assert 'GROUP BY "utubID"' in sql


def test_build_gauge_sql_distribution_max_has_k_anon_guard() -> None:
    sql = build_gauge_sql(GaugeName.MAX_URLS_PER_UTUB)
    assert "MAX(c)" in sql
    assert 'GROUP BY "utubID"' in sql
    assert "< 5" in sql
    assert "CASE WHEN" in sql
    assert "THEN NULL" in sql
    assert 'COUNT(DISTINCT "utubID")' in sql


def test_build_gauge_sql_distribution_max_groups_by_url_and_user() -> None:
    """The two relational max gauges replacing the deferred event-derived ones."""
    url_sql = build_gauge_sql(GaugeName.MAX_UTUBS_PER_URL)
    assert 'GROUP BY "urlID"' in url_sql
    assert 'FROM "UtubUrls"' in url_sql
    assert "< 5" in url_sql

    user_sql = build_gauge_sql(GaugeName.MAX_URLS_PER_USER)
    assert 'GROUP BY "userID"' in user_sql
    assert 'FROM "UtubUrls"' in user_sql
    assert "< 5" in user_sql


def test_no_event_derived_gauges_ship() -> None:
    """No shipped gauge may use the reserved EVENT_DERIVED_MAX kind.

    Guards the deferral so a careless re-add cannot silently ship a
    permanently-NULL gauge before the source events gain per-entity dims.
    """
    assert all(
        definition.kind is not GaugeKind.EVENT_DERIVED_MAX
        for definition in GAUGE_REGISTRY.values()
    )


def test_gauges_module_is_flask_free() -> None:
    """`gauges.py` must pull in no Flask / SQLAlchemy / events module on side-load.

    The sampler side-loads this file by absolute path (via
    `importlib.util.spec_from_file_location`, never `import backend...`) inside
    the workflow container, whose venv has only redis + psycopg2. Loading it as
    a package (`import backend.metrics.gauges`) would falsely pull in Flask via
    `backend/__init__.py`, so the contract must be checked the same way the
    sampler loads it: by file path, in a fresh interpreter with a pruned
    `sys.path` (no project root, so `backend` is not importable as a package),
    then inspecting `sys.modules` for forbidden imports the module itself drags
    in.
    """
    probe = (
        "import importlib.util\n"
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', PROJECT_ROOT)]\n"
        "spec = importlib.util.spec_from_file_location('gauges_leaf', GAUGE_FILE)\n"
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
    gauge_file = Path(gauges.__file__).resolve()
    project_root = gauge_file.parents[2]
    preamble = (
        f"PROJECT_ROOT = {str(project_root)!r}\n" f"GAUGE_FILE = {str(gauge_file)!r}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", preamble + probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"gauges module pulled in a forbidden import on side-load:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_value_column_for() -> None:
    assert value_column_for(GaugeKind.DISTRIBUTION_AVG) == "valueFloat"
    assert value_column_for(GaugeKind.VOLUME) == "valueInt"
    assert value_column_for(GaugeKind.DISTRIBUTION_MAX) == "valueInt"
    assert value_column_for(GaugeKind.EVENT_DERIVED_MAX) == "valueInt"
