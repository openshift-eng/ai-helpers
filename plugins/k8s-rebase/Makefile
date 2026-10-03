.DEFAULT_GOAL := help
.PHONY: help matrix test watch results court set-known-good set-from-commit stop clean assert-evidence-paths eval

SCRIPT := test/test-skill.sh
SPEC ?= $(if $(spec),$(spec),none)
REPO ?= $(repo)
REF ?= $(ref)
URL ?= $(url)
COMMIT ?= $(commit)
JOBS ?= $(jobs)
VER ?= $(version)
REPOS ?= $(repos_dir)
CONFIG ?= test/config$(if $(VER),-$(shell echo $(VER) | grep -oE '[0-9]+\.[0-9]+'),).yaml

help: ## Show available targets
	@echo ""
	@echo "  k8s-rebase skill testing"
	@echo "  ────────────────────────"
	@echo "  Tests the k8s-rebase skill by running it against real repos, then"
	@echo "  comparing the output to a known-good human-verified rebase."
	@echo "  Gates = $(words $(wildcard gates/step[1-4]-*/*.md)) verification checks (build, vet, lint, correctness, ...)."
	@echo "  Court = AI adversarial review that compares output to known-good, votes pass/fail."
	@echo "  Requires: claude CLI, yq, jq, git, rsync. ~20 min per repo."
	@echo ""
	@echo "  Quick start:"
	@echo "    make test repo=ovn-kubernetes/ovn-kubernetes-mcp"
	@echo "    make watch                      # monitor progress"
	@echo "    make court repo=ovn-kubernetes/ovn-kubernetes-mcp"
	@echo "    make results repo=ovn-kubernetes/ovn-kubernetes-mcp"
	@echo ""
	@echo "  Full pipeline (all versions, all repos, court, retries):"
	@echo "    make matrix                     # 4-8 hours unattended"
	@echo ""
	@echo "  Workflow: test → watch → court → results"
	@echo ""
	@echo "  Test (auto-clones repos on first run)"
	@echo "    make test                       Launch all repos in background, then block until all finish"
	@echo "    make test repo=<repo>           Launch in background, returns immediately (use make watch)"
	@echo "    make test repo=\"<r1> <r2>\"       Run multiple repos (same version, same spec)"
	@echo "    make test spec=all              Blind test — no patterns doc or autofix"
	@echo "    make test version=1.35          Backtest against an older k8s version"
	@echo "    spec: none (default), all (blind), fn:<tag>, pattern:<key>"
	@echo "    versions: $(shell ls test/config-*.yaml 2>/dev/null | sed 's|test/config-||;s|\.yaml||' | tr '\n' ' ')"
	@echo "    repos:"; yq '.repos | keys | .[]' test/config.yaml 2>/dev/null | while read -r r; do echo "      $$r"; done
	@echo ""
	@echo "  Monitor (check progress while tests run)"
	@echo "    make watch                      Show session state, gate count, diff vs known-good"
	@echo "    watch -n 10 make watch          Auto-refresh every 10s"
	@echo ""
	@echo "  Review (run after gates pass — compares output to known-good rebase)"
	@echo "    make court                      Run court for all pending repos (all versions)"
	@echo "    make court repo=<repo>          AI review one repo (add version=X.Y for specific version)"
	@echo ""
	@echo "  Results"
	@echo "    make results                    Show all versions (or one with version=X)"
	@echo "    make results repo=<repo>        Show gate reports, diff vs known-good, history"
	@echo ""
	@echo "  Manage"
	@echo "    make stop                       Stop all running test sessions"
	@echo "    make clean                      Reset worktrees, state, temp branches (keeps clones)"
	@echo "    make clean repo=<repo>          Clean one repo (all versions)"
	@echo "    make clean repo=<repo> version=1.34.1  Clean one repo, one version only"
	@echo ""
	@echo "  Config"
	@echo "    make set-known-good repo=<repo> ref=<sha>            Set known-good to a SHA on main"
	@echo "    make set-known-good repo=<repo> ref=<branch> url=<u> Set known-good to a branch on a fork"
	@echo "    make set-from-commit repo=<repo> commit=<sha>        Set pre-rebase starting commit"
	@echo "    repos_dir=/path make test       Override repo checkout location (default: test/.repos/)"
	@echo ""
	@echo "  Agent eval (agent-eval-harness — cost/token/model measurement)"
	@echo "    make eval case=001              Run one pattern-retention eval case (see evals/README.md)"
	@echo ""

matrix: ## Full pipeline: all versions x all repos, court, retries (4-8 hours)
	@$(if $(JOBS),MAX_CONCURRENT=$(JOBS)) $(if $(REPOS),REPOS_DIR=$(REPOS)) bash $(SCRIPT) matrix $(if $(spec),$(SPEC),all)

test: ## Run tests
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
		$(if $(REPOS),REPOS_DIR=$(REPOS)) CONFIG_FILE=$(CONFIG) bash $(SCRIPT) results $(REPO) --court; \
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

eval: ## Run the agent-eval-harness pattern-retention eval for one case (case=NNN required). Manually-triggered only, same as `make court`.
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
	bash $(CURDIR)/evals/scripts/run-rebase.sh "$$REPO_URL" "$$FROM_COMMIT" "$$VERSION" "claude-sonnet-4-6" "$$KNOWN_GOOD_URL" "$$KNOWN_GOOD_REF"

clean: ## Reset worktrees, state, temp branches (keeps clones). Use repo= and version= to limit scope.
	@$(if $(REPOS),REPOS_DIR=$(REPOS)) bash $(SCRIPT) clean $(if $(VER),--version $(VER)) $(if $(REPO),$(REPO))
