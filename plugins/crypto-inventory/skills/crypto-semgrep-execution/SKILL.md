---
name: Semgrep Execution
description: Execute semgrep scans and process results for crypto detection
---

# Semgrep Execution

Standardized semgrep execution for crypto detection. Handles rule fetching, .semgrepignore management, cleanup, and result processing.

## When to Use This Skill

Use this skill whenever you need to:

- Run semgrep scans with argus-observe-rules from GitHub
- Ensure vendor/dependency directories are scanned (via .semgrepignore override)
- Handle existing .semgrepignore files safely
- Execute semgrep with proper cleanup
- Parse and process semgrep JSON output
- Filter and categorize findings

This skill is used by:

- `crypto-detection-core` skill (Phase 3: Semgrep Setup and Execution)
- `/crypto-inventory:scan` command
- `/crypto-inventory:security` command

## Prerequisites

- `semgrep` CLI installed and available in PATH
- Python 3.6+ installed (`which python3`)
- Network access to GitHub (for fetching crypto-all.yml config)
- Write access to workspace root (for temporary .semgrepignore, only if `--include-deps` flag is used)

## Implementation

### Step 1: Run Semgrep Scan Script

Run the `run_semgrep_scan.py` script:

```bash
python3 plugins/crypto-inventory/skills/crypto-semgrep-execution/run_semgrep_scan.py \
  --config "https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml" \
  --output ".work/crypto-inventory/semgrep-all.json" \
  [--include-deps]
```

**Arguments:**

- `--config`: Semgrep config URL (always use crypto-all.yml)
- `--output`: Output file path for JSON results
- `--include-deps`: Include this flag to scan vendor/dependency directories

**Example for comprehensive inventory (includes dependencies):**

```bash
python3 plugins/crypto-inventory/skills/crypto-semgrep-execution/run_semgrep_scan.py \
  --config "https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml" \
  --output ".work/crypto-inventory/semgrep-all.json" \
  --include-deps
```

**Example for security-focused scan (excludes dependencies):**

```bash
python3 plugins/crypto-inventory/skills/crypto-semgrep-execution/run_semgrep_scan.py \
  --config "https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml" \
  --output ".work/crypto-inventory/security-all.json"
```

### Step 2: Parse Semgrep Output

Read the JSON output file:

```bash
cat .work/crypto-inventory/semgrep-all.json
```

Parse the JSON structure:

```json
{
  "version": "1.x.x",
  "paths": {
    "scanned": ["file1.go", "file2.py"]
  },
  "results": [
    {
      "check_id": "go-crypto-md5",
      "path": "pkg/auth/hash.go",
      "start": { "line": 15, "col": 5 },
      "end": { "line": 15, "col": 15 },
      "message": "MD5 hash function usage detected",
      "metadata": {
        "category": "crypto",
        "cwe": "CWE-327",
        "impact": "Inventory: MD5 hash function usage detected in codebase"
      },
      "extra": {
        "severity": "INFO",
        "lines": "hash := md5.New()",
        "metavars": {
          "$KEY_SIZE": {
            "start": { "line": 20, "col": 12 },
            "end": { "line": 20, "col": 16 },
            "abstract_content": "2048"
          },
          "$ITERATIONS": {
            "start": { "line": 25, "col": 15 },
            "end": { "line": 25, "col": 21 },
            "abstract_content": "100000"
          }
        }
      }
    }
  ],
  "errors": []
}
```

Key fields to extract for each result:

- `check_id`: Rule identifier (e.g., `go-crypto-md5`, `python-crypto-sha256`)
- `path`: File path
- `start.line`, `start.col`: Location
- `end.line`, `end.col`: End location
- `message`: Human-readable message
- `metadata.category`: Usually "crypto"
- `metadata.cwe`: CWE identifier if applicable
- `metadata.impact`: Description
- `extra.severity`: Severity level
- `extra.lines`: Code snippet
- `extra.metavars`: **Parameter values extracted by semgrep** (if available)

