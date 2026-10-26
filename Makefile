.PHONY: help dev install install-python install-angular test test-python test-unit test-integration \
        test-angular lint lint-python format typecheck build clean

# Show this list when `make` is run with no target.
.DEFAULT_GOAL := help

help: ## Show this help message.
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## /{ printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

dev: ## Launch the FastAPI backend (uv) and Angular frontend (pnpm) together.
	./dev.sh

install: install-python install-angular ## Install Python (uv) and Angular (pnpm) dependencies.

install-python: ## Install Python dependencies (dev and api groups) with uv.
	uv sync --group dev --group api

install-angular: ## Install Angular dependencies with pnpm.
	cd webapp && pnpm install

test: test-python test-angular ## Run the full test suite (Python + Angular).

test-python: ## Run the full Python test suite (unit + integration).
	uv run pytest tests/ -v

test-unit: ## Run only the fast Python unit tests.
	uv run pytest tests/ -v -m "unit"

test-integration: ## Run the Python integration tests (downloads small datasets).
	uv run pytest tests/ -v -m "integration"

test-angular: ## Run the Angular test suite once (headless).
	cd webapp && pnpm test --watch=false --browsers=ChromeHeadless

lint: lint-python ## Run all lint/format checks (mirrors CI's pre-commit step).

lint-python: ## Run pre-commit checks on the Python code.
	uv run pre-commit run --all-files

# Ruff is only installed through pre-commit (pinned in .pre-commit-config.yaml). The hooks exit non-zero when
# they modify files, so the first pass ignores the exit code and the second pass confirms a clean result.
format: ## Auto-fix formatting/lint issues where possible.
	-uv run pre-commit run ruff --all-files
	-uv run pre-commit run ruff-format --all-files
	uv run pre-commit run ruff --all-files
	uv run pre-commit run ruff-format --all-files

typecheck: ## Run mypy type checking on the Python code.
	uv run mypy

build: ## Build the Angular app for production.
	cd webapp && pnpm build

clean: ## Remove build artifacts and caches.
	rm -rf webapp/dist webapp/.angular
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -not -path "./.venv/*" -not -path "./webapp/node_modules/*" -exec rm -rf {} +
