# Shared metrics-UI test machinery (fixtures + helpers) reused across every
# domain UI test directory that exercises the anonymous-metrics pipeline.
#
# Layout choice:
#   - `conftest_fragment.py` defines the fixtures (metrics_redis_client,
#     metrics_enabled_for_ui, metrics_registry_synced, clear_metrics_state,
#     pg_conn_for_metrics). It is registered as a `pytest_plugins` entry in
#     `tests/functional/conftest.py` so the fixtures are visible to every
#     domain UI test without requiring per-file `pytest_plugins` declarations.
#   - `db_utils.py` defines the helper functions (query_anonymous_metrics_rows,
#     wait_for_metrics_row, _trigger_metrics_flush_via_pagehide) imported
#     directly by tests.
#
# This package is NOT a pytest collection directory — naming it `metrics_helpers`
# (rather than `metrics_ui`) keeps pytest from treating it as a test location
# and avoids the implicit conftest scoping that the original metrics_ui
# package relied on. Fixtures are exposed via the explicit `pytest_plugins`
# import path documented above instead.
