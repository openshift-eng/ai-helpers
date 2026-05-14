# Makefile for ai-helpers

# Container runtime (podman or docker)
CONTAINER_RUNTIME ?= $(shell command -v podman 2>/dev/null || echo docker)

# skillsaw image
SKILLSAW_IMAGE = ghcr.io/stbenjam/skillsaw:0.8.0

# Detect if SELinux is enforcing and add security option
SELINUX_OPT := $(shell if command -v getenforce >/dev/null 2>&1 && [ "$$(getenforce 2>/dev/null)" = "Enforcing" ]; then echo "--security-opt label=disable"; fi)

.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: lint
lint: ## Run plugin linter (verbose, strict mode)
	$(CONTAINER_RUNTIME) run --rm --platform linux/amd64 $(SELINUX_OPT) -v $(PWD):/workspace:Z $(SKILLSAW_IMAGE) -v --strict .

.PHONY: lint-pull
lint-pull: ## Pull the latest skillsaw image
	$(CONTAINER_RUNTIME) pull $(SKILLSAW_IMAGE)

.PHONY: update
update: ## Update plugin documentation and website data
	@echo "Fixing frontmatter quotes, if any..."
	@python3 scripts/fix_frontmatter_quotes.py
	@echo "Syncing marketplace versions..."
	@python3 scripts/sync_marketplace_versions.py
	@echo "Updating plugin documentation..."
	@python3 scripts/generate_plugin_docs.py
	@echo "Building website data..."
	@python3 scripts/build-website.py

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
	PROMPTFOO_PASS_RATE_THRESHOLD=$(EVAL_PASS_RATE_THRESHOLD) \
		npx promptfoo eval \
		-c "$(CONFIG)" \
		$(if $(EVAL_FILTER),--filter-pattern "$(EVAL_FILTER)") \
		$(if $(EVAL_TIER),--filter-metadata "tier=$(EVAL_TIER)") \
		$(if $(EVAL_OUTPUT_DIR),--output "$(EVAL_OUTPUT_DIR)/$(EVAL_NAME).xml") \
		--repeat $(EVAL_REPEAT) \
		--no-cache \
		--table-cell-max-length 500

.DEFAULT_GOAL := help
