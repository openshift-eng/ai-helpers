---
name: Crypto Detection Core
description: Shared core logic for crypto detection: language detection, semgrep setup, filtering rules, and error handling
---

# Crypto Detection Core

Shared core logic for `/crypto-inventory:scan` and `/crypto-inventory:security` commands.

## When to Use This Skill

Use when implementing crypto detection commands for:

- Language detection
- Detection method selection (semgrep vs pattern matching)
- Semgrep setup using GitHub raw URLs
- Common filtering rules
- Error handling patterns

## Phase 1: Language Detection

### Step 1: Check for Explicit Language Flag

Use `--language` flag if provided and not "auto". Otherwise, detect languages automatically.

### Step 2: Detect Languages in Codebase

Language Detection Table:

| Language   | File Extensions               | Dependency Files                                 |
| ---------- | ----------------------------- | ------------------------------------------------ |
| Go         | `*.go`                        | `go.mod`                                         |
| Python     | `*.py`                        | `requirements.txt`, `pyproject.toml`, `setup.py` |
| JavaScript | `*.js`                        | `package.json`, `package-lock.json`, `yarn.lock` |
| TypeScript | `*.ts`                        | `package.json`, `package-lock.json`, `yarn.lock` |
| Java       | `*.java`                      | `pom.xml`, `build.gradle`                        |
| Rust       | `*.rs`                        | `Cargo.toml`, `Cargo.lock`                       |
| C          | `.c`, `.h`                    | `CMakeLists.txt`, `Makefile`                     |
| C++        | `.cpp`, `.cc`, `.cxx`, `.hpp` | `CMakeLists.txt`, `Makefile`                     |
| C#         | `.cs`                         | `.csproj`, `*.sln`                               |

Detection Commands:

```bash
# Check for source files (sample first 5)
find . -name "*.go" -type f | head -5      # Go
find . -name "*.py" -type f | head -5      # Python
find . -name "*.js" -type f | head -5      # JavaScript
find . -name "*.ts" -type f | head -5      # TypeScript
find . -name "*.java" -type f | head -5    # Java
find . -name "*.rs" -type f | head -5      # Rust
find . -name "*.c" -type f | head -5       # C
find . \( -name "*.cpp" -o -name "*.cc" -o -name "*.cxx" \) -type f | head -5  # C++
find . -name "*.cs" -type f | head -5      # C#

# Check for dependency files
test -f go.mod && echo "Go detected"
test -f requirements.txt -o -f pyproject.toml -o -f setup.py && echo "Python detected"
test -f package.json && echo "JavaScript/TypeScript detected"
test -f pom.xml -o -f build.gradle && echo "Java detected"
test -f Cargo.toml && echo "Rust detected"
test -f CMakeLists.txt -o -f Makefile && echo "C/C++ detected"
find . -name "*.csproj" -o -name "*.sln" | head -1 >/dev/null && echo "C# detected"
```

- Compile list of detected languages

## Phase 2: Determine Detection Method

### Step 1: Check for Semgrep Availability

```bash
which semgrep >/dev/null 2>&1
```

### Step 2: Load Appropriate Skills

If semgrep is available:

- Read `plugins/crypto-inventory/skills/crypto-semgrep-execution/SKILL.md`
- Use Semgrep Method

If semgrep is not available:

- Read `plugins/crypto-inventory/skills/crypto-finder-patterns/SKILL.md`
- Use Pattern Method

### Step 3: Load Parameter Extraction Skill

Read `plugins/crypto-inventory/skills/crypto-parameter-extraction/SKILL.md`

## Phase 3: Semgrep Setup and Execution

### Argus-Observe-Rules Configuration

Use the single crypto-all.yml config file that includes all languages:

```bash
CONFIG_URL="https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml"
```

