.DEFAULT_GOAL := help
.PHONY: help matrix test watch results court set-known-good set-from-commit stop clean assert-evidence-paths eval test-court

SCRIPT := test/test-skill.sh
SPEC ?= $(if $(spec),$(spec),none)
REPO ?= $(repo)
REF ?= $(ref)
URL ?= $(url)
COMMIT ?= $(commit)
FROM_COMMIT ?= $(from_commit)
JOBS ?= $(jobs)
VER ?= $(version)
REPOS ?= $(repos_dir)
CONFIG ?= test/config$(if $(VER),-$(shell echo $(VER) | grep -oE '[0-9]+\.[0-9]+'),).yaml

help: ## Show available targets
	@echo "k8s-rebase workflow testing ($(words $(wildcard gates/step[1-4]-*/*.md)) gates)"
	@echo ""
	@echo "Offline checks (no model calls):"
	@echo "  make test-compatibility test-version-selection test-version-references test-kind-images test-go-version-gate test-rebase-base test-cve-evidence test-validation test-court assert-evidence-paths"
	@echo ""
	@echo "One rebase, then review its result:"
	@echo "  make test repo=ovn-kubernetes/ovn-kubernetes-mcp version=1.35 spec=none"
	@echo "  make watch version=1.35"
	@echo "  make court repo=ovn-kubernetes/ovn-kubernetes-mcp version=1.35"
	@echo "  make court repo=openshift/cluster-network-operator version=1.36 from_commit=<sha>"
	@echo "  make court repo=<repo> version=1.36 from_commit=<sha> diff_only=1  Eval diff review without matrix-row association"
	@echo "  make results repo=ovn-kubernetes/ovn-kubernetes-mcp version=1.35"
	@echo ""
	@echo "Configured matrix (all versions, court, bounded retries):"
	@echo "  make matrix spec=none            Full skill"
	@echo "  make matrix spec=all             Withhold patterns and autofix (matrix default)"
	@echo "  make test defaults to spec=none; no repo= launches all repos for that version."
	@echo "  Other specs: all-patterns, all-fns, fn:<tag>, pattern:<key>"
	@echo ""
	@echo "Artifacts (without YAML scoring): make eval case=012"
	@echo "Management: make stop; make clean repo=<repo> version=1.35.3"
	@echo "  clean discards selected eval work; omit filters only to reset all configured repos."
	@echo "Config: make set-known-good repo=<repo> ref=<ref> [url=<fork>] version=1.35"
	@echo "        make set-from-commit repo=<repo> commit=<sha> version=1.35"
	@echo "  repos_dir=<path> overrides the disposable clone directory for the workflow harness."
	@echo ""
	@echo "Full runs call models and build projects; time and cost vary by repo."
	@echo "See evals/README.md for prerequisites, coverage, artifacts, and scoring limits."

matrix: ## Run configured cases, court, and bounded retries; defaults to spec=all
	@$(if $(JOBS),MAX_CONCURRENT=$(JOBS)) $(if $(REPOS),REPOS_DIR=$(REPOS)) bash $(SCRIPT) matrix $(if $(spec),$(SPEC),all)

test: ## Run skill workflows; defaults to spec=none
	@if [ -n "$(REPO)" ]; then \
		$(if $(JOBS),MAX_CONCURRENT=$(JOBS)) $(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) test $(SPEC) $(REPO) $(if $(COMMIT),--from-commit $(COMMIT)); \
	else \
		$(if $(JOBS),MAX_CONCURRENT=$(JOBS)) $(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) test-all $(SPEC); \
	fi

watch: ## Show active test status
	@$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) watch

results: ## Show results
	@if [ -z "$(VER)" ] && [ -z "$(REPO)" ]; then \
		$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) results --all-versions; \
	else \
		$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) results $(REPO); \
	fi

court: ## Adversarial court review
	@if [ -n "$(REPO)" ]; then \
		$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) results $(REPO) --court $(if $(FROM_COMMIT),--from-commit $(FROM_COMMIT)) $(if $(filter 1 true yes,$(diff_only)),--diff-only); \
	elif [ -n "$(FROM_COMMIT)" ]; then \
		echo "ERROR: from_commit requires repo=<repo> for a single court review"; exit 1; \
	elif [ -z "$(VER)" ]; then \
		$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) court-all --all-versions; \
	else \
		$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) court-all; \
	fi

