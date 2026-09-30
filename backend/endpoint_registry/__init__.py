"""Generated endpoint registry: a pure builder over the live Flask url_map.

`registry.build_registry(app)` derives every mechanical column (handler,
decorators, services, schemas, templates, JS linkage) from `app.url_map`,
`app.view_functions`, handler source ASTs, `backend/utils/all_routes.py` and
`backend/templates`. The output is deterministic so it can be committed and
audited for drift.
"""
