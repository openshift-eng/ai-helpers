---
name: OLM Version Detection
description: Determine which OLM version to use based on context and flags
---

# OLM Version Detection Skill

This skill provides the logic for determining which OLM version (v0 or v1) to use in unified OLM commands. All unified commands should use this logic at the beginning of their implementation.

## When to Use This Skill

Use this skill in any OLM command that supports both v0 and v1 implementations:
- `/olm:install`
- `/olm:list`
- `/olm:search`
- `/olm:status`
- `/olm:uninstall`
- `/olm:upgrade`
- `/olm:catalog`

## Prerequisites

- User has access to the workspace directory (for reading `.work/olm/context.txt`)
- Command arguments have been parsed

## Version Determination Logic

### Priority Order

The version is determined in this order (highest to lowest priority):

1. **`--version` flag in command arguments** (overrides everything)
2. **Context file** at `.work/olm/context.txt` (session default)
3. **No version found** → Error with helpful message

### Implementation Steps

#### Step 1: Check for --version Flag

Parse the command arguments for a `--version` flag:

```bash
OLM_VERSION=""

# Parse arguments for --version flag
for arg in "$@"; do
  case $arg in
    --version=*)
      OLM_VERSION="${arg#*=}"
      shift
      ;;
    --version)
      shift
      OLM_VERSION="$1"
      shift
      ;;
  esac
done
```

#### Step 2: Check Context File (if flag not provided)

If no `--version` flag was found, check the context file:

```bash
if [ -z "$OLM_VERSION" ]; then
  if [ -f .work/olm/context.txt ]; then
    OLM_VERSION=$(cat .work/olm/context.txt)
    echo "Using OLM version from context: $OLM_VERSION"
    echo ""
  fi
fi
```

#### Step 3: Validate Version

Ensure the version is valid (v0 or v1):

```bash
if [ -n "$OLM_VERSION" ]; then
  if [ "$OLM_VERSION" != "v0" ] && [ "$OLM_VERSION" != "v1" ]; then
    echo "❌ Invalid OLM version: $OLM_VERSION"
    echo ""
    echo "Valid versions are: v0, v1"
    exit 1
  fi
fi
```

#### Step 4: Error if No Version Found

If still no version is found, display a helpful error:

```bash
if [ -z "$OLM_VERSION" ]; then
  echo "❌ OLM version not specified"
  echo ""
  echo "You must explicitly specify the OLM version:"
  echo ""
  echo "Option 1 - Set context for this session:"
  echo "  /olm:use-version v0  (for traditional OLM)"
  echo "  /olm:use-version v1  (for next-generation OLM)"
  echo ""
  echo "Option 2 - Use per-command flag:"
  echo "  /olm:install <name> --version v0 [options]"
  echo "  /olm:install <name> --version v1 [options]"
  echo ""
  echo "Not sure which version to use?"
  echo "  /olm:detect-version"
  echo ""
  exit 1
fi
```

#### Step 5: Branch to Version-Specific Implementation

Now branch based on the determined version:

```bash
if [ "$OLM_VERSION" == "v0" ]; then
  echo "Using OLM v0 (traditional OLM)"
  echo ""
  # ... Execute v0-specific implementation
  
elif [ "$OLM_VERSION" == "v1" ]; then
  echo "Using OLM v1 (next-generation OLM)"
  echo ""
  # ... Execute v1-specific implementation
fi
```

## Complete Reusable Template

Here's a complete template that can be used in any unified command:

