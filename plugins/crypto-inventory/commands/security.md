---
description: Scan codebase for security-critical cryptographic issues and provide actionable recommendations
argument-hint: [--format markdown|json] [--output path] [--language go|python|java|javascript|typescript|rust|c|cpp|csharp|auto] [--include-deps]
---

## Name

crypto-inventory:security

## Synopsis

```
/crypto-inventory:security [--format markdown|json] [--output path] [--language go|python|java|javascript|typescript|rust|c|cpp|csharp|auto] [--include-deps]
```

## Description

Finds security-critical crypto issues: hardcoded secrets, insecure random, deprecated algorithms, weak encryption modes. Provides recommendations.

For complete inventory, use `/crypto-inventory:scan`.

## Implementation

Follow instructions directly. Do not write scripts. Execute steps using available tools (grep, codebase_search, read_file) and generate the report directly.

Read `plugins/crypto-inventory/skills/crypto-detection-core/SKILL.md` for shared phases:

- Phase 1: Language Detection - Identify programming languages in the codebase
- Phase 2: Determine Detection Method - Choose semgrep or pattern matching based on availability
- Phase 4: Common Filtering Rules - Filter out test files, comments, and false positives
- Phase 5: Error Handling - Handle semgrep failures, file access errors, and edge cases

Execute those phases, then continue with security-specific logic below.

### Phase 1-2: Language Detection and Detection Method

See `crypto-detection-core` skill for language detection, semgrep availability check, skill loading, and parameter extraction setup.

### Phase 3a: Scan Using Semgrep

If semgrep is available:

1. Run semgrep scan:

   Run the script from `crypto-semgrep-execution` skill:

   ```bash
   python3 plugins/crypto-inventory/skills/crypto-semgrep-execution/run_semgrep_scan.py \
     --config "https://raw.githubusercontent.com/smith-xyz/argus-observe-rules/main/configs/crypto-all.yml" \
     --output ".work/crypto-inventory/security-all.json" \
     [--include-deps]
   ```

   Security scans exclude dependencies by default. If `--include-deps` flag is present, add `--include-deps` to the script command.

2. Extract parameters:

   Check `extra.metavars` in semgrep results first. Common: `$KEY_SIZE`, `$ITERATIONS`, `$MODE`, `$IV`, `$NONCE`. Extract from `extra.metavars.$VAR.abstract_content`.

   If metavariables aren't available, extract literals from `extra.lines` code snippet.

   Only use parameter extraction script if both methods fail and the parameter is security-critical.

3. Assess security:

   Apply security rules from `crypto-detection-core` skill:

   - RSA key size: < 2048 = CRITICAL, 2048 = OK, >= 3072 = GOOD
   - PBKDF2 iterations: < 10k = WEAK, < 100k = OK, >= 100k = GOOD
   - AES mode: ECB = CRITICAL, CBC/CTR = REVIEW, GCM/CCM/SIV = SECURE
   - IV/Nonce: Hardcoded = CRITICAL, reuse = CRITICAL
   - TLS version: < TLS 1.2 = CRITICAL, TLS 1.2 = OK, TLS 1.3 = SECURE
   - Certificate validation: InsecureSkipVerify = CRITICAL
   - Hash context: Password hashing with raw hash = INSECURE

4. Filter and categorize security findings

   Apply filtering rules from `crypto-detection-core` skill (Phase 4: Common Filtering Rules), then categorize by severity:

   - CRITICAL Severity: Hardcoded secrets/keys, insecure random, AES-ECB, RC4, RSA < 2048 bits, PBKDF2 < 10k iterations, hardcoded IV, IV reuse, TLS < 1.2, certificate validation disabled
   - HIGH Severity: MD5/SHA1 for signatures, DES/3DES, RSA 2048 bits (acceptable but consider upgrading), PBKDF2 < 100k iterations, AES-CBC without MAC
   - MEDIUM Severity: Deprecated algorithms in acceptable contexts, environment variable key storage, file-based key storage

### Phase 3b: Scan Using Pattern Matching

If semgrep is not available:

1. Detect Hardcoded Secrets (CRITICAL)

   ```bash
   # Common secret variable names
   grep -rE "(SECRETKEY|APIKEY|PRIVATE_KEY|PASSWORD|TOKEN|SECRET)\s=\s[\"']" --include="*" .

   # Base64-encoded keys (40+ chars)
   grep -rE "[A-Za-z0-9+/]{40,}={0,2}" --include="*.go" --include="*.py" --include="*.js" .

   # PEM-encoded private keys
   grep -rE "-----BEGIN (RSA |EC )?PRIVATE KEY-----" --include="*" .

   # Long hex strings near crypto operations (32+ chars)
   grep -rE "0x[0-9a-fA-F]{32,}" --include="*.go" --include="*.py" --include="*.c" .
   ```