set-known-good: ## Set known-good reference
	@test -n "$(REPO)" || (echo "ERROR: repo required" && exit 1)
	@test -n "$(REF)" || (echo "ERROR: ref required" && exit 1)
	@$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) set-known-good $(REPO) $(REF) $(if $(URL),--url $(URL))

set-from-commit: ## Set pre-rebase starting commit
	@test -n "$(REPO)" || (echo "ERROR: repo required" && exit 1)
	@test -n "$(COMMIT)" || (echo "ERROR: commit required" && exit 1)
	@$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) set-from-commit $(REPO) $(COMMIT)

stop: ## Stop all sessions
	@$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) stop --all || true

assert-evidence-paths: ## Verify all companion .sh files have matching EVIDENCE templates
	@bash test/assert-evidence-paths.sh

.PHONY: test-compatibility
test-compatibility: ## Offline Claude/Codex review, hook, and gate interface checks
	@python3 test/test_compatibility.py

.PHONY: test-version-selection
test-version-selection: ## Offline Step 1 metadata and command-derivation checks
	@python3 test/test_version_selection.py

.PHONY: test-version-references
test-version-references: ## Offline verified OpenShift builder and generic Go image checks
	@python3 test/test_version_references.py

.PHONY: test-kind-images
test-kind-images: ## Offline published KIND image and patch reconciliation checks
	@python3 test/test_kind_images.py

.PHONY: test-go-version-gate
test-go-version-gate: ## Offline Go-reference attribution against real Git baselines
	@python3 test/test_go_version_gate.py

.PHONY: test-validation
test-validation: ## Offline test execution and module/package coverage checks
	@python3 test/test_validation.py

.PHONY: test-rebase-base test-cve-evidence
test-rebase-base: ## Offline recorded baseline and release-branch scope checks
	@python3 test/test_rebase_base.py

test-cve-evidence: ## Offline complete dependency inventory and OSV coverage checks
	@python3 test/test_cve_evidence.py

test-court: ## Offline court scope/cache checks with a fake reviewer
	@python3 test/test_court.py

eval: ## Collect one case's rebase artifacts (case=NNN required); does not run YAML judges
	@test -n "$(case)" || (echo "ERROR: case required, e.g. make eval case=001" && exit 1)
	@INPUT="evals/cases/pattern-retention/case-$(case)/input.yaml"; \
	test -f "$$INPUT" || (echo "ERROR: $$INPUT not found" && exit 1); \
	REPO_URL=$$(grep '^repo_url:' "$$INPUT" | cut -d' ' -f2); \
	FROM_COMMIT=$$(grep '^from_commit:' "$$INPUT" | cut -d' ' -f2); \
	VERSION=$$(grep '^version:' "$$INPUT" | cut -d' ' -f2 | tr -d '"'); \
	KNOWN_GOOD_URL=$$(grep '^known_good_url:' "$$INPUT" | cut -d' ' -f2); \
	KNOWN_GOOD_REF=$$(grep '^known_good_ref:' "$$INPUT" | cut -d' ' -f2); \
	mkdir -p /tmp/k8s-rebase-eval-case-$(case)/output; \
	cd /tmp/k8s-rebase-eval-case-$(case) && \
	AI_HELPERS_DIR=$$(cd $(CURDIR)/../.. && pwd) \
	bash $(CURDIR)/evals/scripts/run-rebase.sh "$$REPO_URL" "$$FROM_COMMIT" "$$VERSION" "claude-sonnet-5-5" "$$KNOWN_GOOD_URL" "$$KNOWN_GOOD_REF"

clean: ## Reset worktrees, state, temp branches (keeps clones). Use repo= and version= to limit scope.
	@$(if $(REPOS),REPOS_DIR=$(REPOS)) bash $(SCRIPT) clean $(if $(VER),--version $(VER)) $(if $(REPO),$(REPO))
