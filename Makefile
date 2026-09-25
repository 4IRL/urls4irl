COMPOSE = docker compose --project-directory . -f docker/compose.local.yaml
COMPOSE_BUILT = docker compose --project-directory . -f docker/compose.local.yaml -f docker/compose.built.yaml
EXEC_WEB = $(COMPOSE) exec web bash -c
EXEC_WEB_BUILT = $(COMPOSE_BUILT) exec web bash -c
EXEC_VITE = $(COMPOSE) exec vite
PYTEST = source /code/venv/bin/activate && python -m pytest
FLASK = source /code/venv/bin/activate && flask
MISE = mise exec --
FRONTEND_BIN = frontend/node_modules/.bin
# Recursive `=` so git only runs for the shell targets; `wildcard` drops tracked-but-deleted paths. Paths must not contain spaces.
SHELL_FILES = $(wildcard $(shell git ls-files '*.sh' ':!:.claude/hooks/*' ':!:.claude/worktrees/*' 2>/dev/null))
NOTIFY_TEST_DEFAULT_MSG = **Daily Backup — SUCCESS**\n✅ 💾 Database\n✅ 📄 Logs\n✅ ☁️ R2 daily\n💤 ☁️ R2 monthly\n✅ ☁️ R2 logs\n\n**Metrics — HEALTHY**\n🟢 📊 Minute Flush · 38s ago\n🟢 📊 Hourly Snapshot · 12m ago

.PHONY: hooks hooks-check tools mise-config-check lockfile-check _require-tools _require-shell-files up down build restart test-integration test-integration-parallel test-functional test-ui-parallel test-js test-js-built test-backup-pipeline test-marker test-file test-file-parallel test-file-parallel-built vite-build vite-build-built typecheck lint lint-python lint-frontend lint-shell lint-actions format format-check format-check-python format-check-frontend format-check-shell prune help up-built start-built test-functional-built test-ui-parallel-built test-marker-built test-marker-parallel test-marker-parallel-built generate-types clear-db reset-db metrics-watch metrics-snapshot metrics-flush-now metrics-rows metrics-smoke-test metrics-clear-counters metrics-clear-rows metrics-clear-all gauge-sample-now gauge-rows gauge-clear-rows notify-test addmock audit plan-list playwright-unlock tunnel tunnel-stop

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# -V (--renew-anon-volumes): recreate anonymous volumes (vite's /app/node_modules masks) on every up,
# so a stale pre-bump node_modules never shadows the freshly built image's pnpm install. Named volumes are unaffected.
up: ## Build and start the full stack (pass d=1 for detached mode)
	$(COMPOSE) up --build --remove-orphans -V $(if $(d),-d,)

up-built: ## Build and start the full stack using pre-built Vite assets (pass d=1 for detached mode)
	$(COMPOSE_BUILT) up --build --remove-orphans -V $(if $(d),-d,)

start-built: prune ## Tear down stack, rebuild with pre-built assets, wait for healthy (used by built test targets)
	$(COMPOSE) down
	$(COMPOSE_BUILT) up --build --remove-orphans --wait

down: ## Stop the stack
	$(COMPOSE) down

build: ## Rebuild images without starting
	$(COMPOSE) build

restart: ## Restart a specific container: make restart c=<service>
	$(COMPOSE) restart $(c)

tunnel: ## Force the built stack up (mobile-ready assets, no localhost:5173 dependency) + start an on-demand public Cloudflare tunnel and print its URL
	$(COMPOSE_BUILT) up --build --remove-orphans -V -d --wait
	$(COMPOSE_BUILT) --profile tunnel up -d --no-recreate cloudflared
	@echo "Waiting for Cloudflare quick-tunnel URL (~5-10s)..."
	@for i in $$(seq 1 30); do \
		url=$$($(COMPOSE_BUILT) logs cloudflared 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1); \
		if [ -n "$$url" ]; then echo "TUNNEL URL: $$url"; exit 0; fi; \
		sleep 1; \
	done; \
	echo "URL not ready yet — check: $(COMPOSE_BUILT) logs cloudflared"

tunnel-stop: ## Stop and remove the Cloudflare tunnel (leaves the rest of the stack running)
	$(COMPOSE) --profile tunnel rm -sf cloudflared

