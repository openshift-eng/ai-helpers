---
name: Crypto Parameter Extraction
description: Extract cryptographic parameter values from semgrep results using metavariables and literal parsing
---

# Crypto Parameter Extraction

Extract cryptographic parameter values from semgrep findings. The script prioritizes semgrep metavariables (which extract literals reliably), then falls back to parsing code snippets for literals.

Note: This is a simplified implementation. Complex cases (function calls, cross-file references, control flow) are marked as "unextractable" and may require manual review.

## When to Use This Skill

Use this skill when implementing `/crypto-inventory:scan` or `/crypto-inventory:security` to extract parameter values from crypto operations. The script works best for:

**Priority 1: Semgrep metavariables** (high confidence)

- When semgrep rules extract literals via metavariables (e.g., `$ITERATIONS`, `$KEY_SIZE`)
- Example: `extra.metavars.$ITERATIONS.abstract_content` → extracts `100000`

**Priority 2: Literal parsing** (medium confidence)

- Literal values in code snippets: `pbkdf2.Key(..., 100000, ...)` → extracts `100000`
- Numeric literals (decimal, hex) found in the code snippet

**What it cannot extract:**

- Function calls: `pbkdf2.Key(..., getIterations(), ...)` → marked as "unextractable"
- Variable assignments: `iterations = 100000` (unless in metavars)
- Cross-file references: Variables defined in other files
- Complex control flow: Values from if/else branches, loops
- Runtime values: Function parameters, config files

## Prerequisites

- Python 3.6+ installed (`which python3`)
- Semgrep results JSON file

## Implementation

### Step 1: Run Parameter Extraction Script

Run the extraction script on semgrep results:

```bash
python3 plugins/crypto-inventory/skills/crypto-parameter-extraction/extract_parameters.py \
  --semgrep-results .work/crypto-inventory/semgrep-all.json \
  --output .work/crypto-inventory/parameters.json
```

**Arguments:**

- `--semgrep-results`: Path to semgrep JSON results file (or read from stdin)
- `--output`: Output file path for extracted parameters JSON
- `--workspace-root`: Workspace root directory (default: current directory)

**Example:**

```bash
python3 plugins/crypto-inventory/skills/crypto-parameter-extraction/extract_parameters.py \
  --semgrep-results .work/crypto-inventory/semgrep-all.json \
  --output .work/crypto-inventory/parameters.json
```

### Step 2: Parse Extracted Parameters

Read the extracted parameters JSON:

```bash
cat .work/crypto-inventory/parameters.json
```

**Output structure:**

```json
{
  "extracted_parameters": [
    {
      "file_path": "pkg/crypto/key.go",
      "line": 45,
      "column": 12,
      "check_id": "go-crypto-pbkdf2-iterations",
      "parameter_name": "iterations",
      "parameter_type": "iterations",
      "value": 100000,
      "confidence": "high",
      "resolution_path": ["semgrep metavar $ITERATIONS: 100000"]
    }
  ],
  "total_extracted": 1,
  "summary": {
    "high_confidence": 1,
    "medium_confidence": 0,
    "low_confidence": 0,
    "unextractable": 0
  }
}
```

**Parameter fields:**

- `file_path`: Source file path
- `line`, `column`: Location of crypto call
- `check_id`: Semgrep rule identifier
- `parameter_name`: Name of extracted parameter
- `parameter_type`: Type (key_size, iterations, cipher_mode, etc.)
- `value`: Extracted value (int, str, list, or null if unextractable)
- `confidence`: Extraction confidence (high, medium, low, unextractable)
- `resolution_path`: Chain showing how value was resolved

### Step 3: Handle Unextractable Parameters

For parameters marked as "unextractable", the script could not automatically resolve them. These may require:

- Manual code review
- Cross-file resolution
- Runtime value analysis
- Configuration file lookup

The LLM can handle these cases manually if needed for security-critical parameters.

## Parameter Extraction Capabilities

The script handles:

**High confidence (from semgrep metavariables):**

- Literal values extracted by semgrep rules via metavariables (e.g., `$ITERATIONS`, `$KEY_SIZE`, `$MODE`)
- Semgrep's `abstract_content` field contains the literal value already parsed

**Medium confidence (from code snippet parsing):**

- Numeric literals (decimal, hex) found in `extra.lines` code snippet
- Simple pattern matching for numbers in function call arguments

The script marks as unextractable:

- Function calls requiring AST traversal
- Variable assignments not captured by metavariables
- Cross-file references
- Complex control flow
- Runtime values (function parameters)

## Error Handling

- If script fails, check stderr for error messages
- If semgrep results are invalid JSON, script will fail with parse error
- Missing files are skipped (logged to stderr)

## See Also

- `crypto-semgrep-execution` skill - Generates semgrep results
- `/crypto-inventory:scan` command - Uses this skill for parameter extraction
- `/crypto-inventory:security` command - Uses this skill for security-critical parameter extraction