2. Detect Insecure Random (CRITICAL)

   ```bash
   # Insecure patterns (CRITICAL)
   grep -rE "(import.*math/rand|from random import|Math\.random|java\.util\.Random|System\.Random)" \
     --include="*.go" --include="*.py" --include="*.js" --include="*.java" --include="*.cs" .
   ```

3. Detect Deprecated/Weak Crypto

   ```bash
   # MD5 (deprecated)
   grep -rE "(md5|MD5)" --include="*.go" --include="*.py" --include="*.js" .

   # SHA1 (deprecated for signatures)
   grep -rE "(sha1|SHA1)" --include="*.go" --include="*.py" --include="*.js" .

   # DES/3DES (weak)
   grep -rE "(DES|des|3DES)" --include="*.go" --include="*.py" --include="*.java" .

   # RC4 (broken)
   grep -rE "(RC4|rc4)" --include="*.go" --include="*.py" --include="*.java" .
   ```

4. Detect Weak Encryption Modes

   ```bash
   # AES-ECB (CRITICAL - deterministic)
   grep -rE "(ECB|ecb|NewECB)" --include="*.go" --include="*.py" .

   # AES-CBC (requires review - needs MAC)
   grep -rE "(CBC|cbc|NewCBC)" --include="*.go" --include="*.py" .
   ```

5. Extract parameters and assess security (optimized)

   Pre-filter findings before extraction:

   - Filter test files (unless `--include-tests`)
   - Filter vendor dependencies (focus on user code security)
   - Prioritize Tier 1 security-critical findings

   Batch findings by file before extraction:

   - Group findings by file path
   - Read file once per file (not per finding)
   - Cache file contents during processing

   For each finding:

   - Read file context around each finding (5-10 lines, expand only if needed)
   - Use grep to pre-locate identifiers before reading:

     ```bash
     grep -n "iterations.*=" file.go | head -3
     grep -n "const.*iterations" file.go
     ```

   - Extract parameters using `crypto-parameter-extraction` skill (Tier 1 only):
     - Key sizes (RSA, AES)
     - Cipher modes (GCM, CBC, CTR, ECB)
     - Key derivation parameters (PBKDF2 iterations, scrypt N/r/p)
     - IV/nonce generation method and length
     - TLS configuration (version, cipher suites)
     - Hash function context (password hashing vs file integrity)
   - Apply security assessment rules from `crypto-detection-core` skill:
     - Assess parameter values against security thresholds
     - Flag weak parameters (RSA < 2048, PBKDF2 < 100k, ECB mode, etc.)
     - Determine severity based on parameter values and context
   - Identify function/method name
   - Understand usage context
   - Determine final severity based on parameters and context

### Phase 4: Generate Security Report

1. Create Report Structure

   - Location: `.work/crypto-inventory/security/report.md` (or user-specified path via `--output`)
   - Format: Markdown (default) or JSON (if `--format json`)
   - Create directory if needed: `mkdir -p .work/crypto-inventory/security/`

