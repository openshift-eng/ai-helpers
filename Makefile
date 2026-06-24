# Makefile for ai-helpers

# Container runtime (podman or docker)
CONTAINER_RUNTIME ?= $(shell command -v podman 2>/dev/null || echo docker)

# skillsaw image
SKILLSAW_IMAGE = ghcr.io/stbenjam/skillsaw:0.14.0

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

.PHONY: lint-fix
lint-fix: ## Auto-fix lint violations
	$(CONTAINER_RUNTIME) run --rm --platform linux/amd64 $(SELINUX_OPT) -v $(PWD):/workspace:Z $(SKILLSAW_IMAGE) fix -y .

.PHONY: lint-pull
lint-pull: ## Pull the latest skillsaw image
	$(CONTAINER_RUNTIME) pull $(SKILLSAW_IMAGE)

.PHONY: update
update: ## Update plugin documentation and website data
	@echo "Fixing frontmatter quotes, if any..."
	@python3 scripts/fix_frontmatter_quotes.py
	@echo "Syncing marketplace versions..."
	@python3 scripts/sync_marketplace_versions.py
	@echo "Generating docs..."
	$(CONTAINER_RUNTIME) run --rm --platform linux/amd64 $(SELINUX_OPT) -v $(PWD):/workspace:Z --entrypoint skillsaw $(SKILLSAW_IMAGE) docs -o docs/ --theme crimson-red

EVAL_REPEAT ?= 1
EVAL_PASS_RATE_THRESHOLD ?= 100
EVAL_CONFIGS := $(shell find plugins/$(or $(EVAL_PLUGIN),*) -path '*/evals/*.yaml' 2>/dev/null | sort)
EVAL_TARGETS := $(foreach c,$(EVAL_CONFIGS),_run-eval__$(subst /,__,$(c)))

.PHONY: eval-plugins
eval-plugins: ## Run plugin behavioral evals (EVAL_PLUGIN, EVAL_FILTER, EVAL_OUTPUT, EVAL_REPEAT)
	@npm install
	@$(MAKE) -j$(words $(EVAL_CONFIGS)) --no-print-directory $(EVAL_TARGETS)

.PHONY: $(EVAL_TARGETS)
$(EVAL_TARGETS):
	$(eval CONFIG := $(subst __,/,$(patsubst _run-eval__%,%,$@)))
	$(eval EVAL_NAME := $(basename $(notdir $(CONFIG))))
	@echo "=== Running eval: $(CONFIG) ==="
	@CLAUDE_CODE_USE_VERTEX=true \
	$(if $(PROMPTFOO_CONFIG_DIR),PROMPTFOO_CONFIG_DIR=$(PROMPTFOO_CONFIG_DIR)) \
	PROMPTFOO_PASS_RATE_THRESHOLD=$(EVAL_PASS_RATE_THRESHOLD) \
		npx promptfoo eval \
		-c "$(CONFIG)" \
		$(if $(EVAL_FILTER),--filter-pattern "$(EVAL_FILTER)") \
		$(if $(EVAL_TIER),--filter-metadata "tier=$(EVAL_TIER)") \
		$(if $(EVAL_OUTPUT_DIR),--output "$(EVAL_OUTPUT_DIR)/$(EVAL_NAME).xml" --output "$(EVAL_OUTPUT_DIR)/$(EVAL_NAME).html") \
		--repeat $(EVAL_REPEAT) \
		--no-cache \
		--table-cell-max-length 500

.PHONY: eval-contributing
eval-contributing: ## Run contributing workflow evals (root evals/promptfooconfig.yaml)
	@npm install
	@CLAUDE_CODE_USE_VERTEX=true \
	$(if $(PROMPTFOO_CONFIG_DIR),PROMPTFOO_CONFIG_DIR=$(PROMPTFOO_CONFIG_DIR)) \
	PROMPTFOO_PASS_RATE_THRESHOLD=$(EVAL_PASS_RATE_THRESHOLD) \
		npx promptfoo eval \
		-c evals/promptfooconfig.yaml \
		$(if $(EVAL_FILTER),--filter-pattern "$(EVAL_FILTER)") \
		$(if $(EVAL_OUTPUT_DIR),--output "$(EVAL_OUTPUT_DIR)/contributing.xml" --output "$(EVAL_OUTPUT_DIR)/contributing.html") \
		--repeat $(EVAL_REPEAT) \
		--no-cache \
		--table-cell-max-length 500

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