**Using Metavariables:**

If `extra.metavars` is present, use it for parameter values. Semgrep already extracted them:

- `extra.metavars.$KEY_SIZE.abstract_content` → key size value
- `extra.metavars.$ITERATIONS.abstract_content` → iterations value
- `extra.metavars.$MODE.abstract_content` → cipher mode value

Common metavariables: `$KEY_SIZE`, `$ITERATIONS`, `$MODE`, `$IV`, `$NONCE`. Names vary by rule.

If metavariables aren't available, extract literals from `extra.lines` code snippet.

### Step 3: Filter and Process Findings

Filter findings to reduce noise:

1. Filter by file type:

   - Exclude test files: `test.go`, `test.py`, `*Test.java`
   - Exclude examples: `/examples/`, `/samples/`
   - Exclude generated code: `/generated/`, `/gen/`
   - For `/crypto-inventory:scan`: Include vendor dependencies
   - For `/crypto-inventory:security`: Exclude vendor dependencies

2. Filter by context:

   - Read file around finding to check if it's in comments/documentation
   - Check if it's in test code (acceptable for testing)
   - Check if it's dead code (unreachable)

3. Filter duplicates:

   - Same rule, same file, same line → keep one
   - Same rule, same file, different lines → keep all (multiple instances)
   - Different rules, same location → keep all (related findings)

4. Filter false positives:
   - Comments mentioning crypto APIs
   - Documentation strings
   - String literals containing crypto names (not actual usage)

### Step 4: Categorize Findings

Map semgrep rule IDs to operation categories:

Hashing: `*-crypto-md5`, `*-crypto-sha1`, `*-crypto-sha256`, `*-crypto-sha512`, `*-crypto-sha3`, `*-crypto-blake2`, `*-crypto-hmac`

Encryption: `*-crypto-aes`, `*-crypto-cipher-des`, `*-crypto-cipher-rc4`, `*-crypto-chacha20`, `*-crypto-cipher-modes`

Signing: `*-crypto-rsa`, `*-crypto-ecdsa`, `*-crypto-digital-signatures`

Key Derivation: `*-crypto-pbkdf2`, `*-crypto-scrypt`, `*-crypto-argon2`, `*-crypto-hkdf`, `*-crypto-bcrypt`, `*-crypto-key-derivation`

Random Generation: `*-crypto-random-generation`

TLS/SSL: `*-crypto-tls-version`, `*-crypto-tls-cipher-suites`, `*-crypto-certificate-validation`

Other: `*-crypto-hardcoded-key`, `*-crypto-iv-nonce`, `*-crypto-password-hashing`

### Step 5: Organize Findings

Group findings by:

- Language (from rule ID prefix: `go-`, `python-`, `java-`, etc.)
- Operation type (hashing, encryption, signing, etc.)
- File path (all crypto usage in a single file)
- Function/method (extract context from code snippets)

## Error Handling

- If the script fails, check stderr for error messages
- If semgrep fails, the script returns a non-zero exit code
- The script always cleans up .semgrepignore even if semgrep fails
- If config URL is unavailable, check network connectivity

## Integration with Patterns Skill

When semgrep is not available or doesn't cover a language:

1. Fall back to `crypto-finder-patterns` skill
2. Use grep/pattern matching for detection
3. Combine results with semgrep findings if both available

## Notes

- Semgrep rules are for inventory (INFO severity), not security judgment
- Rules use neutral language ("detected" not "weak" or "insecure")
- Some rules may have false positives - verify context
- Test files may legitimately use crypto for testing
- Semgrep can be slow on large codebases - consider excluding vendor/node_modules for security scans
- JSON output can be large - process incrementally if needed

## See Also

- `crypto-detection-core` skill - Uses this skill for semgrep execution
- `crypto-finder-patterns` skill - Pattern matching fallback when semgrep unavailable
- `/crypto-inventory:scan` command - Uses this skill for comprehensive inventory
- `/crypto-inventory:security` command - Uses this skill for security-focused scans
