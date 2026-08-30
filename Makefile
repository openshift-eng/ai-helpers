# Makefile for ai-helpers

# Container runtime (podman or docker)
CONTAINER_RUNTIME ?= $(shell command -v podman 2>/dev/null || echo docker)

# skillsaw image (version shared with the Python development dependency)
SKILLSAW_VERSION := $(shell awk -F '==' '/^skillsaw==[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$$/ { version = $$2; count++ } END { if (count == 1) print version }' requirements-dev.txt)
ifeq ($(strip $(SKILLSAW_VERSION)),)
$(error requirements-dev.txt must contain exactly one skillsaw==X.Y.Z requirement)
endif
SKILLSAW_IMAGE ?= ghcr.io/stbenjam/skillsaw:$(SKILLSAW_VERSION)

# Detect if SELinux is enforcing and add security option
SELINUX_OPT := $(shell if command -v getenforce >/dev/null 2>&1 && [ "$$(getenforce 2>/dev/null)" = "Enforcing" ]; then echo "--security-opt label=disable"; fi)

.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

PLUGIN_TESTS := $(shell find plugins -name 'test_*.py' -o -name '*_test.py' 2>/dev/null | sort)

.PHONY: test
test: ## Run all tests
	pytest tests/ -v
	@failures=0; \
	for t in $(PLUGIN_TESTS); do \
		echo "=== $$t ==="; \
		python3 "$$t" || failures=$$((failures + 1)); \
		echo; \
	done; \
	if [ $$failures -gt 0 ]; then \
		echo "$$failures test file(s) failed"; \
		exit 1; \
	fi

.PHONY: lint
lint: ## Run plugin linter (verbose, strict mode)
	$(CONTAINER_RUNTIME) run --rm --platform linux/amd64 $(SELINUX_OPT) -v $(PWD):/workspace:Z $(SKILLSAW_IMAGE) .

.PHONY: lint-pull
lint-pull: ## Pull the configured skillsaw image
	$(CONTAINER_RUNTIME) pull $(SKILLSAW_IMAGE)

.PHONY: update
update: ## Update marketplace versions and generate site content
	@echo "Fixing frontmatter quotes, if any..."
	@python3 scripts/fix_frontmatter_quotes.py
	@echo "Syncing marketplace versions..."
	@python3 scripts/sync_marketplace_versions.py
	@echo "Generating site content..."
	@python3 scripts/generate_site.py

.PHONY: site-build
site-build: update ## Build the documentation site with strict checks
	@cd site && python3 -m mkdocs build --strict --site-dir ../public

.PHONY: site-serve
site-serve: update ## Preview the site at http://127.0.0.1:8000/ai-helpers/
	@cd site && python3 -m mkdocs serve --strict --dev-addr 127.0.0.1:8000

.PHONY: list-unprotected
list-unprotected: ## List directories where anyone can contribute (no OWNERS file)
	@echo "Directories auto-approved via auto_approve_unowned_subfolders:"
	@echo ""
	@find . -mindepth 1 -maxdepth 1 -type d \
		-not -name '.*' \
		-not -name 'node_modules' | sort | while read dir; do \
		if [ ! -f "$$dir/OWNERS" ]; then \
			echo "  $$dir/ (unprotected — inherits root OWNERS auto-approve)"; \
		fi; \
	done
	@echo ""
	@echo "Plugin directories without OWNERS (auto-approved):"
	@echo ""
	@find plugins -mindepth 1 -maxdepth 1 -type d | sort | while read dir; do \
		if [ ! -f "$$dir/OWNERS" ]; then \
			echo "  $$dir/"; \
		fi; \
	done

.DEFAULT_GOAL := help
