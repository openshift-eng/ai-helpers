# Makefile for ai-helpers

# Container runtime (podman or docker)
CONTAINER_RUNTIME ?= $(shell command -v podman 2>/dev/null || echo docker)

# claudelint image
CLAUDELINT_IMAGE = ghcr.io/stbenjam/claudelint:main

.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: lint
lint: ## Run plugin linter (verbose, strict mode)
	@echo "Running claudelint with $(CONTAINER_RUNTIME)..."
	$(CONTAINER_RUNTIME) run --rm -v $(PWD):/workspace:Z ghcr.io/stbenjam/claudelint:main -v --strict

.PHONY: lint-pull
lint-pull: ## Pull the latest claudelint image
	@echo "Pulling latest claudelint image..."
	$(CONTAINER_RUNTIME) pull $(CLAUDELINT_IMAGE)

.DEFAULT_GOAL := help

