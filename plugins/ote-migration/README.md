# OTE Migration Plugin

  Automated migration tools for integrating OpenShift component repositories with the openshift-tests-extension (OTE) framework.

  ## Overview

  This plugin automates the complete process of migrating OpenShift component repositories to use the OTE framework. The tool handles everything from repository setup to code generation with customizable destination paths.

  ## Commands

  ### `/ote-migration:migrate`

  Performs the complete OTE migration in one workflow.

  **What it does:**
  1. Collects user inputs - Extension name, directories, repository URLs
  2. Sets up repositories - Clones/updates source and target repositories
  3. Creates structure - Builds test/e2e and test/testdata directories
  4. Copies files - Moves test files and testdata to destinations
  5. Vendors dependencies - Automatically vendors Go dependencies
  6. Generates code - Creates go.mod, cmd/main.go, Makefile, fixtures.go
  7. Migrates tests - Automatically replaces FixturePath() calls and updates imports
  8. Provides validation - Gives comprehensive next steps and validation guide

  **Key Features:**
  - Complete automation - One command handles the entire migration
  - Smart repository management with remote detection
  - Automatic dependency vendoring (compat_otp, exutil, etc.)
  - Two directory strategies - multi-module or single-module
  - Git status validation for working directory
  - Auto-install go-bindata for generating embedded testdata
  - Automatic FixturePath() migration and import updates
  - Build verification before completion

  ## Installation

  This plugin is available through the ai-helpers marketplace:

  ```bash
  /plugin marketplace add openshift-eng/ai-helpers
  /plugin install ote-migration@ai-helpers

  Usage

  /ote-migration:migrate

  Follow the prompts to provide:
  - Extension name (e.g., "sdn", "router", "storage")
  - Directory structure strategy (monorepo or single-module)
  - Working directory
  - Local openshift-tests-private path (optional)
  - Test subfolder under test/extended/
  - Testdata subfolder under test/extended/testdata/
  - Local target repository path (optional)
  - Target repository URL (if not using local)

  Directory Structure Strategies

  Option 1: Monorepo Strategy (Recommended)

  Best for component repos with existing cmd/ and test/ directories.

  Option 2: Single-Module Strategy

  Best for standalone test extensions or prototyping.

  Resources

  - https://github.com/openshift/enhancements/pull/1676
  - https://github.com/openshift-eng/openshift-tests-extension
  - https://github.com/openshift-eng/openshift-tests-extension/blob/main/cmd/example-tests/main.go