```bash
#!/bin/bash

# ============================================================================
# OLM Version Detection (Shared Logic)
# ============================================================================

OLM_VERSION=""

# Step 1: Check for --version flag
for arg in "$@"; do
  case $arg in
    --version=*)
      OLM_VERSION="${arg#*=}"
      ;;
    --version)
      # Next argument is the version
      NEXT_IS_VERSION=true
      ;;
    *)
      if [ "$NEXT_IS_VERSION" == "true" ]; then
        OLM_VERSION="$arg"
        NEXT_IS_VERSION=false
      fi
      ;;
  esac
done

# Step 2: Check context file if flag not provided
if [ -z "$OLM_VERSION" ]; then
  if [ -f .work/olm/context.txt ]; then
    OLM_VERSION=$(cat .work/olm/context.txt)
    echo "ℹ️  Using OLM version from context: $OLM_VERSION"
    echo ""
  fi
fi

# Step 3: Validate version
if [ -n "$OLM_VERSION" ]; then
  if [ "$OLM_VERSION" != "v0" ] && [ "$OLM_VERSION" != "v1" ]; then
    echo "❌ Invalid OLM version: $OLM_VERSION"
    echo ""
    echo "Valid versions are: v0, v1"
    exit 1
  fi
fi

# Step 4: Error if no version found
if [ -z "$OLM_VERSION" ]; then
  cat << 'EOF'
❌ OLM version not specified

You must explicitly specify the OLM version:

Option 1 - Set context for this session:
  /olm:use-version v0  (for traditional OLM)
  /olm:use-version v1  (for next-generation OLM)

Option 2 - Use per-command flag:
  /olm:install <name> --version v0 [options]
  /olm:install <name> --version v1 [options]

Not sure which version to use?
  /olm:detect-version

EOF
  exit 1
fi

# ============================================================================
# Version-Specific Implementation
# ============================================================================

if [ "$OLM_VERSION" == "v0" ]; then
  echo "═══════════════════════════════════════════════════════════════"
  echo "Using OLM v0 (Traditional OLM)"
  echo "═══════════════════════════════════════════════════════════════"
  echo ""
  
  # ... OLM v0 implementation here ...
  
elif [ "$OLM_VERSION" == "v1" ]; then
  echo "═══════════════════════════════════════════════════════════════"
  echo "Using OLM v1 (Next-Generation OLM)"
  echo "═══════════════════════════════════════════════════════════════"
  echo ""
  
  # ... OLM v1 implementation here ...
fi
```

## Usage in Command Files

In your command markdown files, reference this skill in the Implementation section:

```markdown
## Implementation

1. **Determine OLM version** (see [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md)):
   - Check for `--version` flag in arguments
   - If no flag: Check context file `.work/olm/context.txt`
   - If neither: Display error and exit
   - Validate version is `v0` or `v1`

2. **Branch to version-specific implementation**:

---

### OLM v0 Implementation

[v0-specific steps here]

---

### OLM v1 Implementation

[v1-specific steps here]
```

## Examples

### Example 1: Using Context

```bash
# User sets context
/olm:use-version v0

# Command runs, reads context
/olm:install cert-manager-operator
# → Detects v0 from .work/olm/context.txt
# → Executes v0 implementation
```

### Example 2: Using Flag

```bash
# No context set, user provides flag
/olm:install cert-manager --version v1 --channel stable
# → Detects v1 from --version flag
# → Executes v1 implementation
```

### Example 3: Flag Overrides Context

```bash
# User sets context to v0
/olm:use-version v0

# But uses flag to override
/olm:install argocd --version v1 --channel stable
# → Flag takes precedence
# → Executes v1 implementation
```

### Example 4: No Version Specified (Error)

```bash
# No context set, no flag provided
/olm:install cert-manager
# → No version found
# → Displays error message with help
# → Exits with code 1
```

## Testing Checklist

When implementing a unified command, test these scenarios:

- [ ] Command works with `--version v0` flag
- [ ] Command works with `--version v1` flag
- [ ] Command works with v0 context set
- [ ] Command works with v1 context set
- [ ] Command errors helpfully with no version
- [ ] Flag overrides context correctly
- [ ] Invalid version value shows error
- [ ] Error messages are clear and actionable

## Best Practices

1. **Always use this skill first** - Version detection should be the first step in unified commands
2. **Clear separation** - Keep v0 and v1 implementations clearly separated in the code
3. **Consistent messaging** - Use the same error messages across all commands
4. **No defaults** - Never default to v0 or v1, always require explicit selection
5. **Helpful errors** - Always guide users toward solutions when version is missing
6. **Context indicator** - Show which version is being used (from context or flag)

## Troubleshooting

### Issue: Context file not readable

**Symptom**: Command can't read `.work/olm/context.txt` even though it exists

**Solution**: Check file permissions and ensure `.work/olm/` directory exists and is accessible

### Issue: Version persists unexpectedly

**Symptom**: User thinks they cleared context but commands still use a version

**Solution**: Check if `.work/olm/context.txt` still exists. Run `/olm:use-version` to verify.

### Issue: Flag not recognized

**Symptom**: `--version v0` is not parsed correctly

**Solution**: Ensure flag parsing happens before positional arguments. The version detection logic should be at the very beginning of command parsing.

