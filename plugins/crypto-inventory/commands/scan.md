---
description: Scan codebase and generate a comprehensive crypto usage inventory from user code and third-party dependencies
argument-hint: [--format markdown|json] [--output path] [--language go|python|java|javascript|typescript|rust|c|cpp|csharp|auto] [--include-deps]
---

## Name

crypto-inventory:scan

## Synopsis

```
/crypto-inventory:scan [--format markdown|json] [--output path] [--language go|python|java|javascript|typescript|rust|c|cpp|csharp|auto] [--include-deps]
```

## Description

Scans codebase for crypto usage in user code and dependencies. Identifies crypto operations, categorizes by type, and extracts parameter values when available.

Use `/crypto-inventory:security` for security issues. Use `/crypto-inventory:find` to search for specific algorithms.

## Implementation

Execute these steps directly. Don't write scripts - use available tools (grep, codebase_search, read_file) and generate the report.

Read `plugins/crypto-inventory/skills/crypto-detection-core/SKILL.md` for shared phases:

- Phase 1: Language Detection - Identify programming languages in the codebase
- Phase 2: Determine Detection Method - Choose semgrep or pattern matching based on availability
- Phase 4: Common Filtering Rules - Filter out test files, comments, and false positives
- Phase 5: Error Handling - Handle semgrep failures, file access errors, and edge cases

Execute those phases, then continue with command-specific logic below.

### Phase 1-2: Language Detection and Detection Method

See `crypto-detection-core` skill for language detection, semgrep availability check, skill loading, and parameter extraction setup.

### Phase 3a: Scan User Code Using Semgrep

If semgrep is available:

1. Execute semgrep scan:

   Run the script from `crypto-semgrep-execution` skill:

   ```bash
   python3 plugins/crypto-inventory/skills/crypto-semgrep-execution/run_semgrep_scan.py \
     --config "https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml" \
     --output ".work/crypto-inventory/semgrep-all.json" \
     [--include-deps]
   ```

   If `--include-deps` flag is present, add `--include-deps` to the script command.

2. Parse semgrep JSON output

   - Read semgrep output file
   - Extract results array
   - For each result, extract:
     - `check_id`: Rule identifier
     - `path`: File path
     - `start.line`, `start.col`: Location
     - `message`: Human-readable message
     - `metadata.category`, `metadata.cwe`, `metadata.impact`
     - `extra.severity`, `extra.lines`: Code snippet

3. Pre-filter findings:

   - Test files: Exclude unless `--include-tests` flag
   - Vendor dependencies: Mark separately, skip deep extraction
   - Low-value findings: File integrity hashes, skip extraction
   - Prioritize: Process Tier 1 (RSA, PBKDF2, AES mode, IV, TLS) first, then Tier 2

4. Extract parameters (optional):

   Check `extra.metavars` in semgrep results first. Common metavariables: `$KEY_SIZE`, `$ITERATIONS`, `$MODE`, `$IV`, `$NONCE`. Extract from `extra.metavars.$VAR.abstract_content`.

   If metavariables aren't available, extract literals from `extra.lines` code snippet.

   Parameter extraction is optional for inventory - focus on finding where crypto is used.

5. Filter findings

   Apply filtering rules from `crypto-detection-core` skill:

   - Always exclude: Comments, build artifacts, documentation false positives
   - Include vendor/dependency directories (categorized separately)
   - Conditionally exclude: Test files (report separately), example code (configurable)
   - Remove duplicates (same rule, same file, same line)

6. Categorize findings

   Map rule IDs to operation categories:

   - `-crypto-md5.yml`, `-crypto-sha1.yml` → Hashing
   - `-crypto-aes.yml`, `-crypto-cipher-*.yml` → Encryption
   - `-crypto-rsa.yml`, `-crypto-ecdsa.yml` → Signing
   - `-crypto-pbkdf2.yml`, `-crypto-scrypt.yml` → Key Derivation
   - `*-crypto-random-generation.yml` → Random Generation
   - `-crypto-tls-.yml` → TLS/SSL

   Categorize by source:

   - User Code: Files not in vendor/dependency directories
   - Third-Party Dependencies: Files in vendor/dependency directories
   - Report both categories separately

