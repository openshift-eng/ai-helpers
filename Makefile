.PHONY: install install-metrics help

help: ## Show this help message
	@echo "AI Helpers - Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: install-metrics ## Install all AI helper components

install-metrics: ## Install metrics tracking script to ~/.ai-helpers
	@echo "Installing metrics tracking script..."
	@mkdir -p ~/.ai-helpers/bin
	@cp scripts/track-metrics.sh ~/.ai-helpers/bin/track-metrics
	@chmod +x ~/.ai-helpers/bin/track-metrics
	@echo "✓ Installed to ~/.ai-helpers/bin/track-metrics"
	@echo ""
	@echo "When Claude asks to run the metrics script, you can approve"
	@echo "and choose to allowlist it permanently for auto-approval."

