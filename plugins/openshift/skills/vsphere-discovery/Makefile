.PHONY: build clean install test help

# Binary name
BINARY_NAME=vsphere-helper

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOCLEAN=$(GOCMD) clean
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod

# Detect OS and architecture
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# Default target architecture based on current system
ifeq ($(UNAME_S),Darwin)
	OS=darwin
else ifeq ($(UNAME_S),Linux)
	OS=linux
else
	OS=unsupported
endif

ifeq ($(UNAME_M),x86_64)
	ARCH=amd64
else ifeq ($(UNAME_M),arm64)
	ARCH=arm64
else ifeq ($(UNAME_M),aarch64)
	ARCH=arm64
else
	ARCH=unsupported
endif

# Build flags
LDFLAGS=-ldflags "-s -w"

# Default target
all: build

# Download dependencies
deps:
	@echo "Downloading dependencies..."
	$(GOMOD) download
	$(GOMOD) tidy

# Build for current platform
build: deps
	@echo "Building $(BINARY_NAME) for $(OS)/$(ARCH)..."
	CGO_ENABLED=0 GOOS=$(OS) GOARCH=$(ARCH) $(GOBUILD) $(LDFLAGS) -o $(BINARY_NAME) .
	@echo "✓ Build complete: $(BINARY_NAME)"

# Build for Linux (amd64)
build-linux:
	@echo "Building $(BINARY_NAME) for linux/amd64..."
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(BINARY_NAME)-linux-amd64 .
	@echo "✓ Build complete: $(BINARY_NAME)-linux-amd64"

# Build for Linux (arm64)
build-linux-arm64:
	@echo "Building $(BINARY_NAME) for linux/arm64..."
	CGO_ENABLED=0 GOOS=linux GOARCH=arm64 $(GOBUILD) $(LDFLAGS) -o $(BINARY_NAME)-linux-arm64 .
	@echo "✓ Build complete: $(BINARY_NAME)-linux-arm64"

# Build for macOS (amd64)
build-darwin:
	@echo "Building $(BINARY_NAME) for darwin/amd64..."
	CGO_ENABLED=0 GOOS=darwin GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(BINARY_NAME)-darwin-amd64 .
	@echo "✓ Build complete: $(BINARY_NAME)-darwin-amd64"

# Build for macOS (arm64/M1/M2)
build-darwin-arm64:
	@echo "Building $(BINARY_NAME) for darwin/arm64..."
	CGO_ENABLED=0 GOOS=darwin GOARCH=arm64 $(GOBUILD) $(LDFLAGS) -o $(BINARY_NAME)-darwin-arm64 .
	@echo "✓ Build complete: $(BINARY_NAME)-darwin-arm64"

# Build all platforms
build-all: build-linux build-linux-arm64 build-darwin build-darwin-arm64
	@echo "✓ All builds complete"
	@ls -lh $(BINARY_NAME)-*

# Install to user's local bin
install: build
	@echo "Installing $(BINARY_NAME)..."
	@if [ -d "$$HOME/.local/bin" ]; then \
		cp $(BINARY_NAME) $$HOME/.local/bin/$(BINARY_NAME); \
		echo "✓ Installed to $$HOME/.local/bin/$(BINARY_NAME)"; \
	elif [ -d "$$HOME/bin" ]; then \
		cp $(BINARY_NAME) $$HOME/bin/$(BINARY_NAME); \
		echo "✓ Installed to $$HOME/bin/$(BINARY_NAME)"; \
	else \
		echo "Error: Neither ~/.local/bin nor ~/bin exists"; \
		echo "Create one with: mkdir -p ~/.local/bin"; \
		exit 1; \
	fi

# Run tests
test:
	$(GOTEST) -v ./...

# Clean build artifacts
clean:
	@echo "Cleaning..."
	$(GOCLEAN)
	rm -f $(BINARY_NAME)
	rm -f $(BINARY_NAME)-linux-amd64
	rm -f $(BINARY_NAME)-linux-arm64
	rm -f $(BINARY_NAME)-darwin-amd64
	rm -f $(BINARY_NAME)-darwin-arm64
	@echo "✓ Clean complete"

# Show help
help:
	@echo "vsphere-helper Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  make              - Build for current platform"
	@echo "  make build        - Build for current platform"
	@echo "  make build-all    - Build for all platforms"
	@echo "  make install      - Build and install to ~/.local/bin or ~/bin"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make test         - Run tests"
	@echo "  make deps         - Download dependencies"
	@echo ""
	@echo "Platform-specific builds:"
	@echo "  make build-linux          - Build for Linux amd64"
	@echo "  make build-linux-arm64    - Build for Linux arm64"
	@echo "  make build-darwin         - Build for macOS amd64"
	@echo "  make build-darwin-arm64   - Build for macOS arm64 (M1/M2)"
	@echo ""
	@echo "Current platform: $(OS)/$(ARCH)"