7. Extract context
   - Read file around each finding
   - Identify function/method name
   - Understand usage context
   - Note related crypto operations nearby
   - Mark user code vs vendor/dependency code

### Phase 3b: Scan User Code Using Pattern Matching

If semgrep is not available:

1. Find Crypto Imports

   Use patterns from `crypto-finder-patterns` skill:

   - Go: `grep -r "import.crypto/" --include="*.go" .`
   - Python: `grep -rE "(hashlib|hmac|secrets|cryptography)" --include="*.py" .`
   - Java: `grep -rE "(javax\.crypto|java\.security)" --include="*.java" .`
   - JavaScript/TypeScript: `grep -rE "(require.crypto|import.crypto|from ['\"]crypto)" --include="*.js" --include="*.ts" .`
   - Rust: `grep -rE "(use.crypto|extern crate crypto)" --include="*.rs" .`
   - C/C++: `grep -rE "(openssl|libcrypto|gcrypt|crypto\+\+|nss|gnutls)" --include="*.c" --include="*.cpp" .`
   - C#: `grep -rE "(System\.Security\.Cryptography|System\.Cryptography)" --include="*.cs" .`
   - Use `codebase_search` for semantic searches

2. Identify Crypto Operations

   For each file with crypto imports, read and analyze:

   - Crypto packages imported
   - Functions/methods called from crypto packages
   - Categorize: Encryption (AES, DES, RSA, ChaCha20), Hashing (MD5, SHA1, SHA256, SHA512, BLAKE2), Signing (RSA, ECDSA, Ed25519, HMAC), Key Derivation (PBKDF2, scrypt, argon2, HKDF), Random, TLS/SSL, Other

3. Extract Parameters and Context

   For each crypto usage, capture: file path, line numbers, function/method name, operation type, package name, extracted parameters, brief context.

   Parameter extraction: Extract from semgrep metavariables (`extra.metavars`) if available, otherwise from code snippet (`extra.lines`). For comprehensive inventory, parameters are optional - focus on identifying crypto usage locations.

Pattern matching fallback for missing semgrep findings:

1. PBKDF2: `grep -rE "pbkdf2\.Key|pbkdf2\.Derive" --include="*.go" .` (check vendor, imports)
2. Scrypt: `grep -rE "scrypt\.Key|scrypt\.Derive" --include="*.go" .` (check vendor)
3. Argon2: `grep -rE "argon2\.IDKey|argon2\.Key|argon2\.Derive" --include="*.go" .` (check vendor)
4. JWT libraries: `grep -rE "import.*[\"'](.*jose|.*jwt)" --include="*.go" .` (check usage)

Add found patterns to report even if semgrep missed them.

### Phase 4: Scan Dependencies for Crypto Packages

For each detected language:

1. Parse Dependency Files

   - Go:
     - Read `go.mod` file from workspace root
     - Extract all dependencies using `go list -mod=mod -m all` (handles vendored modules)
     - Identify crypto dependencies using multiple methods:
       a. Direct grep: `go list -mod=mod -m all | grep -i crypto` (finds modules with "crypto" in name)
       b. Import analysis: Search source files for crypto-related imports:
       - `grep -rE "import.*[\"'](.*crypto|.*jose|.*jwt|.*tls|.*x509|.*ssh)" --include="*.go" .`
       - Common crypto libraries: `go-jose`, `golang-jwt`, `jwt-go`, `crypto-ssh`, etc.
         c. Package analysis: For each dependency, check if it's imported with crypto-related patterns:
       - Check `go.mod` for module names that might be crypto-related
       - Search for imports like `"github.com/go-jose/go-jose/v3"`, `"gopkg.in/square/go-jose.v2"`, etc.
         d. Vendor directory: If vendor exists, scan vendor directory for crypto packages:
       - `find vendor -type d -name "*crypto*" -o -name "*jose*" -o -name "*jwt*"`
   - Python:
     - Read `requirements.txt` or `pyproject.toml` or `setup.py`
     - If available, run `pip list | grep -i crypto`
     - Identify crypto-related packages
   - Node.js:
     - Read `package.json` and `package-lock.json` if available
     - Search for crypto-related dependencies
     - If available, run `npm list | grep crypto`
   - Java:
     - Read `pom.xml` or `build.gradle`
     - If available, run `mvn dependency:tree | grep -i crypto`
     - Identify crypto-related dependencies
   - Rust:
     - Read `Cargo.toml` and `Cargo.lock` if available
     - Search for crypto-related crates
     - If available, run `cargo tree | grep crypto`
   - C/C++:
     - Check `CMakeLists.txt`, `Makefile`, `configure.ac` for crypto library dependencies
     - Look for linker flags: `-lssl`, `-lcrypto`, `-lgcrypt`, `-lnss3`, `-lgnutls`
     - Check `pkg-config` references to openssl, libcrypto, nss, gnutls
   - C#:
     - Read `.csproj`, `.sln`, `packages.config` if available
     - Search for `System.Security.Cryptography` references
     - If available, run `dotnet list package | grep -i crypto`

