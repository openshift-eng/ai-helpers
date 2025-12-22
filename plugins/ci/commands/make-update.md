---
description: Run make update in OpenShift repos with proper Podman setup (macOS only)
argument-hint: [repo-path]
---

## Name
ci:make-update

## Synopsis
```
/ci:make-update [repo-path]
```

## Description

**Platform: macOS only**

The `ci:make-update` command runs `make update` in OpenShift repositories while handling common setup issues on macOS with Podman. It automates the configuration of Podman machine, dependency installation, and environment setup required for running generation scripts.

This command solves the common "Cannot connect to Podman" and platform mismatch errors encountered when running `make update` on macOS by:
- Starting Podman machine with increased memory (4GB) if not running
- Configuring native ARM64 image usage instead of forced AMD64 emulation
- Installing required dependencies (gnu-sed, pyyaml)
- Setting up proper Python virtual environment

The command accepts an optional repository path argument. If not provided, it uses the current working directory.

**Note**: This command is designed specifically for macOS. Linux users should run `make update` directly as Podman runs natively without requiring a VM.

## Implementation

The command performs the following steps:

1. **Validate Platform**:
   - Check that the platform is macOS: `uname -s` should return "Darwin"
   - If not macOS, display error message:
     ```
     This command is only supported on macOS.
     On Linux, run 'make update' directly.
     ```
   - Exit if not on macOS

2. **Validate Repository**:
   - If repo path is provided ($1), verify it exists and contains a Makefile
   - If not provided, use current working directory
   - Verify the directory is an OpenShift repository (has Makefile with update target)

3. **Check Podman Installation**:
   - Run `which podman` to verify Podman is installed
   - If not installed, provide installation instructions:
     ```
     brew install podman
     ```
   - Exit with error if Podman is not available

4. **Initialize Podman Machine** (if needed):
   - Check if a Podman machine exists: `podman machine list`
   - If no machine exists, create one with 4GB memory:
     ```bash
     podman machine init --memory 4096 --disk-size 50
     ```
   - Display output to user

5. **Start Podman Machine**:
   - Check machine status: `podman machine list`
   - If machine is not running, start it:
     ```bash
     podman machine start
     ```
   - Wait for machine to be ready (check `podman machine list` until status is "running")
   - Display startup progress to user

6. **Verify Podman Connection**:
   - Test connection: `podman ps`
   - If connection fails, suggest troubleshooting:
     ```
     podman system connection list
     podman machine stop
     podman machine start
     ```

7. **Install gnu-sed**:
   - Check if gnu-sed is installed: `which gsed`
   - If not installed, install via Homebrew:
     ```bash
     brew install gnu-sed
     ```
   - Verify installation: `gsed --version`

8. **Set Up Python Virtual Environment**:
   - Check if `.venv` directory exists in repository
   - If not, create virtual environment:
     ```bash
     cd <repo-path>
     python3 -m venv .venv
     ```
   - Activate virtual environment:
     ```bash
     source .venv/bin/activate
     ```
   - Install pyyaml:
     ```bash
     pip install pyyaml
     ```
   - Display confirmation of venv setup

9. **Set Environment Variables**:
   - Export `CONTAINER_ENGINE_OPTS=""` to use native ARM64 images:
     ```bash
     export CONTAINER_ENGINE_OPTS=""
     ```
   - Explain to user that this prevents platform mismatch errors by using native architecture instead of emulation

10. **Run make update**:
    - Execute in the repository directory:
      ```bash
      cd <repo-path>
      CONTAINER_ENGINE_OPTS="" make update
      ```
    - Stream output to user in real-time
    - Capture exit code

11. **Handle Results**:
    - If successful (exit code 0):
      - Display success message
      - Show git diff summary of changed files: `git status --short`
      - Offer to review changes or create a commit
    - If failed (non-zero exit code):
      - Display error message and output
      - Analyze common error patterns:
        - Podman connection issues → suggest restarting Podman machine
        - Platform mismatch → verify CONTAINER_ENGINE_OPTS is set
        - Missing dependencies → check for specific errors and suggest fixes
      - Offer troubleshooting steps