2. Report Sections:

   Executive Summary

   ```markdown
   # Cryptographic Security Audit

   Generated: {timestamp}
   Codebase: {workspace-path}
   Detection Method: {semgrep|pattern}

   ## Summary

   - Critical Issues: {count} (IMMEDIATE ACTION REQUIRED)
   - High Severity: {count}
   - Medium Severity: {count}
   - Languages Scanned: {list}
   ```

   Critical Issues (IMMEDIATE ACTION REQUIRED)

   ```markdown
   ## Critical Issues

   ### Hardcoded Secrets ({count} instances)

   | File          | Line | Variable   | Type   | Recommendation                              |
   | ------------- | ---- | ---------- | ------ | ------------------------------------------- |
   | pkg/config.go | 45   | SECRET_KEY | Base64 | Move to AWS KMS/Azure Key Vault             |
   | src/auth.py   | 12   | api_key    | String | Use environment variable or secrets manager |

   Action Required: Move all hardcoded secrets to secrets management (AWS KMS, Azure Key Vault, HashiCorp Vault)

   ### Insecure Random Number Generation ({count} instances)

   | File         | Line | Function      | Insecure API    | Secure Alternative   |
   | ------------ | ---- | ------------- | --------------- | -------------------- |
   | pkg/token.go | 23   | GenerateToken | math/rand       | crypto/rand          |
   | src/utils.py | 67   | generateid    | random.random() | secrets.tokenbytes() |

   Action Required: Replace with cryptographically secure random - IMMEDIATE

   ### AES-ECB Encryption ({count} instances)

   | File           | Line | Function    | Recommendation                            |
   | -------------- | ---- | ----------- | ----------------------------------------- |
   | pkg/encrypt.go | 89   | EncryptData | Replace with AES-GCM or ChaCha20-Poly1305 |

   Action Required: IMMEDIATE - ECB is deterministic and insecure
   ```

   High Severity Issues

   ```markdown
   ## High Severity Issues

   ### Deprecated Algorithms

   - MD5 ({count} instances): Cryptographically broken for collision resistance

     - If used for checksums/cache: Acceptable
     - If used for signatures/certificates: MIGRATE to SHA256
     - If used for passwords: MIGRATE to Argon2/bcrypt/scrypt

   - SHA1 ({count} instances): Deprecated for signatures (2017)

     - If used for HMAC: Acceptable (still secure)
     - If used for signatures/certificates: MIGRATE to SHA256+

   - DES/3DES ({count} instances): Legacy algorithms, weak keys
     - Recommendation: MIGRATE to AES-256-GCM
   ```

   Requires Review

   ```markdown
   ## Requires Review

   ### Non-Authenticated Encryption Modes

   - AES-CBC ({count} instances): Requires separate MAC for integrity

     - Verify HMAC is applied separately (Encrypt-then-MAC)
     - Consider migrating to AES-GCM

   - AES-CTR ({count} instances): No authentication
     - Verify separate MAC is used
     - Consider migrating to AES-GCM

   ### Key Management

   - Environment Variables ({count} instances): Acceptable for development, not recommended for production

     - Recommendation: Migrate to dedicated secrets management

   - File-based Storage ({count} instances): Keys in config files
     - Recommendation: Use secrets management (KMS, Key Vault, Vault)
   ```

3. Format Output

   - Use clear Markdown formatting with tables
   - Group by severity (Critical → High → Medium → Review)
   - Include actionable recommendations for each finding
   - For JSON format, use structured data with severity levels

### Phase 5: Validate and Display Results

1. Validate findings

   - If no security issues found:

     ```text
     ✓ No critical security issues detected.

     This is excellent! Your codebase appears to use secure cryptographic practices.

     For complete inventory, use `/crypto-inventory:scan`.
     ```

     - Still generate report with "No issues found" message

2. Display report

   - Read the generated report
   - Display summary to user:

     ```text
     Security audit complete!

     Summary:
     - Critical Issues: 3 (IMMEDIATE ACTION REQUIRED)
     - High Severity: 5
     - Medium Severity: 2
     - Report saved to: .work/crypto-inventory/security/report.md
     ```

   - Provide path to full report

## Return Value

- Format: Markdown report at `.work/crypto-inventory/security/report.md` (or specified path)
- Content:
  - Summary of security-critical findings
  - Critical issues requiring immediate action
  - High/medium severity issues
  - Actionable recommendations for each finding
  - Severity-based categorization

## Examples

1. Basic security audit:

   ```bash
   /crypto-inventory:security
   ```

   Scans all languages and generates security report

2. Language-specific audit:

   ```bash
   /crypto-inventory:security --language go
   ```

   Only scans Go code for security issues

3. JSON output:

   ```bash
   /crypto-inventory:security --format json --output security-report.json
   ```

   Generates JSON format security report

## Arguments

- `--format`: Output format (markdown|json). Default: markdown
- `--output`: Output file path. Default: `.work/crypto-inventory/security/report.md`
- `--language`: Specific language to scan (go|python|java|javascript|typescript|rust|c|cpp|csharp|auto). Default: auto (detect all)
- `--include-deps`: Include third-party dependencies (vendor/, node_modules/, etc.) in the security scan. Creates a temporary .semgrepignore file to ensure these directories are scanned. Use this flag if semgrep is not scanning vendor directories. The file is automatically cleaned up after the scan. Note: Security scans exclude dependencies by default; this flag overrides that behavior.

## Notes

- Focuses on security issues only. For complete inventory, use `/crypto-inventory:scan`
- Uses semgrep with argus-observe-rules when available, falls back to pattern matching
- Severity levels: Critical (immediate action), High (migrate soon), Medium (review), Review (verify context)

## Prerequisites

- Read access to source files in the workspace
- See `scan.md` Prerequisites section for semgrep and argus-observe-rules setup (optional but recommended)