test-integration: ## Run all integration (non-UI) tests
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui and not metrics_ui and not settings_ui and not search_ui and not admin_ui' -v"

test-integration-parallel: ## Run integration tests in parallel: make test-integration-parallel [n=4, max n=8]
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui and not metrics_ui and not settings_ui and not search_ui and not admin_ui' -n $(or $(n),4) --dist=loadscope -v"

test-functional: prune ## Run all functional (UI/Playwright) tests
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -v"

test-functional-built: start-built ## Run all functional (UI/Playwright) tests against built assets
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -v"

test-ui-parallel: prune ## Run UI tests in parallel: make test-ui-parallel [n=8] (max n=8: redis-metrics has 16 DBs, so gw8 errors on app-backed tests; see CLAUDE.md)
	$(EXEC_WEB) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -n $(or $(n),8) --dist=loadscope"

test-ui-parallel-built: start-built ## Run UI tests in parallel against built assets: make test-ui-parallel-built [n=8] (max n=8, see CLAUDE.md)
	$(EXEC_WEB_BUILT) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui or admin_ui' -n $(or $(n),8) --dist=loadscope"

test-js: ## Run all JS unit tests (vitest)
	$(EXEC_VITE) pnpm test

test-js-built: ## Run all JS unit tests in the built stack (one-off vite container; used when up-built is running and the long-lived dev vite service is absent)
	$(COMPOSE_BUILT) run --rm --no-deps vite pnpm test

test-backup-pipeline: ## Build web+workflow images and run the backup pipeline E2E harness locally
	docker build -f docker/Dockerfile.Local    -t u4i-local-web:test .
	docker build -f docker/Dockerfile.Workflow -t u4i-local-workflow:test .
	chmod +x docker/backup-pipeline-test.sh docker/backup-pipeline-driver.sh
	docker/backup-pipeline-test.sh u4i-local-web:test u4i-local-workflow:test