12. **Cleanup**:
    - Deactivate Python virtual environment if it was created by this command
    - Preserve .venv directory for future runs

## Return Value

- **Success**: Exit code 0, displays changed files from `git status`
- **Error**: Non-zero exit code with error details and troubleshooting suggestions

**Possible errors:**
- Unsupported platform (not macOS)
- Podman not installed
- Podman machine failed to start
- Podman connection refused
- Missing Makefile or update target
- Python dependencies installation failed
- make update execution failed

## Examples

1. **Run make update in current directory**:
   ```
   /ci:make-update
   ```

2. **Run make update in specific repository**:
   ```
   /ci:make-update ~/code/openshift/ci-tools
   ```

3. **Run make update after troubleshooting**:
   ```
   /ci:make-update /path/to/release
   ```

## Tested Repositories

This command has been tested and verified to work with the following OpenShift repositories on macOS:

**Tested:**
- **[openshift/release](https://github.com/openshift/release)** - Tested multiple times (primary use case)
  - Generates ci-operator configs, cluster profiles, and release controller configurations
  - Uses extensive Python generation scripts requiring pyyaml
  - Heavy Podman usage for ci-operator-checkconfig containers

**Should work (similar patterns):**
- **[openshift/ci-tools](https://github.com/openshift/ci-tools)** - CI tooling and ci-operator development
- **[openshift/release-controller](https://github.com/openshift/release-controller)** - Release controller configurations
- Any OpenShift repository with `make update` target that uses ci-operator containers

If you successfully use this command with other repositories, please update this list to help track compatibility.

## Notes

- **macOS only**: This command only works on macOS. Linux users should run `make update` directly.
- **First-time setup**: Initial Podman machine creation may take several minutes
- **Memory allocation**: 4GB is recommended for ci-operator containers; adjust if needed
- **ARM64 native images**: Setting `CONTAINER_ENGINE_OPTS=""` prevents forcing `--platform linux/amd64`, allowing Podman to use native ARM64 images when available
- **Virtual environment**: The `.venv` directory is preserved across runs and added to `.gitignore` by default
- **gnu-sed requirement**: Many OpenShift generation scripts use GNU sed syntax incompatible with BSD sed (macOS default)
- **Podman machine persistence**: Once created and configured, the Podman machine persists across reboots
- **Troubleshooting**: If Podman connection issues persist, try:
  ```bash
  podman machine stop
  podman machine rm
  podman machine init --memory 4096
  podman machine start
  ```

## Troubleshooting

Common issues and solutions on macOS:

1. **"Cannot connect to Podman" error**:
   - Verify machine is running: `podman machine list`
   - Restart machine: `podman machine stop && podman machine start`
   - Check system connections: `podman system connection list`

2. **"platform linux/amd64" errors**:
   - Ensure `CONTAINER_ENGINE_OPTS=""` is set (command does this automatically)
   - Verify no global Podman config is overriding this setting

3. **"sed: illegal option" errors**:
   - Install gnu-sed: `brew install gnu-sed`
   - Verify `gsed` is in PATH

4. **Python import errors**:
   - Delete and recreate venv: `rm -rf .venv && python3 -m venv .venv`
   - Reinstall dependencies: `source .venv/bin/activate && pip install pyyaml`

5. **Insufficient memory errors**:
   - Stop machine: `podman machine stop`
   - Remove machine: `podman machine rm`
   - Recreate with more memory: `podman machine init --memory 8192`

## Arguments

- **$1** (repo-path): Optional path to OpenShift repository. Defaults to current working directory if not provided.

## Platform Support

- **macOS**: Fully supported (Apple Silicon and Intel)
- **Linux**: Not supported - run `make update` directly
- **Windows**: Not supported
