---
description: Set or view the OLM version context for this session
argument-hint: [v0|v1|clear]
---

## Name
olm:use-version

## Synopsis
```
/olm:use-version [v0|v1|clear]
```

## Description
The `olm:use-version` command manages the OLM version context for your current session. This allows you to set the OLM version once and have all subsequent OLM commands use that version automatically, eliminating the need to specify `--version` flag on every command.

**Why use this command:**
- Reduces repetition when working with multiple OLM commands
- Makes workflows cleaner and easier to read
- Provides explicit control over which OLM version is being used
- Can be changed at any time during your session

**Context storage:** The version context is stored in `.work/olm/context.txt` and persists for the duration of your session.

## Implementation

1. **Parse the argument**:
   - If no argument provided: Display current context
   - If argument is `v0` or `v1`: Set context to that version
   - If argument is `clear`: Remove the context file
   - If argument is invalid: Show error and usage help

2. **Create context directory** (if setting version):
   ```bash
   mkdir -p .work/olm
   ```

3. **Handle "view current context" (no argument)**:
   ```bash
   if [ -f .work/olm/context.txt ]; then
     CURRENT_VERSION=$(cat .work/olm/context.txt)
     echo "Current OLM version context: $CURRENT_VERSION"
   else
     echo "No OLM version context is set"
     echo ""
     echo "To set a context:"
     echo "  /olm:use-version v0  (for traditional OLM)"
     echo "  /olm:use-version v1  (for next-generation OLM)"
     echo ""
     echo "Or use --version flag on each command:"
     echo "  /olm:install <name> --version v0 [options]"
     echo ""
     echo "Not sure which version to use? Run:"
     echo "  /olm:detect-version"
   fi
   exit 0
   ```

4. **Handle "set to v0"**:
   ```bash
   echo "v0" > .work/olm/context.txt
   echo "✓ OLM version context set to: v0"
   echo ""
   echo "All OLM commands will now use OLM v0 (traditional OLM) by default."
   echo "You can override this per-command with the --version flag."
   echo ""
   echo "OLM v0 uses:"
   echo "  - Resources: Subscription, CSV, InstallPlan, OperatorGroup"
   echo "  - Catalogs: CatalogSource, PackageManifest"
   echo "  - CLI: oc (OpenShift CLI)"
   echo ""
   echo "To switch to v1: /olm:use-version v1"
   echo "To clear context: /olm:use-version clear"
   ```

5. **Handle "set to v1"**:
   ```bash
   echo "v1" > .work/olm/context.txt
   echo "✓ OLM version context set to: v1"
   echo ""
   echo "All OLM commands will now use OLM v1 (next-generation OLM) by default."
   echo "You can override this per-command with the --version flag."
   echo ""
   echo "OLM v1 uses:"
   echo "  - Resources: ClusterExtension, ClusterCatalog"
   echo "  - RBAC: User-managed ServiceAccount + ClusterRole"
   echo "  - CLI: kubectl"
   echo ""
   echo "To switch to v0: /olm:use-version v0"
   echo "To clear context: /olm:use-version clear"
   ```

6. **Handle "clear"**:
   ```bash
   if [ -f .work/olm/context.txt ]; then
     rm -f .work/olm/context.txt
     echo "✓ OLM version context cleared"
     echo ""
     echo "You will need to specify --version flag on each command, or set a new context."
   else
     echo "No context was set"
   fi
   ```

7. **Handle invalid argument**:
   ```bash
   echo "❌ Invalid argument: $1"
   echo ""
   echo "Usage: /olm:use-version [v0|v1|clear]"
   echo ""
   echo "Options:"
   echo "  v0     - Set context to OLM v0 (traditional OLM)"
   echo "  v1     - Set context to OLM v1 (next-generation OLM)"
   echo "  clear  - Clear the context"
   echo "  (none) - View current context"
   exit 1
   ```

## Return Value
- **Success (view)**: Displays current context or message if not set
- **Success (set)**: Confirmation message with version set and helpful information
- **Success (clear)**: Confirmation that context was cleared
- **Error**: Invalid argument with usage help
- **Format**: Human-readable status messages

## Examples

1. **View current context**:
   ```
   /olm:use-version
   ```
   
   Output (when set):
   ```
   Current OLM version context: v0
   ```
   
   Output (when not set):
   ```
   No OLM version context is set
   
   To set a context:
     /olm:use-version v0  (for traditional OLM)
     /olm:use-version v1  (for next-generation OLM)
   ```

2. **Set context to OLM v0**:
   ```
   /olm:use-version v0
   ```
   
   Output:
   ```
   ✓ OLM version context set to: v0
   
   All OLM commands will now use OLM v0 (traditional OLM) by default.
   You can override this per-command with the --version flag.
   
   OLM v0 uses:
     - Resources: Subscription, CSV, InstallPlan, OperatorGroup
     - Catalogs: CatalogSource, PackageManifest
     - CLI: oc (OpenShift CLI)
   ```

3. **Set context to OLM v1**:
   ```
   /olm:use-version v1
   ```
   
   Output:
   ```
   ✓ OLM version context set to: v1
   
   All OLM commands will now use OLM v1 (next-generation OLM) by default.
   You can override this per-command with the --version flag.
   
   OLM v1 uses:
     - Resources: ClusterExtension, ClusterCatalog
     - RBAC: User-managed ServiceAccount + ClusterRole
     - CLI: kubectl
   ```

4. **Clear context**:
   ```
   /olm:use-version clear
   ```
   
   Output:
   ```
   ✓ OLM version context cleared
   
   You will need to specify --version flag on each command, or set a new context.
   ```

5. **Typical workflow**:
   ```
   # Set context once
   /olm:use-version v0
   
   # All commands now use v0
   /olm:search cert-manager
   /olm:install cert-manager-operator
   /olm:status cert-manager-operator
   
   # Switch to v1 for different workflow
   /olm:use-version v1
   /olm:install argocd --channel stable
   ```

## Arguments
- **$1** (version): Optional argument specifying the action
  - `v0`: Set context to OLM v0 (traditional OLM with Subscription/CSV)
  - `v1`: Set context to OLM v1 (next-generation OLM with ClusterExtension)
  - `clear`: Remove the context, requiring explicit --version flags
  - (empty): View the current context

## Notes

- **Persistence**: The context is stored in `.work/olm/context.txt` which is ignored by git (in `.gitignore`)
- **Session-scoped**: The context persists for your current work session but does not survive across different machines or repository clones
- **Override**: You can always override the context with `--version` flag on any command
- **No default**: If no context is set and no `--version` flag is provided, commands will error with helpful guidance
- **Switching**: You can switch between v0 and v1 at any time without affecting already-installed operators/extensions

