.DEFAULT_GOAL := help
SHELL := /bin/bash

# Compose files. The VPS override layers TLS and login on top of the same stack.
COMPOSE := docker compose -f docker-compose.all-in-one.yml
COMPOSE_VPS := $(COMPOSE) -f docker-compose.vps.yml

# sre-control mounts the repo at this same absolute path, so compose paths resolve identically.
export WORKSHOP_DIR := $(CURDIR)

.PHONY: help env build up down ps logs check book e2e score chaos chaos-reset

help: ## List every target
	@grep -E '^[a-z0-9-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[33m%-12s\033[0m %s\n", $$1, $$2}'

env: ## Add any missing generated secrets to .env (never overwrites a value)
	@uv run --quiet python scripts/generate_env.py

build: env ## Build the local images, including both subscription-app releases
	$(COMPOSE) build
	APP_RELEASE=v2 $(COMPOSE) build subscription-app

up: build ## Start the stack, wait until every service is healthy, create the workshop logins
	$(COMPOSE) up -d --wait --wait-timeout 600
	@uv run --quiet python scripts/bootstrap_users.py

up-vps: build ## On a VPS: the same stack behind Caddy with TLS, only ports 80 and 443 open
	$(COMPOSE_VPS) up -d --wait --wait-timeout 900
	@uv run --quiet python scripts/bootstrap_users.py

down: ## Stop the stack (data is kept)
	$(COMPOSE) --profile browser-load down

ps: ## Show service health
	$(COMPOSE) ps

logs: ## Follow logs for one service: make logs SERVICE=sre-control
	$(COMPOSE) logs -f $(SERVICE)

check: ## Lint, unit and structural tests (no Docker, no model spend)
	@mkdir -p artifacts && rm -f artifacts/junit.xml
	@uv run --quiet python scripts/tree_hash.py --all > artifacts/check-tree.txt
	uv run --quiet ruff check .
	uv run --quiet ruff format --check .
	uv run --quiet python scripts/check_prose.py
	uv run --quiet pytest --continue-on-collection-errors --junitxml=artifacts/junit.xml

# Declared here, not in the .PHONY line above the first target: that line is inside the e2e stamp,
# and a target that prints a page must not cost a Docker run to re-certify.
.PHONY: tokens diagrams
tokens: ## Regenerate design/tokens.css from design/tokens.json
	@uv run --quiet python scripts/tokens.py

diagrams: ## Redraw every figure and colour every code block in the workbook and the guide
	@node scripts/diagram.mjs
	@node scripts/highlight.mjs

book: diagrams ## Render the workbook and the guide to PDF, then read them back
	@cd e2e && npm ci --silent && npx playwright install chromium --only-shell >/dev/null 2>&1 || true
	@uv run --quiet python scripts/contents.py
	@node scripts/build_book.mjs

e2e: up ## Full stack, real model, real browser; writes artifacts/playwright.json
	@mkdir -p artifacts evidence/screens && rm -f artifacts/playwright.json artifacts/run-state.json
	cd e2e && npm ci --silent && npx playwright install chromium
	trap 'uv run --quiet python $(CURDIR)/scripts/chaos.py reset' EXIT; \
		uv run --quiet python scripts/tree_hash.py > artifacts/e2e-tree.txt && \
		cd e2e && npx playwright test

score: ## Score the build 0 to 100 from the latest check and e2e results
	@uv run --quiet python scripts/score.py

chaos: ## Inject a failure: make chaos SCENARIO=bad-release|docs-hang
	uv run --quiet python scripts/chaos.py $(SCENARIO)

chaos-reset: ## Undo every injected failure
	uv run --quiet python scripts/chaos.py reset
