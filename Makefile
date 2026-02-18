COMPOSE = docker compose --project-directory . -f docker/compose.local.yaml
EXEC_WEB = $(COMPOSE) exec web bash -c
EXEC_VITE = $(COMPOSE) exec vite
PYTEST = source /code/venv/bin/activate && python -m pytest

.PHONY: up down build restart test-integration test-functional test-js test-marker vite-build help

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the full stack
	$(COMPOSE) up --build --remove-orphans

down: ## Stop the stack
	$(COMPOSE) down

build: ## Rebuild images without starting
	$(COMPOSE) build

restart: ## Restart a specific container: make restart c=<service>
	$(COMPOSE) restart $(c)

test-integration: ## Run all integration (non-UI) tests
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'not splash_ui and not home_ui and not utubs_ui and not members_ui and not urls_ui and not create_urls_ui and not update_urls_ui and not tags_ui and not mobile_ui' -v"

test-functional: ## Run all functional (UI/Selenium) tests
	$(EXEC_WEB) "$(PYTEST) tests/ -m 'splash_ui or home_ui or utubs_ui or members_ui or urls_ui or create_urls_ui or update_urls_ui or tags_ui or mobile_ui' -v"

test-js: ## Run all JS unit tests (vitest)
	$(EXEC_VITE) npm test

test-marker: ## Run tests for a specific marker: make test-marker m=<marker>
	$(EXEC_WEB) "$(PYTEST) tests/ -m '$(m)' -v"

vite-build: ## Build Vite to verify no import/syntax errors
	$(EXEC_VITE) npx vite build
