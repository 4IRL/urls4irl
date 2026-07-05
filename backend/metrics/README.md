# Metrics & Events — How to Add, Modify, or Remove

This guide is the **forward path** for changing the anonymous-metrics surface. The
**backward path** (catching what's already broken) is `make audit` — that's the
executable contract; this doc is what to do before running it.

> **Before you start:** confirm `make audit` reports clean on `main`. If it
> doesn't, fix the existing drift before adding new noise.

---

## Mental model

Each event flows through three layers:

```
Definition       Wiring                          Emission
EventName    →   EVENT_REGISTRY                  service code (DOMAIN/API)
             →   DIMENSION_MODELS  (Pydantic)    or TS recordEvent() (UI)
             →   EVENT_NAME_TO_RESOURCE
```

The audit gate (`flask metrics audit --strict`) checks that every layer is
populated and aligned. Missing any one → CI red.

**Three categories** with different code paths:

| Category | Where it fires from                              | TS codegen?      |
|----------|--------------------------------------------------|------------------|
| `API`    | Automatic, via `MetricsMiddleware` on every route| No               |
| `DOMAIN` | Manual, after `db.session.commit()` in services  | No               |
| `UI`     | Manual, via `recordEvent(...)` in TypeScript     | Yes (auto-typed) |

---

## Recipe 1 — Add a new event

### 1. Define it

In `backend/metrics/events.py`:
- Append to `EventName` (alphabetical within category section).

In `backend/metrics/event_registry.py`:
- Add an entry to `EVENT_REGISTRY` with `description`, `category`, and
  `dimensions` (empty dict if none). `EVENT_CATEGORY` and
  `EVENT_DESCRIPTIONS` are derived projections of `EVENT_REGISTRY` —
  do **not** edit them directly.

### 2. Wire the dimension model

In `backend/metrics/dimension_models.py`:
- If your event carries no dims beyond `device_type`, register it against
  `_DimDeviceOnly` in the `DIMENSION_MODELS` dict.
- If it carries closed-set dims (e.g., `reason: "unknown_user" | "bad_password"`),
  define a new `_DimYourEvent(BaseModel)` class with `model_config =
  ConfigDict(extra="forbid")`, mirror the `_DimApiHit` pattern, then register it.

> **Hard rule:** all string dims must be `Literal[...]`, not bare `str`. The
> audit's drift check is blind to `str`-typed fields, and unbounded cardinality
> blows up the dashboard query cost.

### 3. Map to a resource

In `backend/metrics/resources.py`, add an `EVENT_NAME_TO_RESOURCE` entry pointing
to the right `Resource`. If your event introduces a *new* resource to a category
(e.g., the first DOMAIN-category `Resource.AUTH` event), the dict-derived
`RESOURCE_BY_CATEGORY[EventCategory.DOMAIN]` set will grow.

> **Gotcha:** if you grow `RESOURCE_BY_CATEGORY[DOMAIN]`, the unit test
> `test_resource_by_category_domain_is_crud_only` in
> `tests/unit/test_metrics_resources.py` will fail. Update its expected set AND
> its docstring in the same commit.

### 4. Emit it

**DOMAIN events** — emit from the service layer **after** the relevant
`db.session.commit()`:

```python
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName

# ...inside the service function, after commit:
db.session.commit()
record_event(EventName.URL_ADDED_TO_UTUB)
```

For events with dims:

```python
record_event(
    EventName.LOGIN_FAILURE,
    dimensions={"reason": "bad_password"},
)
```

`device_type` is injected automatically by the writer from the request UA — do
not pass it manually.

**UI events** — emit from TypeScript:

```typescript
import { recordEvent } from "../lib/metrics-client.js";

recordEvent(EventName.UI_FOO_BAR, { target: "utubs" });
```

**API events** — usually auto-counted by middleware; no manual emit needed.
Exception: if you need a counter on a specific code path (e.g.,
`API_METRICS_INGEST_BATCH`), emit manually like a DOMAIN event but ensure your
blueprint is on the middleware's recursion-guard list.

### 5. Document it in the Event Registry

The single source of truth for description + category + closed-set dimension
values lives in `backend/metrics/event_registry.py`. Step 1 above already
added the entry; just double-check the `dimensions` tuples exactly match the
Pydantic `Literal[...]` args you defined in step 2, otherwise the audit will
flag the drift. Example entry:

```python
EventName.LOGIN_FAILURE: EventRegistryEntry(
    description="Login attempt that did not succeed",
    category=EventCategory.DOMAIN,
    dimensions={
        "reason": ("unknown_user", "bad_password", "email_unverified"),
    },
),
```

### 6. Regenerate TypeScript types

```bash
make generate-types
```

This regenerates `frontend/types/metrics-events.ts`, `metrics-dim-values.ts`,
`metrics-resources.ts`, `api.d.ts`, and `openapi.json` as needed. Stage them in
the same commit.

> **Why:** CI's `Generated Types Freshness` job runs the same command and fails
> on any diff. UI-category events with new dim Literals must regen or the
> frontend can't type-check the call site.

### 7. Test it

Minimum coverage:
- Add an assertion to the **existing integration test** that drives the flow
  (e.g., extend `tests/integration/splash/test_login.py` for `LOGIN_SUCCESS`).
- Pattern: assert pre-state (`count_counter_keys(redis, EventName.X) == 0`) →
  perform the action → assert post-state (`== 1`) → for non-`device_type` dims,
  call `parse_dims(key)` and assert the value.
- For events with multiple closed-set dim values (e.g., `LOGIN_FAILURE` reasons),
  parametrize one test per value. A count-only assertion is **insufficient** —
  it can't catch the wrong dim value being emitted.

### 8. Verify

```bash
make audit                                    # passes
make test-marker-parallel m=<your-marker> n=8 # green
make generate-types                           # no diff after second run
```

---

## Recipe 2 — Modify an existing event

### Renaming the EventName

Don't, unless you're willing to migrate historical Postgres rows. The event name
is the join key for all dashboards and the `AnonymousMetrics.event_name` column.
A rename creates a split in your time series.

If you must:
1. Update `EventName.OLD_NAME` → `EventName.NEW_NAME` everywhere (audit will
   find call sites).
2. Update the `EVENT_REGISTRY`, `EVENT_NAME_TO_RESOURCE`, and
   `DIMENSION_MODELS` keys.
3. Write a one-off Alembic migration to `UPDATE "AnonymousMetrics" SET
   event_name = 'new_name' WHERE event_name = 'old_name'`.
4. `make generate-types` + commit.

### Adding a new dim value to a closed-set Literal

E.g., `transport: Literal["fetch", "beacon"]` → adding `"sendbeacon"`:

1. Edit the Literal in `backend/metrics/dimension_models.py`.
2. Append the new value to the matching tuple in
   `backend/metrics/event_registry.py`'s `EVENT_REGISTRY[event].dimensions`.
3. `make generate-types`.
4. Update any frontend code that branches on the dim.
5. `make audit` confirms drift is gone.

### Changing the Resource mapping

Edit `EVENT_NAME_TO_RESOURCE` in `backend/metrics/resources.py`. If you remove
the last event from a `(category, resource)` pair, the unit test asserting
membership in `RESOURCE_BY_CATEGORY` will fail — update it.

### Changing the description

Edit `EVENT_REGISTRY[event].description` in
`backend/metrics/event_registry.py`. Because `EVENT_DESCRIPTIONS` is a derived
projection, all dashboards and TSV outputs pick the new text up automatically.

---

## Recipe 3 — Remove (deprecate) an event

**Critical:** `AnonymousMetrics` rows live in Postgres forever (subject to the
warehouse retention window). "Remove" really means **deprecate the emitter, keep
the schema**.

### Phase 1 — Stop emitting

1. Delete the `record_event(EventName.FOO_BAR)` call(s) in the service layer
   or TS code.
2. Update `EVENT_REGISTRY[EventName.FOO_BAR].description` to start with
   `DEPRECATED YYYY-MM-DD:` — leaves a marker for future readers (and the
   derived `EVENT_DESCRIPTIONS` projection picks the prefix up automatically).
3. Do **not** delete the `EventName` member yet. The audit's orphan check will
   ignore explicitly-deprecated members if you add `EventName.FOO_BAR` to
   `_INTENTIONALLY_UNTRACKED_EVENTS` in `backend/metrics/audit.py` (with a
   comment linking to the deprecation date).
4. `make audit` should still be clean. Commit.

### Phase 2 — Drop after retention window expires

After enough time has passed that no dashboards or queries care about historical
rows (typically 90 days, check with whoever runs the analytics):

1. Remove the member from `EventName`, `EVENT_REGISTRY`, `DIMENSION_MODELS`,
   `EVENT_NAME_TO_RESOURCE`, and `_INTENTIONALLY_UNTRACKED_EVENTS`.
2. Optionally, write an Alembic migration to delete the historical rows from
   `AnonymousMetrics` (only if storage matters).
3. `make generate-types` + `make audit` + commit.

---

## Cross-cutting reference

### Verification commands

| Check                                | Command                                          |
|--------------------------------------|--------------------------------------------------|
| Structural wiring                    | `make audit`                                     |
| Backend tests for your event         | `make test-marker-parallel m=<marker> n=8`       |
| Frontend tests (UI events)           | `make test-js`                                   |
| Generated TS types are fresh         | `make generate-types && git status frontend/types/` |
| Full integration suite               | `make test-integration-parallel n=8`             |

### Common pitfalls

- **Forgetting `make generate-types`** — CI's staleness check fails even if
  every test passes locally.
- **Emitting before `db.session.commit()`** — if the transaction rolls back,
  you've reported a state change that didn't happen.
- **Bare `str` dims** — audit can't validate them; cardinality is unbounded;
  dashboard queries break.
- **Resource.X auto-insertion** — adding the first event mapped to a new
  resource within a category silently grows `RESOURCE_BY_CATEGORY[cat]` and
  breaks the membership unit test.
- **API events without recursion guard** — emitting a metrics event from a
  request handler that itself fires `API_HIT` causes infinite recursion. Check
  `backend/extensions/metrics/middleware.py::should_skip` covers your blueprint.

### What the audit does NOT catch

- Call-site dim correctness (`record_event(EventName.X, dimensions={"wrong_key": "v"})`
  passes the audit, fails at runtime via Pydantic).
- Whether the event is emitted from the *right* place semantically.
- Whether the event still reflects product reality (an unused emitter still
  passes the audit if it's referenced once).

Run the relevant integration test, not just the audit.