This single config file contains rules for all supported languages (Go, Python, Java, JavaScript, TypeScript, Rust, C, C++, C#), eliminating the need to detect languages or fetch multiple rule files.

### Semgrep Execution

Execute semgrep scan using `crypto-semgrep-execution` skill:

- Use single config URL (crypto-all.yml)
- Run the Python script from `crypto-semgrep-execution` skill
- Include `--include-deps` flag if `--include-deps` is present in the command

For comprehensive inventory (includes dependencies), use the script with `--include-deps` flag.

For security-focused scans (excludes dependencies), use the script without `--include-deps` flag.

See `crypto-semgrep-execution` skill for complete implementation.

## Phase 4: Common Filtering Rules

Apply these filtering rules consistently to all findings:

### Always Exclude

- Comments and docstrings
- Build artifacts: `/_generated.go`, `/.pb.go`, `/generated/`, `/build/`, `/dist/`, `/target/`
- Documentation false positives: Markdown files mentioning crypto APIs, README examples

### Vendor/Dependency Directories

Vendor and dependency directories (`vendor/`, `node_modules/`, `site-packages/`, `thirdparty/`, `.venv/`, `venv/`) are handled differently by command:

- `/crypto-inventory:scan`: Include these directories by default (use `--include-deps` flag to ensure they're scanned)
- `/crypto-inventory:security`: Exclude these directories by default (security scans focus on user code)

### Conditionally Exclude

- Test files: Excluded by default, report count separately
- Example code in `examples/` directory: Included by default

### Never Exclude

- Example code in main codebase
- Commented-out crypto code
- Dead code

### Additional Filtering

- Remove duplicates (same rule, same file, same line)
- Verify findings are not in comments/docstrings by reading file context

## Phase 5: Error Handling

### Language Detection Errors

If no languages detected:

```text
Error: No supported language files found in workspace.
Checked for: Go, Python, Java, JavaScript, TypeScript, Rust, C, C++, C#
Suggestions:
- Verify workspace contains source code
- Use --language flag to force specific language
```

- Exit with error code

### Finding Validation

If no crypto found:

```text
No cryptographic usage detected.
This may indicate:
- Codebase does not use cryptography
- Patterns didn't match actual usage
- All findings were filtered as tests/vendor code
Suggestions:
- Review debug logs for filtered findings
- Try manual search: grep -r "crypto" .
- Use --include-tests flag to see test crypto usage
```

- Still generate report with "No crypto found" message

If only test crypto found:

```text
Crypto usage found only in test files (5 occurrences).
No crypto usage in production code.
Use --include-tests flag to see test crypto usage details.
```

- Generate report noting test-only findings

### Semgrep Errors

If semgrep failed (exit code != 0):

1. Check the actual error message:

   - Read semgrep output file to see error details
   - Common exit codes:
     - Exit code 1: Found issues (normal, not an error)
     - Exit code 2: Fatal error
     - Exit code 7: Invalid rule or parsing error
     - Exit code 8: Invalid language
     - Exit code 9: Missing config

2. Debug steps:

   a. Test with the config file to verify accessibility:

   ```bash
   # Test with single config file
   CONFIG_URL="https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml"
   semgrep --config="${CONFIG_URL}" \
     --json \
     --output=.work/crypto-inventory/test-config.json \
     .
   ```

   b. Check if config file is accessible:

   ```bash
   # Verify config file is accessible
   curl -I "https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml"
   ```

   c. Test with verbose output to see what rules are being loaded:

   ```bash
   # Test with verbose output
   CONFIG_URL="https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml"
   semgrep --config="${CONFIG_URL}" \
     --verbose \
     --json \
     --output=.work/crypto-inventory/test-verbose.json \
     .
   ```

   d. Check semgrep version:

   ```bash
   semgrep --version
   ```

3. If semgrep crashed or returned error:

   ```text
   Warning: Semgrep scan failed with error: <error message>
   Exit code: <code>
   Falling back to pattern-based detection...
   ```

   - Log error details to `.work/crypto-inventory/debug.log`
   - Switch to pattern-based detection for affected languages
   - Continue with pattern matching

### File Access Errors

If file access denied, log skipped files and continue with accessible files.

### Success Criteria

- At least one language detected: ✓
- Findings in production code OR explicit "no crypto found": ✓
- Report generated successfully: ✓
- No critical errors: ✓

## Phase 6: Security Assessment Rules

Use these rules to assess the security of extracted crypto parameters:

### RSA Key Size Assessment

- 1024 bits: CRITICAL (deprecated, insecure since 2010)
- 2048 bits: ACCEPTABLE (current minimum standard)
- 3072 bits: GOOD (recommended, future-proof)
- 4096 bits: STRONG (high security, may impact performance)

Assessment Logic: If key size < 2048: Flag as CRITICAL, recommend upgrading to 2048+. If key size == 2048: Mark as ACCEPTABLE. If key size >= 3072: Mark as GOOD or STRONG.

### PBKDF2 Iteration Assessment

- < 10,000: WEAK (insufficient for modern security)
- 10,000 - 100,000: ACCEPTABLE (minimum acceptable)
- 100,000 - 600,000: GOOD (recommended range)
- > 600,000: STRONG (may impact performance)

Assessment Logic: If iterations < 10,000: Flag as WEAK, recommend minimum 100,000. If iterations < 100,000: Mark as ACCEPTABLE, recommend increasing. If iterations >= 100,000: Mark as GOOD or STRONG.

### Scrypt Parameter Assessment

- N < 2^14 (16384): WEAK (insufficient memory cost)
- N >= 2^14: ACCEPTABLE (minimum acceptable)
- N >= 2^15 (32768): GOOD (recommended)
- N >= 2^16 (65536): STRONG (high security)

Assessment Logic: Verify N is a power of 2. If N < 16384: Flag as WEAK. If N >= 16384: Mark as ACCEPTABLE or better.

### AES Mode Assessment

- GCM/CCM/SIV: SECURE (authenticated encryption, no separate MAC needed)
- CBC/CTR: REVIEW (requires separate MAC/HMAC for authentication)
- ECB: CRITICAL (insecure, deterministic, never use)

Assessment Logic: If mode is GCM/CCM/SIV: Mark as SECURE. If mode is CBC/CTR: Mark as "REQUIRES REVIEW - Ensure separate MAC/HMAC". If mode is ECB: Flag as CRITICAL, recommend GCM.

### IV/Nonce Generation Assessment

- crypto/rand or secrets module: SECURE (cryptographically random)
- Hardcoded IV: CRITICAL (predictable, breaks security)
- IV reuse: CRITICAL (same IV used multiple times)
- IV length mismatch: REVIEW (verify length matches algorithm requirements)

Assessment Logic: GCM requires 12-byte nonce; CBC requires 16-byte IV. Hardcoded IVs and IV reuse are both CRITICAL vulnerabilities. Verify IV length matches algorithm requirements; flag mismatches as REVIEW.

### TLS Version Assessment

- TLS 1.3: SECURE (latest standard)
- TLS 1.2: ACCEPTABLE (current minimum)
- TLS 1.1: DEPRECATED (should upgrade)
- TLS 1.0: CRITICAL (deprecated, insecure)

Assessment Logic: If MinVersion < TLS 1.2: Flag as CRITICAL or DEPRECATED. If MinVersion == TLS 1.2: Mark as ACCEPTABLE. If MinVersion == TLS 1.3: Mark as SECURE.

### Certificate Validation Assessment

- Validation enabled: SECURE (default behavior)
- InsecureSkipVerify: true: CRITICAL (bypasses certificate validation)

Assessment Logic: If InsecureSkipVerify is true: Flag as CRITICAL. Recommend enabling certificate validation.

### Hash Function Context Assessment

- Password hashing with raw hash (SHA256/MD5): INSECURE (use KDF instead)
- Password hashing with PBKDF2/scrypt/Argon2/bcrypt: SECURE
- File integrity / checksum: ACCEPTABLE (non-security-critical)
- Digital signature: SECURE (appropriate usage)

Assessment Logic: Functions suggesting password hashing with raw hash are INSECURE; those using KDF are SECURE. File integrity and digital signature contexts are both ACCEPTABLE uses.

## Integration with Commands

This skill is referenced by:

- `/crypto-inventory:scan`: Uses Phases 1-2, 4-5
- `/crypto-inventory:security`: Uses Phases 1-2, 4-5, 6

Usage Pattern:

1. Reference this skill at the start of command implementation
2. Execute shared phases from this skill
3. Implement command-specific logic (inventory vs security analysis)
4. Use shared filtering and error handling from this skill
5. Use Phase 6 security assessment rules when evaluating extracted parameters