2. Categorize Crypto Dependencies

   - Standard Library: Built-in crypto packages (e.g., Go's `crypto/*`, Python's `hashlib`)
   - Extended Library: Extended standard libraries (e.g., `golang.org/x/crypto/*`)
   - Third-Party Crypto Libraries: Dedicated crypto libraries (e.g., `go-jose`, `golang-jwt`, `cryptography` for Python, `crypto-js` for JavaScript)
   - Libraries with Crypto: Libraries that use crypto but aren't primarily crypto libraries

   IMPORTANT: For Go, also check for crypto libraries that don't have "crypto" in their module name:

   - JWT libraries: `go-jose`, `golang-jwt`, `jwt-go`
   - SSH libraries: `golang.org/x/crypto/ssh`
   - TLS libraries: `golang.org/x/crypto/acme`
   - Search imports: `grep -rE "import.*[\"'](.*jose|.*jwt|.*ssh|.*acme)" --include="*.go" .`

3. Get Dependency Versions
   - For each crypto-related dependency, extract:
     - Module/package name
     - Version
     - Whether it's direct or transitive
     - Purpose (what crypto functionality it provides)

### Phase 5: Generate Inventory Report (Tiered Structure)

1. Create Report Structure

   - Location: `.work/crypto-inventory/inventory/report.md` (or user-specified path via `--output`)
   - Format: Markdown (default) or JSON (if `--format json`)
   - Create directory if needed: `mkdir -p .work/crypto-inventory/inventory/`

2. Generate Tiered Report (Summary First, Details On-Demand)

   Use progressive disclosure to reduce token usage:

   a. Executive Summary (always include - concise):

   ```markdown
   # Crypto Inventory Report

   ## Executive Summary

   - Languages detected: Go, Python
   - Total crypto operations: 45 (user code: 32, dependencies: 13)
   - Operations by category:
     - Encryption: 12 locations
     - Hashing: 18 locations
     - Signing: 8 locations
     - Key Derivation: 4 locations
     - TLS/SSL: 3 locations
   - Security-critical parameters extracted: 8 (RSA keys, PBKDF2 iterations, AES modes)
   - Test files excluded: 5 findings (see summary below)
   - Vendor dependencies: 13 findings (categorized separately)

   For detailed findings, see sections below.
   ```

   b. Summary Tables (use tables instead of prose for repetitive data):

   ```markdown
   ## Summary by Language

   | Language | User Code | Dependencies | Total |
   | -------- | --------- | ------------ | ----- |
   | Go       | 25        | 8            | 33    |
   | Python   | 7         | 5            | 12    |

   ## Summary by Category

   | Category       | User Code | Dependencies | Total |
   | -------------- | --------- | ------------ | ----- |
   | Encryption     | 8         | 4            | 12    |
   | Hashing        | 15        | 3            | 18    |
   | Signing        | 6         | 2            | 8     |
   | Key Derivation | 3         | 1            | 4     |
   | TLS/SSL        | 2         | 1            | 3     |
   ```

   c. Detailed Sections (group similar findings, use patterns):

   Instead of listing every finding individually, group by pattern:

   ```markdown
   ## User Code Operations

   ### Go

   #### Encryption (8 locations)

   AES-GCM (5 locations):

   - `pkg/crypto/encrypt.go:42` - AES-256-GCM, key from config
   - `pkg/crypto/encrypt.go:89` - AES-256-GCM, key from config
   - `pkg/crypto/encrypt.go:156` - AES-256-GCM, key from config
   - `pkg/crypto/encrypt.go:203` - AES-256-GCM, key from config
   - `pkg/crypto/encrypt.go:250` - AES-256-GCM, key from config

   AES-CBC (2 locations):

   - `pkg/legacy/old_encrypt.go:12` - AES-128-CBC (requires review)
   - `pkg/legacy/old_encrypt.go:45` - AES-128-CBC (requires review)

   RSA Encryption (1 location):

   - `pkg/crypto/rsa.go:78` - RSA-2048-OAEP
   ```

   d. Filtered Findings Summary (counts only, not details):

   ```markdown
   ## Filtered Findings Summary

   - Test files excluded: 5 findings (use `--include-tests` to see details)
   - Low-value findings skipped: 3 file integrity hashes
   - Vendor dependencies: 13 findings (see Dependencies section)
   ```

