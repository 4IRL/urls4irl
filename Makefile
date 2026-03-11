COMPOSE = docker compose --project-directory . -f docker/compose.local.yaml
COMPOSE_BUILT = docker compose --project-directory . -f docker/compose.local.yaml -f docker/compose.built.yaml
EXEC_WEB = $(COMPOSE) exec web bash -c
EXEC_WEB_BUILT = $(COMPOSE_BUILT) exec web bash -c
EXEC_VITE = $(COMPOSE) exec vite
PYTEST = source /code/venv/bin/activate && python -m pytest

.PHONY: up down build restart test-integration test-integration-parallel test-functional test-ui-parallel test-js test-marker vite-build prune help up-built start-built test-functional-built test-ui-parallel-built test-marker-built

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the full stack
	$(COMPOSE) up --build --remove-orphans

up-built: ## Build and start the full stack using pre-built Vite assets
	$(COMPOSE_BUILT) up --build --remove-orphans

start-built: ## Tear down stack, rebuild with pre-built assets, wait for healthy (used by built test targets)
	$(COMPOSE) down
	$(COMPOSE_BUILT) up --build --remove-orphans --wait

down: ## Stop the stack
	$(COMPOSE) down

build: ## Rebuild images without starting
	$(COMPOSE) build

restart: ## Restart a specific container: make restart c=<service>
	$(COMPOSE) restart $(c)

test-integration: ## Run all integration (non-UI) tests
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui' -v"

test-integration-parallel: ## Run integration tests in parallel: make test-integration-parallel [n=4]
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui' -n $(or $(n),4) --dist=loadscope -v"

test-functional: ## Run all functional (UI/Selenium) tests
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui' -v"

test-functional-built: start-built ## Run all functional (UI/Selenium) tests against built assets
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui' -v"

test-ui-parallel: ## Run UI tests in parallel: make test-ui-parallel [n=12] (matches SE_NODE_MAX_SESSIONS)
	$(EXEC_WEB) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui' -n $(or $(n),12) --dist=loadscope"

test-ui-parallel-built: start-built ## Run UI tests in parallel against built assets: make test-ui-parallel-built [n=12]
	$(EXEC_WEB_BUILT) "$(PYTEST) -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui' -n $(or $(n),12) --dist=loadscope"

test-js: ## Run all JS unit tests (vitest)
	$(EXEC_VITE) npm test

test-marker: ## Run tests for a specific marker: make test-marker m=<marker>
	$(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -v"

test-marker-built: start-built ## Run tests for a specific marker against built assets: make test-marker-built m=<marker>
	$(EXEC_WEB_BUILT) "$(PYTEST) tests/ -m '$(m)' -v"

test-last-failed: ## Run tests for a specific marker: make test-marker m=<marker>
	$(EXEC_WEB) "$(PYTEST) tests/ -v --lf"

vite-build: ## Build Vite to verify no import/syntax errors
	$(EXEC_VITE) npx vite build

prune: ## Prune Docker build cache to free disk space
	docker builder prune -f
