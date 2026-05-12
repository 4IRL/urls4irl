# Local `redis-metrics` Verification Runbook

Manual end-to-end verification that the dedicated `redis-metrics` container is wired correctly in the local stack and that the anonymous-metrics pipeline ingests writes against it (not the shared `redis`).

Run top-to-bottom. Each step has a pass criterion; deviations point to a specific wiring bug.

## Setup

```bash
make down                       # ensure clean state — testing on stale state masks wiring bugs
METRICS_ENABLED=true make up d=1
docker compose --project-directory . -f docker/compose.local.yaml ps
```

**Pass:** both `u4i-local-redis` and `u4i-local-redis-metrics` are listed and show `(healthy)`.

- Missing `redis-metrics` → service was never added to `compose.local.yaml`.
- `(unhealthy)` → `docker compose logs redis-metrics` for startup errors (most likely a bad `--maxmemory` value or port conflict).

## Step 1 — Dedicated container has the expected runtime config

```bash
docker compose exec redis-metrics redis-cli CONFIG GET maxmemory
docker compose exec redis-metrics redis-cli CONFIG GET maxmemory-policy
docker compose exec redis-metrics redis-cli CONFIG GET save
docker compose exec redis-metrics redis-cli CONFIG GET appendonly
docker compose exec redis-metrics redis-cli CONFIG GET databases
```

| Setting            | Expected              |
|--------------------|-----------------------|
| `maxmemory`        | `268435456` (256 MiB) |
| `maxmemory-policy` | `allkeys-lru`         |
| `save`             | `""` (empty)          |
| `appendonly`       | `no`                  |
| `databases`        | `16`                  |

## Step 2 — Consumers are pointed at the new container

```bash
docker compose exec web sh -c 'echo $METRICS_REDIS_URI'
docker compose exec workflow grep METRICS_REDIS_URI /app/container_environment
```

**Pass:** both print `redis://redis-metrics:6379/0`.

**Fail** (prints `redis://redis:6379/2`) → env wiring still on the old shared instance.

## Step 3 — Shared `redis` is empty of metrics keys at startup

```bash
docker compose exec redis redis-cli -n 0 KEYS 'metrics:*'
docker compose exec redis redis-cli -n 2 KEYS '*'
```

**Pass:** both return empty. Proves the runtime never touches the shared instance for metrics.

## Step 4 — Drive a write through the live app

```bash
curl -sI http://127.0.0.1:8659/ > /dev/null
```

Or just load the homepage in a browser. Either path hits the splash route and increments an `api_hit` counter.

## Step 5 — Write landed on `redis-metrics` DB 0

```bash
make metrics-snapshot
```

**Pass:** at least one `metrics:counter:<bucket>:api_hit:...=1` (or `=N` for N curls) line.

Cross-check directly:

```bash
docker compose exec redis-metrics redis-cli KEYS 'metrics:counter:*'
```

## Step 6 — Shared `redis` is *still* empty

```bash
docker compose exec redis redis-cli -n 0 KEYS 'metrics:*'
docker compose exec redis redis-cli -n 2 KEYS '*'
```

**Pass:** still empty. This is the structural guarantee — the dedicated container can fill up without touching session DB.

## Step 7 — Flush worker reads from `redis-metrics`, writes to Postgres

```bash
make metrics-flush-now
make metrics-rows
```

**Pass:** `metrics-flush-now` logs `upserted=N` for some `N>=1`, and `metrics-rows` shows recent rows for the current hour bucket.

Verify the liveness sentinel was updated on the dedicated container:

```bash
docker compose exec redis-metrics redis-cli GET metrics:flush:last_success_epoch
```

**Pass:** returns a Unix epoch within the last few seconds.

## Step 8 — Operator Make targets all point at the right container

```bash
make metrics-snapshot           # already exercised in Step 5
make metrics-watch              # streams live ops; Ctrl-C to exit (you should see PINGs from the liveness checker)
make metrics-clear-counters     # silently UNLINKs all counters
make metrics-snapshot           # now prints nothing
docker compose exec redis-metrics redis-cli GET metrics:flush:last_success_epoch
                                # still returns the prior epoch — the sentinel survived the counter clear
make metrics-smoke-test         # snapshot -> flush -> rows
```

## Step 9 — Eviction actually evicts under memory pressure (optional stress test)

Demonstrates the structural promise: when memory fills, counters are LRU-evicted rather than refusing writes.

```bash
docker compose exec redis-metrics redis-cli CONFIG SET maxmemory 1mb
docker compose exec redis-metrics redis-cli CONFIG RESETSTAT

for i in {1..2000}; do curl -s http://127.0.0.1:8659/ > /dev/null; done

docker compose exec redis-metrics redis-cli INFO stats | grep evicted_keys

docker compose exec redis redis-cli -n 0 KEYS 'metrics:*'
docker compose exec redis redis-cli -n 2 KEYS '*'

docker compose exec redis-metrics redis-cli CONFIG SET maxmemory 268435456
```

**Pass:** `evicted_keys:N` for some `N>0`, AND shared `redis` still has no `metrics:*` keys.

**Fail mode:** if you see `OOM command not allowed when used with 'maxmemory'` in `docker compose logs web | grep OOM`, the eviction policy wasn't applied — recheck Step 1's `maxmemory-policy=allkeys-lru`.

The deterministic automated equivalent is `make test-file f=tests/integration/system/test_metrics_redis_isolation.py`.

## Cleanup

```bash
make metrics-clear-all          # wipes any leftover counters + Postgres rows
make down                       # stops the stack
```

## Failure-mode reference

| Symptom                                                  | Likely cause                                                                  |
|----------------------------------------------------------|-------------------------------------------------------------------------------|
| `redis-metrics` container missing from `ps`              | `compose.local.yaml` change not applied — `make down && make up d=1` again    |
| `redis-metrics` unhealthy                                | `docker compose logs redis-metrics` — check `--maxmemory` value or port       |
| `metrics-snapshot` prints nothing after a curl           | `METRICS_ENABLED` not set, or web container started before the env change     |
| Counters appear on shared `redis` (`-n 2`)               | Web container env still points at old URI — `make restart c=web`              |
| `metrics-flush-now` succeeds but `metrics-rows` is empty | Flush worker is hitting a different Postgres than expected — check workflow env|
| OOM error in web logs during Step 9                      | `maxmemory-policy` not `allkeys-lru` on the dedicated container               |
