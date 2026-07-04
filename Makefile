COMPOSE = docker compose --project-directory . -f docker/compose.local.yaml
COMPOSE_BUILT = docker compose --project-directory . -f docker/compose.local.yaml -f docker/compose.built.yaml
EXEC_WEB = $(COMPOSE) exec web bash -c
EXEC_WEB_BUILT = $(COMPOSE_BUILT) exec web bash -c
EXEC_VITE = $(COMPOSE) exec vite
PYTEST = source /code/venv/bin/activate && python -m pytest
FLASK = source /code/venv/bin/activate && flask
NOTIFY_TEST_DEFAULT_MSG = **Daily Backup — SUCCESS**\n✅ 💾 Database\n✅ 📄 Logs\n✅ ☁️ R2 daily\n💤 ☁️ R2 monthly\n✅ ☁️ R2 logs\n\n**Metrics — HEALTHY**\n🟢 📊 Minute Flush · 38s ago\n🟢 📊 Hourly Snapshot · 12m ago

.PHONY: up down build restart test-integration test-integration-parallel test-functional test-ui-parallel test-js test-backup-pipeline test-marker test-file test-file-parallel test-file-parallel-built vite-build typecheck prune help up-built start-built test-functional-built test-ui-parallel-built test-marker-built test-marker-parallel test-marker-parallel-built generate-types metrics-watch metrics-snapshot metrics-flush-now metrics-rows metrics-smoke-test metrics-clear-counters metrics-clear-rows metrics-clear-all gauge-sample-now gauge-rows gauge-clear-rows notify-test addmock audit plan-list playwright-unlock tunnel tunnel-stop

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the full stack (pass d=1 for detached mode)
	$(COMPOSE) up --build --remove-orphans $(if $(d),-d,)

up-built: ## Build and start the full stack using pre-built Vite assets (pass d=1 for detached mode)
	$(COMPOSE_BUILT) up --build --remove-orphans $(if $(d),-d,)

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
	$(COMPOSE_BUILT) up --build --remove-orphans -d --wait
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
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui and not metrics_ui and not settings_ui and not search_ui' -v"

test-integration-parallel: ## Run integration tests in parallel: make test-integration-parallel [n=4]
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui and not metrics_ui and not settings_ui and not search_ui' -n $(or $(n),4) --dist=loadscope -v"

test-functional: prune ## Run all functional (UI/Selenium) tests
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui' -v"

test-functional-built: start-built ## Run all functional (UI/Selenium) tests against built assets
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui' -v"

test-ui-parallel: prune ## Run UI tests in parallel: make test-ui-parallel [n=8] (SE_NODE_MAX_SESSIONS=12, but n=8 avoids host resource saturation)
	$(EXEC_WEB) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui' -n $(or $(n),8) --dist=loadscope"

test-ui-parallel-built: start-built ## Run UI tests in parallel against built assets: make test-ui-parallel-built [n=8]
	$(EXEC_WEB_BUILT) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui or metrics_ui or settings_ui or search_ui' -n $(or $(n),8) --dist=loadscope"

test-js: ## Run all JS unit tests (vitest)
	$(EXEC_VITE) npm test

test-backup-pipeline: ## Build web+workflow images and run the backup pipeline E2E harness locally
	docker build -f docker/Dockerfile.Local    -t u4i-local-web:test .
	docker build -f docker/Dockerfile.Workflow -t u4i-local-workflow:test .
	chmod +x docker/backup-pipeline-test.sh docker/backup-pipeline-driver.sh
	docker/backup-pipeline-test.sh u4i-local-web:test u4i-local-workflow:test

test-marker: ## Run tests for a specific marker: make test-marker m=<marker>
	$(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -v"

test-marker-built: start-built ## Run tests for a specific marker against built assets: make test-marker-built m=<marker>
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m '$(m)' -v"

test-marker-parallel: ## Run tests for a specific marker in parallel: make test-marker-parallel m=<marker> [n=4]
	$(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -n $(or $(n),4) --dist=loadscope -v"

test-marker-parallel-built: start-built ## Run tests for a specific marker in parallel against built assets: make test-marker-parallel-built m=<marker> [n=4]
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m '$(m)' -n $(or $(n),4) --dist=loadscope -v"

test-last-failed: ## Run tests for a specific marker: make test-marker m=<marker>
	$(EXEC_WEB) "$(PYTEST) tests/ -v --lf"

test-file: ## Run pytest against a specific file or path: make test-file f=<path> [args=<extra-pytest-args>]
	$(EXEC_WEB) "$(PYTEST) $(f) -v $(args)"

test-file-parallel: ## Run pytest against a specific file or path in parallel: make test-file-parallel f=<path> [n=4] [args=<extra-pytest-args>]
	$(EXEC_WEB) "$(PYTEST) $(f) -n $(or $(n),4) --dist=loadscope -v $(args)"

test-file-parallel-built: start-built ## Run pytest against a specific file or path in parallel against built assets: make test-file-parallel-built f=<path> [n=4] [args=<extra-pytest-args>]
	$(EXEC_WEB_BUILT) "$(PYTEST) $(f) -n $(or $(n),4) --dist=loadscope -v $(args)"

vite-build: ## Build Vite to verify no import/syntax errors
	$(EXEC_VITE) npx vite build

typecheck: ## Run TypeScript typecheck
	$(EXEC_VITE) npm run typecheck

generate-types: ## Generate TypeScript API types from backend OpenAPI spec + per-event dim shapes
	$(EXEC_WEB) "$(FLASK) openapi generate --output /code/u4i/frontend/types/openapi.json --strict"
	$(EXEC_VITE) npx openapi-typescript frontend/types/openapi.json -o frontend/types/api.d.ts
	$(EXEC_WEB) "$(FLASK) metrics generate-dim-types --output /code/u4i/frontend/types/metrics-dimensions.d.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-dim-values --output /code/u4i/frontend/types/metrics-dim-values.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-events --output /code/u4i/frontend/types/metrics-events.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-resources --output /code/u4i/frontend/types/metrics-resources.ts"
	$(EXEC_WEB) "$(FLASK) metrics generate-flows --output /code/u4i/frontend/types/metrics-flows.ts"
	$(EXEC_VITE) npx prettier --write frontend/types/api.d.ts frontend/types/openapi.json frontend/types/metrics-dimensions.d.ts frontend/types/metrics-dim-values.ts frontend/types/metrics-events.ts frontend/types/metrics-resources.ts frontend/types/metrics-flows.ts

audit: ## Run the metrics event coverage audit (exits non-zero if gaps found)
	$(EXEC_WEB) "$(FLASK) metrics audit --strict"

addmock: ## Seed the dev database with all mock data (flask addmock all)
	$(EXEC_WEB) "$(FLASK) addmock all"

plan-list: ## List every plan (masters + sub-plans) under plans/ with finished/open status
	@.claude/scripts/plan-list.sh

playwright-unlock: ## Kill orphaned Playwright-MCP Chrome holding the profile lock and clear stale Singleton* files
	@.claude/scripts/playwright-unlock.sh

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