3. Report Sections (Detailed):

   Executive Summary

   ```markdown
   # Crypto Usage Inventory

   Generated: {timestamp}
   Codebase: {workspace-path}

   ## Summary

   - Languages detected: {list of languages}
   - Total crypto packages in user code: {count}
   - Total crypto dependencies: {count}
   - Operations found: {encryption, hashing, signing, etc.}
   ```

   Languages Detected

   ```markdown
   ## Languages Detected

   - Go (detected via go.mod and \*.go files)
   - Python (detected via requirements.txt and \*.py files)
     ...
   ```

   User Code Crypto Usage (organized by language)

   ```markdown
   ## User Code

   ### Go

   #### Encryption Operations

   | File                   | Function        | Package    | Operation   | Parameters                                                                    | Context             |
   | ---------------------- | --------------- | ---------- | ----------- | ----------------------------------------------------------------------------- | ------------------- |
   | pkg/auth/encrypt.go:45 | EncryptPassword | crypto/aes | AES-256-GCM | Key: 256-bit (PBKDF2-SHA256, 100k iter), IV: 12-byte (crypto/rand), Mode: GCM | Password encryption |

   #### Hashing Operations

   ...

   ### Python

   ...
   ```

   Dependencies (organized by language)

   ```markdown
   ## Dependencies

   ### Go

   #### Standard Library

   - `crypto/aes` (built-in)
   - `crypto/rand` (built-in)

   #### Extended Library (golang.org/x/crypto)

   - `golang.org/x/crypto/bcrypt` v0.1.0 (direct)
   - `golang.org/x/crypto/ssh` v0.1.0 (transitive via github.com/example/ssh-client)

   #### Third-Party Crypto Libraries

   - `github.com/golang-jwt/jwt/v5` v5.2.0 (direct)
     Purpose: JWT token signing and verification

   ### Python

   ...
   ```

   Categorized Breakdown

   ```markdown
   ## Operations by Category

   ### Encryption

   - User code: {count} locations across {languages}
   - Dependencies: {list}

   - Algorithms: AES, DES, RSA, ChaCha20, etc.

   ### Hashing

   ...
   ```

   For security analysis, use `/crypto-inventory:security`.

4. Complete Example Report

   See `.developer/examples/scan-report-example.md` for a realistic complete example that demonstrates the expected output format. Use this as a reference when generating reports.

   Report Structure:

   - Executive summary with statistics
   - Languages detected
   - User code crypto operations (organized by language) with extracted parameters
   - Dependency inventory (organized by language)
   - Categorized breakdown by operation type
   - Deprecation warnings (if any)
   - Filtered findings summary

   See `.developer/examples/scan-report-example.md` for the complete example report.

5. Format Output (Optimized)

   - Use clear Markdown formatting with tables (not prose for repetitive data)
   - Group related information together (patterns, not individual instances)
   - Use summary tables for statistics
   - Include file paths as clickable links (if in IDE context)
   - Make it scannable with clear headers
   - Progressive disclosure: Summary first, details grouped by pattern
   - For large reports (>100 findings), consider:
     - Summary in main report
     - Detailed findings in separate file: `.work/crypto-inventory/inventory/details.md`
     - Link between summary and details
   - For JSON format, use structured data matching the Markdown sections

### Phase 6: Validate and Display Results