test-marker: ## Run tests for a specific marker: make test-marker m=<marker>
	$(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -v"

test-marker-built: start-built ## Run tests for a specific marker against built assets: make test-marker-built m=<marker>
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m '$(m)' -v"

test-marker-parallel: ## Run tests for a specific marker in parallel: make test-marker-parallel m=<marker> [n=4, max n=8]
	$(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -n $(or $(n),4) --dist=loadscope -v"

test-marker-parallel-built: start-built ## Run tests for a specific marker in parallel against built assets: make test-marker-parallel-built m=<marker> [n=4, max n=8]
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m '$(m)' -n $(or $(n),4) --dist=loadscope -v"

test-last-failed: ## Run tests for a specific marker: make test-marker m=<marker>
	$(EXEC_WEB) "$(PYTEST) tests/ -v --lf"

test-file: ## Run pytest against a specific file or path: make test-file f=<path> [args=<extra-pytest-args>]
	$(EXEC_WEB) "$(PYTEST) $(f) -v $(args)"

test-file-parallel: ## Run pytest against a specific file or path in parallel: make test-file-parallel f=<path> [n=4, max n=8] [args=<extra-pytest-args>]
	$(EXEC_WEB) "$(PYTEST) $(f) -n $(or $(n),4) --dist=loadscope -v $(args)"

test-file-parallel-built: start-built ## Run pytest against a specific file or path in parallel against built assets: make test-file-parallel-built f=<path> [n=4, max n=8] [args=<extra-pytest-args>]
	$(EXEC_WEB_BUILT) "$(PYTEST) $(f) -n $(or $(n),4) --dist=loadscope -v $(args)"

vite-build: ## Build Vite to verify no import/syntax errors
	$(EXEC_VITE) pnpm exec vite build

vite-build-built: ## Rebuild Vite assets in the built stack (one-off vite build container; used when up-built is running and the long-lived dev vite service is absent)
	$(COMPOSE_BUILT) run --rm --no-deps vite pnpm exec vite build

lint: lint-python lint-frontend lint-shell lockfile-check lint-actions ## Run all linters (same command CI and pre-commit run)

lint-python: _require-tools ## Lint Python with ruff
	$(MISE) ruff check .

lint-frontend: _require-tools ## Lint JS and TS with eslint
	cd frontend && $(MISE) ./node_modules/.bin/eslint "**/*.js" --no-config-lookup --ignore-pattern node_modules
	cd frontend && $(MISE) ./node_modules/.bin/eslint "**/*.ts"

lint-shell: _require-tools _require-shell-files ## Lint shell scripts with shellcheck
	$(MISE) shellcheck --severity=warning -x $(SHELL_FILES)

# The -ignore is an actionlint schema gap, not a repo issue: `command:` under a workflow `services:` entry is valid GitHub Actions syntax (test.yml's redis-metrics) but missing from actionlint's schema.
lint-actions: _require-tools ## Lint GitHub Actions workflows
	$(MISE) actionlint -ignore 'unexpected key "command" for "services" section'

format-check: format-check-python format-check-frontend format-check-shell ## Check formatting (no writes)

format-check-python: _require-tools ## Check Python formatting with ruff
	$(MISE) ruff format --check .

format-check-frontend: _require-tools ## Check JS and TS formatting with prettier
	cd frontend && $(MISE) ./node_modules/.bin/prettier --check "**/*.{ts,js}"

format-check-shell: _require-tools _require-shell-files ## Check shell formatting with shfmt
	$(MISE) shfmt -i 2 -ci -d $(SHELL_FILES)

format: _require-tools _require-shell-files ## Apply all formatters
	$(MISE) ruff format .
	cd frontend && $(MISE) ./node_modules/.bin/prettier --write "**/*.{ts,js}"
	$(MISE) shfmt -i 2 -ci -w $(SHELL_FILES)

typecheck: _require-tools ## Run TypeScript typecheck (app + test tsconfigs) on the host
	$(MISE) $(FRONTEND_BIN)/tsc --noEmit --project frontend/tsconfig.json
	$(MISE) $(FRONTEND_BIN)/tsc --noEmit --project frontend/tsconfig.test.json

generate-types: ## Generate TypeScript API types from backend OpenAPI spec + per-event dim shapes
	$(EXEC_WEB) "$(FLASK) openapi generate --output /code/u4i/frontend/types/openapi.json --strict"
	$(EXEC_VITE) pnpm exec openapi-typescript frontend/types/openapi.json -o frontend/types/api.d.ts
	$(EXEC_WEB) "$(FLASK) metrics generate-dim-types --output /code/u4i/frontend/types/metrics-dimensions.d.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-dim-values --output /code/u4i/frontend/types/metrics-dim-values.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-events --output /code/u4i/frontend/types/metrics-events.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-resources --output /code/u4i/frontend/types/metrics-resources.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-flows --output /code/u4i/frontend/types/metrics-flows.ts"
	$(EXEC_VITE) pnpm exec prettier --write frontend/types/api.d.ts frontend/types/openapi.json frontend/types/metrics-dimensions.d.ts frontend/types/metrics-dim-values.ts frontend/types/metrics-events.ts frontend/types/metrics-resources.ts frontend/types/metrics-flows.ts

audit: ## Run the metrics event coverage audit (exits non-zero if gaps found)
	$(EXEC_WEB) "$(FLASK) metrics audit --strict"

addmock: ## Seed the dev database with all mock data (flask addmock all)
	$(EXEC_WEB) "$(FLASK) addmock all"

clear-db: ## Empty every table in the dev database (same schema, no data) — frees any registered email/username for reuse
	$(EXEC_WEB) "$(FLASK) managedb clear dev"

reset-db: clear-db addmock ## Empty the dev database, then reseed all mock data (seeded users/UTubs restored)

plan-list: ## List every plan (masters + sub-plans) under plans/ with finished/open status
	@.claude/scripts/plan-list.sh

playwright-unlock: ## Kill orphaned Playwright-MCP Chrome holding the profile lock and clear stale Singleton* files
	@.claude/scripts/playwright-unlock.sh

hooks: ## Install the pre-commit git hook (one-time per clone; creates ./venv with the pinned pre-commit)
	@test -x venv/bin/pre-commit || python3.11 -m venv venv
	@venv/bin/pip install --quiet --disable-pip-version-check \
		$$(grep -E '^pre-commit==' requirements/requirements-dev.txt)
	@venv/bin/pre-commit install
	@venv/bin/pre-commit --version

hooks-check: ## Report whether the pre-commit hook is installed in this clone
	@test -f .git/hooks/pre-commit \
		&& echo "pre-commit hook: INSTALLED" \
		|| echo "pre-commit hook: MISSING — run 'make hooks'"

# .mise.toml is deliberately never `mise trust`ed: a pin-only config (min_version + plain [tools] strings) loads untrusted, and mise's own trust check refuses anything more at runtime.
# mise-config-check (run by `tools` after `mise install`, and by CI's Format and Lint jobs; uses mise's own python via `mise exec python --`, never a system one): a post-hoc policy lint for contexts where mise's trust check won't fire (CI / trusted clones).
# It keeps .mise.toml to min_version + plain `[tools] name = "version"` pins, and asserts both Dockerfiles' `ARG PNPM_VERSION=` equals the [tools] pnpm pin (one logical pin; images need their own literal). In an untrusted clone, mise's trust error fires first.
# `pnpm install --frozen-lockfile --ignore-scripts`: no dependency install/postinstall scripts run on the host, and a lockfile out of sync with package.json fails instead of being rewritten.
tools: ## Install the pinned host toolchain (.mise.toml) + frontend node_modules; set git blame ignore-revs
	@command -v mise >/dev/null || { echo "mise not installed — see https://mise.jdx.dev/installing-mise.html (Linux: curl https://mise.run | sh; macOS: brew install mise)"; exit 1; }
	@mise install || { echo "make tools: mise install failed (see above). If it says .mise.toml is 'not trusted', the file has more than min_version + plain [tools] pins: remove that config instead of running 'mise trust'."; exit 1; }
	@$(MAKE) --no-print-directory mise-config-check
	cd frontend && $(MISE) pnpm install --frozen-lockfile --ignore-scripts
	git config blame.ignoreRevsFile .git-blame-ignore-revs

mise-config-check: ## Fail unless .mise.toml is pin-only and the Dockerfiles' ARG PNPM_VERSION matches its pnpm pin
	@mise exec python -- python -c 'import sys, re, tomllib; c = tomllib.load(open(".mise.toml", "rb")); t = c.get("tools", {}); bad = sorted(set(c) - {"min_version", "tools"}) + (sorted("tools." + k for k, v in t.items() if not isinstance(v, str)) if isinstance(t, dict) else ["tools"]); bad and sys.exit(".mise.toml has non-version-pin config (" + ", ".join(bad) + "); only min_version and plain [tools] version pins are allowed"); pnpm_pin = t.get("pnpm"); pat = re.compile(r"^ARG PNPM_VERSION=(\S+)$$", re.M); found = {f: (m.group(1) if (m := pat.search(open(f).read())) else "MISSING") for f in ("docker/Dockerfile.Vite", "docker/Dockerfile")}; mism = {f: v for f, v in found.items() if v != pnpm_pin}; mism and sys.exit("ARG PNPM_VERSION mismatch (.mise.toml pnpm=" + str(pnpm_pin) + "): " + ", ".join(f + "=" + v for f, v in mism.items()))'

lockfile-check: ## Fail if an npm lockfile/.npmrc reappears next to pnpm-lock.yaml
	@test -f frontend/pnpm-lock.yaml || { echo "lockfile-check: frontend/pnpm-lock.yaml is missing"; exit 1; }
	@test -f frontend/pnpm-workspace.yaml || { echo "lockfile-check: frontend/pnpm-workspace.yaml is missing"; exit 1; }
	@for npm_file in frontend/package-lock.json frontend/.npmrc; do \
		if test -e "$$npm_file" || test -L "$$npm_file"; then echo "lockfile-check: $$npm_file must not exist (frontend/ is pnpm-only; never run npm install there)"; exit 1; fi; \
	done

# Private prerequisite guards (_require-*) deliberately have no "## desc" so they stay out of 'make help'.
_require-tools:
	@command -v mise >/dev/null && test -x $(FRONTEND_BIN)/prettier || { echo "host lint toolchain missing — run 'make tools'"; exit 1; }

# An empty list would make shfmt read stdin (hang, or pass silently in CI), so fail loudly instead.
_require-shell-files:
	@test -n "$(SHELL_FILES)" || { echo "no shell files found (not a git checkout, or git ls-files failed)"; exit 1; }

prune: ## Prune dangling images, orphaned volumes, and build cache
	docker image prune -f
	docker volume prune -f
	docker builder prune -f

metrics-watch: ## Live tail Redis ops on dedicated redis-metrics container (requires METRICS_ENABLED=true on web)
	$(COMPOSE) exec redis-metrics redis-cli MONITOR

metrics-snapshot: ## Snapshot current metrics:counter:* keys with values
	$(COMPOSE) exec redis-metrics sh -c 'for k in $$(redis-cli --scan --pattern "metrics:counter:*"); do echo "$$k = $$(redis-cli GET $$k)"; done'

metrics-flush-now: ## Trigger an immediate flush worker run (drains Redis -> Postgres)
	$(COMPOSE) exec workflow sh -c 'if [ ! -f /app/container_environment ]; then echo "ERROR: /app/container_environment missing on workflow container. Run make up d=1 first." >&2; exit 1; fi; set -a && . /app/container_environment && set +a && /opt/metrics-venv/bin/python /app/flush_metrics.py'

metrics-rows: ## Show last 25 flushed rows from AnonymousMetrics
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT \"bucketStart\", \"eventName\", endpoint, method, \"statusCode\", dimensions, count FROM \"AnonymousMetrics\" ORDER BY \"bucketStart\" DESC LIMIT 25;"'

metrics-smoke-test: metrics-snapshot metrics-flush-now metrics-rows ## E2E: snapshot Redis, force flush, dump Postgres rows

metrics-clear-counters: ## Delete pending Redis state (metrics:counter:* and metrics:batch:*); leaves flush lock/sentinel intact
	$(COMPOSE) exec redis-metrics sh -c 'redis-cli --scan --pattern "metrics:counter:*" | xargs -r redis-cli UNLINK; redis-cli --scan --pattern "metrics:batch:*" | xargs -r redis-cli UNLINK'

metrics-clear-rows: ## Truncate AnonymousMetrics in Postgres
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "TRUNCATE TABLE \"AnonymousMetrics\";"'

metrics-clear-all: metrics-clear-counters metrics-clear-rows gauge-clear-rows ## Wipe all metrics data (Redis pending + Postgres flushed + gauges)

gauge-sample-now: ## Trigger an immediate gauge sampler run (writes one AnonymousGauges row per gauge)
	$(COMPOSE) exec workflow sh -c 'if [ ! -f /app/container_environment ]; then echo "ERROR: /app/container_environment missing on workflow container. Run make up d=1 first." >&2; exit 1; fi; set -a && . /app/container_environment && set +a && /opt/metrics-venv/bin/python /app/sample_gauges.py'

gauge-rows: ## Show last 25 sampled rows from AnonymousGauges
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT \"gaugeName\", \"sampledAt\", \"valueInt\", \"valueFloat\", dimensions FROM \"AnonymousGauges\" ORDER BY \"sampledAt\" DESC LIMIT 25;"'

gauge-clear-rows: ## Truncate AnonymousGauges in Postgres
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "TRUNCATE TABLE \"AnonymousGauges\";"'

notify-test: ## Post a message to the Discord webhook (NOTIFICATION_URL from the environment, else from .env) via restricted_curl in the workflow container (msg optional, defaults to a sample digest): make notify-test [msg="DOCKER: your message"]
	@url="$${NOTIFICATION_URL:-}"; \
	if [ -z "$$url" ] && [ -f .env ]; then \
	  line="$$(grep -E 'NOTIFICATION_URL[[:space:]]*=' .env | grep -v '^[[:space:]]*#' | tail -n1)"; \
	  url="$${line#*=}"; \
	  url="$$(printf '%s' "$$url" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$$//' -e 's/^["'\'']//' -e 's/["'\'']$$//' | tr -d '\r\n')"; \
	fi; \
	if [ -z "$$url" ]; then echo 'Usage: set NOTIFICATION_URL in the environment or .env, then run: make notify-test [msg="DOCKER: your message"]' >&2; echo 'restricted_curl posts the message verbatim (it does NOT prepend "DOCKER: "); include it yourself to match production. No raw " \\ or newlines (restricted_curl does not JSON-escape).' >&2; exit 1; fi; \
	echo "Posting msg to the Discord webhook in NOTIFICATION_URL via the workflow container..."; \
	$(COMPOSE) exec workflow restricted_curl POST "$$url" "$(or $(msg),$(NOTIFY_TEST_DEFAULT_MSG))"