1. Validate language detection

   - If no languages detected:

     ```text
     Error: No supported language files found in workspace.

     Checked for: Go, Python, Java, JavaScript, TypeScript, Rust, C, C++, C#

     Suggestions:
     - Verify workspace contains source code
     - Check that language files are not all in ignored directories
     - Use --language flag to force specific language
     ```

     - Exit with error code

2. Validate findings

   - If no crypto found:

     ```text
     No cryptographic usage detected.

     This may indicate:
     - Codebase does not use cryptography
     - Patterns didn't match actual usage (try manual search)
     - All findings were filtered as tests/vendor code

     Suggestions:
     - Review .work/crypto-inventory/inventory/debug.log for filtered findings
     - Try manual search: grep -r "crypto" .
     - Use /crypto-inventory:scan --include-tests to see test crypto usage
     ```

     - Still generate report with "No crypto found" message

   - If only test crypto found:

     ```text
     Crypto usage found only in test files (5 occurrences).
     No crypto usage in production code.

     Use --include-tests flag to see test crypto usage details.
     ```

     - Generate report noting test-only findings

3. Handle errors gracefully

   - If semgrep crashed:

     ```text
     Warning: Semgrep scan failed with error: <error message>
     Falling back to pattern-based detection...
     ```

     - Switch to Phase 3b for affected languages
     - Continue with pattern matching

   - If file access denied:

     ```text
     Warning: Unable to read 3 files (permission denied):
     - /path/to/file1.go
     - /path/to/file2.py

     These files were skipped in the analysis.
     ```

     - Log skipped files
     - Continue with accessible files

4. Success criteria:

   - At least one language detected: ✓
   - Findings in production code OR explicit "no crypto found": ✓
   - Report generated successfully: ✓
   - No critical errors: ✓

5. Display report

   - Read the generated report
   - Display summary to user:

     ```text
     Crypto inventory complete!

     Summary:
     - Languages: Go, Python
     - Crypto operations: 12 locations
     - Dependencies: 8 packages
     - Report saved to: .work/crypto-inventory/inventory/report.md
     ```

   - Provide path to full report

## Return Value

- Format: Markdown report at `.work/crypto-inventory/inventory/report.md` (or specified path)
- Content:
  - Summary of crypto usage
  - Languages detected
  - User code crypto operations with file locations (organized by language)
  - Dependency inventory (organized by language)
  - Categorized breakdown
  - Timestamp and codebase information

## Examples

1. Basic inventory:

   ```bash
   /crypto-inventory:scan
   ```

   Generates Markdown report in `.work/crypto-inventory/inventory/report.md`

2. JSON output:

   ```bash
   /crypto-inventory:scan --format json --output crypto-report.json
   ```

   Generates JSON report for programmatic processing

3. Specific language:

   ```bash
   /crypto-inventory:scan --language go
   ```

   Only scans for Go crypto usage

4. Custom output path:

   ```bash
   /crypto-inventory:scan --output ./reports/crypto-inventory.md
   ```

   Saves report to custom location

5. **Include third-party dependencies**:
   ```bash
   /crypto-inventory:scan --include-deps
   ```
   Includes vendor/, node_modules/, and other dependency directories in the scan

## Arguments

- `--format`: Output format (markdown|json). Default: markdown
- `--output`: Output file path. Default: `.work/crypto-inventory/inventory/report.md`
- `--language`: Specific language to scan (go|python|java|javascript|typescript|rust|c|cpp|csharp|auto). Default: auto (detect all)
- `--include-deps`: Include third-party dependencies (vendor/, node_modules/, etc.) in the scan. Creates a temporary .semgrepignore file to ensure these directories are scanned. Use this flag if semgrep is not scanning vendor directories. The file is automatically cleaned up after the scan.

## Notes

- Uses semgrep with argus-observe-rules when available, falls back to pattern matching
- Scans source code only (not binaries or generated code)
- Includes direct and transitive dependencies
- Distinguishes user code from dependencies
- For security analysis, use `/crypto-inventory:security`
- Report saved locally (not committed to git)
- Supports mixed-language codebases

## Prerequisites

- Read access to source files in the workspace
- Optional: `semgrep` for enhanced detection (uses GitHub raw URLs for argus-observe-rules, no local installation needed)
- Optional: Language-specific toolchains for dependency analysis (Go, Python, Node.js, Java, Rust)
