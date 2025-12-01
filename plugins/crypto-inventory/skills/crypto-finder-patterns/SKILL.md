---
name: Crypto Finder Patterns
description: Comprehensive patterns and search strategies for finding cryptographic usage across multiple programming languages
---

# Crypto Finder Patterns

Patterns, search strategies, and categorization guidance for identifying cryptographic usage across multiple programming languages.

## Quick Navigation

IMPORTANT: Only read sections for detected languages. Do not read entire file.

Based on detected languages, use the Language Pattern Template section with language-specific data table.

Common sections (read these regardless of language):

- Language Pattern Template → "Language Pattern Template" section
- Categorization → "Categorization Guide" section
- Parameter Extraction → "Parameter Extraction Patterns" section
- Search Strategy → "Search Strategy" section

## When to Use This Skill

Use this skill when implementing `/crypto-inventory:scan` to:

- Find crypto imports and usage patterns in user code
- Identify crypto dependencies in package managers
- Categorize crypto operations by type
- Generate comprehensive crypto inventories
- Identify which semgrep rules to use from argus-observe-rules

## Selecting Semgrep Rules from Argus Observe Rules

When using semgrep (see `crypto-semgrep-execution` skill), use the single crypto-all.yml config file that includes all languages and rules.

### Rule Directory Structure

The argus-observe-rules project organizes rules by language:

```text
argus-observe-rules/rules/languages/
├── go/crypto/          # Go crypto rules
├── python/crypto/      # Python crypto rules
├── java/crypto/        # Java crypto rules
├── javascript/crypto/   # JavaScript crypto rules
├── typescript/crypto/  # TypeScript crypto rules
├── rust/crypto/        # Rust crypto rules
├── c/crypto/           # C crypto rules
├── cpp/crypto/         # C++ crypto rules
└── csharp/crypto/      # C# crypto rules
```

### Language to Rule Directory Mapping

Based on detected languages, use these rule directories:

- Go → `rules/languages/go/crypto/`
- Python → `rules/languages/python/crypto/`
- Java → `rules/languages/java/crypto/`
- JavaScript → `rules/languages/javascript/crypto/`
- TypeScript → `rules/languages/typescript/crypto/`
- Rust → `rules/languages/rust/crypto/`
- C → `rules/languages/c/crypto/`
- C++ → `rules/languages/cpp/crypto/`
- C# → `rules/languages/csharp/crypto/`

### Rule File Naming Convention

Rules follow a consistent naming pattern: `{lang}-crypto-{operation}.yml`

Examples:

- `go-crypto-md5.yml` - Go MD5 detection
- `python-crypto-sha256.yml` - Python SHA256 detection
- `java-crypto-aes.yml` - Java AES detection
- `javascript-crypto-random-generation.yml` - JavaScript random generation

### Selecting Rules by Operation Type

If you want to detect specific crypto operations, select relevant rule files:

Hashing:

- `*-crypto-md5.yml`
- `*-crypto-sha1.yml`
- `*-crypto-sha256.yml`
- `*-crypto-sha512.yml`
- `*-crypto-sha3.yml`
- `*-crypto-blake2.yml`
- `*-crypto-hmac.yml`

Encryption:

- `*-crypto-aes.yml`
- `*-crypto-cipher-des.yml`
- `*-crypto-cipher-rc4.yml`
- `*-crypto-chacha20.yml`
- `*-crypto-cipher-modes.yml`

Signing:

- `*-crypto-rsa.yml`
- `*-crypto-ecdsa.yml`
- `*-crypto-digital-signatures.yml`

Key Derivation:

- `*-crypto-pbkdf2.yml`
- `*-crypto-scrypt.yml`
- `*-crypto-argon2.yml`
- `*-crypto-hkdf.yml`
- `*-crypto-bcrypt.yml`
- `*-crypto-key-derivation.yml`

Random Generation:

- `*-crypto-random-generation.yml`

TLS/SSL:

- `*-crypto-tls-version.yml`
- `*-crypto-tls-cipher-suites.yml`
- `*-crypto-certificate-validation.yml`

Other:

- `*-crypto-hardcoded-key.yml`
- `*-crypto-iv-nonce.yml`
- `*-crypto-password-hashing.yml`

### Recommended Approach

1. For comprehensive inventory: Use entire `crypto/` directory for each detected language

   ```bash
   semgrep --config=rules/languages/go/crypto/ ...
   ```

2. For specific operations: Select individual rule files

   ```bash
   semgrep --config=rules/languages/go/crypto/go-crypto-md5.yml ...
   semgrep --config=rules/languages/go/crypto/go-crypto-sha256.yml ...
   ```

3. For all languages: Use parent directory (if semgrep supports it)
   ```bash
   semgrep --config=rules/languages/ ...
   ```

### Finding Available Rules

To see what rules are available for a language:

```bash
ls /Users/shsmith/rh/code/personal/argus-observe-rules/rules/languages/go/crypto/
```

This will list all available rule files for that language.

## Language Detection

First, identify which languages are present in the codebase:

1. Check for language-specific files:

   ```bash
   find . -name "*.go" -type f | head -5      # Go
   find . -name "*.py" -type f | head -5      # Python
   find . -name "*.js" -type f | head -5      # JavaScript
   find . -name "*.ts" -type f | head -5      # TypeScript
   find . -name "*.java" -type f | head -5    # Java
   find . -name "*.rs" -type f | head -5      # Rust
   find . -name "*.c" -type f | head -5       # C
   find . -name "*.cpp" -type f | head -5     # C++
   find . -name "*.cc" -type f | head -5      # C++
     find . -name "*.cxx" -type f | head -5     # C++
     find . -name "*.cs" -type f | head -5      # C#
   ```

2. Check for dependency files:
   - `go.mod` → Go
   - `requirements.txt`, `pyproject.toml`, `setup.py` → Python
   - `package.json`, `package-lock.json`, `yarn.lock` → Node.js (JavaScript/TypeScript)
   - `pom.xml`, `build.gradle` → Java
   - `Cargo.toml`, `Cargo.lock` → Rust
   - `CMakeLists.txt`, `Makefile` → C/C++ (indicator)
   - `.csproj`, `.sln` → C# (indicator)

## Language Pattern Template

For each detected language, use this template structure with language-specific data from the table below.

### Template Structure

1. Import Patterns: Use grep command from table to find crypto imports
2. Common Packages: Reference package list from table
3. Function Patterns: See language-specific notes below
4. Dependency Analysis: Use dependency files and commands from table

### Language-Specific Data Table

| Language   | File Ext         | Import Pattern                                                                               | Common Packages                                              | Dependency Files                     | Dependency Command                               |
| ---------- | ---------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------ | ------------------------------------------------ |
| Go         | `*.go`           | `grep -rE "import.*[\"'](.*crypto\|.*jose\|.*jwt\|.*tls\|.*x509\|.*ssh)" --include="*.go" .` | `crypto/*`, `golang.org/x/crypto/*`, `go-jose`, `golang-jwt` | `go.mod`                             | `go list -mod=mod -m all` then filter by imports |
| Python     | `*.py`           | `grep -rE "(hashlib\|hmac\|secrets\|cryptography)" --include="*.py" .`                       | `hashlib`, `hmac`, `secrets`, `cryptography`                 | `requirements.txt`, `pyproject.toml` | `pip list \| grep -i crypto`                     |
| Java       | `*.java`         | `grep -rE "(javax\.crypto\|java\.security)" --include="*.java" .`                            | `java.security.*`, `javax.crypto.*`                          | `pom.xml`, `build.gradle`            | `mvn dependency:tree \| grep -i crypto`          |
| JavaScript | `*.js`           | `grep -rE "(require.*crypto\|import.*crypto)" --include="*.js" .`                            | `crypto`, `crypto-js`                                        | `package.json`                       | `npm list \| grep crypto`                        |
| TypeScript | `*.ts`           | `grep -rE "(import.*crypto\|from ['\"]crypto)" --include="*.ts" .`                           | `crypto`, `node:crypto`                                      | `package.json`                       | `npm list \| grep crypto`                        |
| Rust       | `*.rs`           | `grep -rE "(use.*crypto\|extern crate crypto)" --include="*.rs" .`                           | `ring`, `rustls`, `aes-gcm`                                  | `Cargo.toml`                         | `cargo tree \| grep crypto`                      |
| C          | `*.c`, `*.h`     | `grep -rE "(openssl\|nss\|gnutls)" --include="*.c" --include="*.h" .`                        | OpenSSL, NSS, GnuTLS                                         | `CMakeLists.txt`, `Makefile`         | `pkg-config --list-all \| grep crypto`           |
| C++        | `*.cpp`, `*.hpp` | `grep -rE "(openssl\|crypto\+\+)" --include="*.cpp" --include="*.hpp" .`                     | OpenSSL, Crypto++, Botan                                     | `CMakeLists.txt`, `Makefile`         | `pkg-config --list-all \| grep crypto`           |
| C#         | `*.cs`           | `grep -rE "System\.Security\.Cryptography" --include="*.cs" .`                               | `System.Security.Cryptography.*`                             | `*.csproj`, `*.sln`                  | `dotnet list package \| grep -i crypto`          |

### Language-Specific Function Patterns

Go: `NewCipher`, `NewGCM`, `New()`, `Sum()`, `Sign()`, `Verify()`, `Read()`, `Int()`. Extended: `golang.org/x/crypto/*` (bcrypt, scrypt, pbkdf2, argon2)

Python: `hashlib.md5()`, `hashlib.sha256()`, `hmac.new()`, `secrets.token_bytes()`, `cryptography.fernet.Fernet`

Java: `Cipher`, `MessageDigest`, `Mac`, `KeyGenerator`, `SecureRandom`, `Signature`. Third-party: `org.bouncycastle.*`

JavaScript/TypeScript: `crypto.createCipheriv()`, `crypto.createHash()`, `crypto.createHmac()`, `crypto.randomBytes()`, `crypto.createSign()`

Rust: `ring`, `rustls`, `aes-gcm`, `sha2`, `hmac`, `rand` crates

C: OpenSSL (`EVP`, `SHA256`, `AES`, `RAND`), NSS (`PK11`, `SEC`, `HASH`), GnuTLS (`gnutls_*`), Libgcrypt (`gcrycipher`, `gcrymd`)

C++: OpenSSL (C++ wrappers), NSS (`PK11`, `SEC`, `NSS_*`), Crypto++ (`CryptoPP::*`), Botan (`Botan::*`)

C#: `MD5`, `SHA256`, `Aes`, `RSA`, `ECDsa`, `Rfc2898DeriveBytes`, `RNGCryptoServiceProvider`

### Dependency Analysis (All Languages)

For each detected language:

1. Check for dependency files listed in table
2. Parse dependencies using command from table
3. Filter crypto-related packages/modules/crates
4. Categorize as: Standard Library, Extended Library, Third-Party Crypto, Libraries with Crypto

## Security-Critical Detection Patterns

### Hardcoded Keys and Secrets (CRITICAL)

Detection patterns (all languages):

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

Language-specific patterns:

- Go: `const secretKey = "..."`, `key := []byte("...")`
- Python: `SECRETKEY = "..."`, `apikey = "..."`, `AWSSECRETACCESS_KEY = "..."`
- JavaScript: `const SECRETKEY = "..."`, `process.env.SECRETKEY = "..."`
- Java: `private static final String SECRET_KEY = "..."`
- C#: `private const string SecretKey = "..."`

Severity: CRITICAL - Flag immediately in report

### Key Management Detection

Cloud KMS:

- AWS KMS: `aws-sdk.*kms`, `github.com/aws/aws-sdk-go/service/kms`
- Azure Key Vault: `azure-keyvault`, `Azure.Security.KeyVault`
- Google Cloud KMS: `cloud.google.com/go/kms`, `google-cloud-kms`
- HashiCorp Vault: `github.com/hashicorp/vault/api`, `hvac` (Python)

Platform Keychains:

- iOS: `Security.framework`, `SecItemAdd`, `kSecClass`
- Android: `java.security.KeyStore`, `AndroidKeyStore`
- Windows DPAPI: `CryptProtectData`, `CryptUnprotectData`
- macOS: `SecKeychainItemRef`

Anti-patterns (flag for review):

- Environment variables: `os.Getenv("SECRETKEY")`, `process.env.SECRETKEY`
- File-based: Reading from `.env`, config files (JSON/YAML/TOML)

## Categorization Guide

When you find crypto usage, categorize it:

### Encryption

Authenticated Encryption (AEAD) - SECURE:

- AES-GCM, ChaCha20-Poly1305, AES-CCM, AES-SIV, XChaCha20-Poly1305
- Go: `cipher.NewGCM()`
- Python: `Cipher(algorithms.AES(), modes.GCM())`, `ChaCha20Poly1305()`
- Look for: `GCM`, `Poly1305`, `CCM`, `SIV`

Non-AEAD Modes - REQUIRES REVIEW:

- AES-CBC (vulnerable to padding oracle without separate MAC)
- AES-CTR (no authentication)
- AES-ECB (CRITICAL - deterministic, insecure)
- DES-CBC, 3DES-CBC
- Go: `cipher.NewCBCEncrypter()`
- Python: `Cipher(algorithms.AES(), modes.CBC())`
- Flag AES-ECB as CRITICAL, CBC/CTR as "Requires Review - Ensure separate MAC"

Other:

- AES, DES, 3DES, ChaCha20, RSA encryption
- Look for: `encrypt`, `decrypt`, `cipher`, `AES`, `RSA`

### Hashing

- MD5, SHA1, SHA256, SHA512, BLAKE2
- Look for: `hash`, `digest`, `md5`, `sha`, `blake`

### Signing

- RSA, ECDSA, Ed25519, HMAC
- Look for: `sign`, `verify`, `signature`, `hmac`

### Key Derivation

- PBKDF2, scrypt, argon2, HKDF
- Look for: `pbkdf2`, `scrypt`, `argon2`, `derive`, `kdf`
- Go PBKDF2 patterns:
  - Standard library: `crypto/pbkdf2` (if available)
  - Extended library: `golang.org/x/crypto/pbkdf2`
  - Function signature: `pbkdf2.Key(password, salt, iterations, keyLen, hash)`
  - Search: `grep -rE "pbkdf2\.Key|pbkdf2\.Derive" --include="*.go" .`
  - Also check vendor: `grep -rE "pbkdf2\.Key|pbkdf2\.Derive" vendor/ 2>/dev/null || true`
  - Import patterns: `grep -rE "import.*[\"'](.*pbkdf2|crypto/pbkdf2)" --include="*.go" .`

### Random Number Generation

CRITICAL SECURITY ISSUE: Distinguish secure vs insecure random

Secure Random (Cryptographically Secure):

- Go: `crypto/rand` - `rand.Reader`, `rand.Int()`, `rand.Read()`
- Python: `secrets` module - `secrets.token_bytes()`, `secrets.randbits()`
- JavaScript: `crypto.randomBytes()`, `crypto.getRandomValues()`
- Java: `java.security.SecureRandom`
- C#: `System.Security.Cryptography.RNGCryptoServiceProvider`, `RandomNumberGenerator`
- Rust: `rand_core::OsRng`, `getrandom`

Insecure Random (CRITICAL - Flag as security issue):

- Go: `math/rand` - `rand.Int()`, `rand.Intn()` - NOT secure for crypto
- Python: `random` module - `random.random()`, `random.randint()` - NOT secure
- JavaScript: `Math.random()` - NOT secure
- Java: `java.util.Random` - NOT secure
- C#: `System.Random` - NOT secure
- Rust: `rand::thread_rng()` without `OsRng` seed - verify usage

Detection patterns:

```bash
# Insecure patterns (CRITICAL)
grep -rE "(import.math/rand|from random import|Math\.random|java\.util\.Random|System\.Random)" --include="*.go" --include="*.py" --include="*.js" --include="*.java" --include="*.cs" .
```

Look for: `random`, `rand`, `secure`, `secrets`, `SecureRandom`, `RNGCryptoServiceProvider`

### TLS/SSL

- TLS configuration, certificate handling
- Look for: `tls`, `ssl`, `certificate`, `x509`

## Parameter Extraction Patterns

CRITICAL: Extract specific parameters from crypto operations to understand how crypto is configured, not just where it's used. This provides 80% of engineer value.

### Key Size Extraction

Pattern (works across languages):

```text
{key_generation_function}({key_size_parameter})
```

Language-specific implementations:

- RSA Key Size:

  - Go: `rsa.GenerateKey(rand.Reader, 2048)` → Extract 3rd argument. Also check: `keySize := 2048`
  - Python: `generate_private_key(key_size=2048)` → Extract key_size parameter
  - Java: `keyPairGenerator.initialize(2048)` → Extract argument. Also check: `KeyPairGeneratorSpec.setKeySize(2048)`

- AES Key Size:
  - Go: `aes.NewCipher(key[:32])` → Extract key length (32 bytes = 256 bits)
  - Python: `algorithms.AES(key[:32])` → Extract key length
  - Java: `Cipher.getInstance("AES/256/GCM/NoPadding")` → Extract from algorithm string

### Cipher Mode Extraction

Pattern (works across languages):

```text
{encryption_function}(mode={mode_value})
```

Language-specific implementations:

- Go: `cipher.NewGCM(block)` → GCM, `cipher.NewCBCEncrypter(block, iv)` → CBC, `cipher.NewECBEncrypter(block)` → ECB (CRITICAL)
- Python: `modes.GCM(iv)` → GCM, `modes.CBC(iv)` → CBC, `modes.ECB()` → ECB (CRITICAL)
- Java: `Cipher.getInstance("AES/GCM/NoPadding")` → GCM, `Cipher.getInstance("AES/CBC/PKCS5Padding")` → CBC, `Cipher.getInstance("AES/ECB/PKCS5Padding")` → ECB (CRITICAL)

### Key Derivation Parameter Extraction

Pattern (works across languages):

```text
{kdf_function}(password, salt, {iterations_or_params}, ...)
```

Language-specific implementations:

- PBKDF2 Iterations:

  - Go: `pbkdf2.Key(password, salt, 100000, 32, sha256.New)` → Extract 3rd argument (100000)
  - Python: `PBKDF2HMAC(..., iterations=100000, ...)` → Extract iterations parameter
  - Java: `new PBEKeySpec(password, salt, 100000, 256)` → Extract 3rd argument (100000)

- Scrypt Parameters (N, r, p):

  - Go: `scrypt.Key(password, salt, 32768, 8, 1, 32)` → N=32768, r=8, p=1
  - Python: `scrypt(..., n_factor=32768, r_factor=8, p_factor=1, ...)` → Extract n/r/p parameters

- Argon2 Parameters (time, memory, threads):
  - Go: `argon2.IDKey(password, salt, 1, 64*1024, 4, 32)` → time=1, memory=65536, threads=4
  - Python: `argon2.hash_password(..., time_cost=1, memory_cost=65536, parallelism=4, ...)` → Extract time/memory/threads

### IV/Nonce Generation Analysis

Pattern (works across languages):

```text
{secure_random_function}(iv, length)
```

Language-specific implementations:

- Secure IV Generation:

  - Go: `crypto/rand.Read(iv)` → SECURE
  - Python: `secrets.token_bytes(12)` → SECURE (for GCM)
  - Java: `SecureRandom.nextBytes(iv)` → SECURE
  - JavaScript: `crypto.randomBytes(12)` → SECURE

- Insecure IV Patterns (CRITICAL):

  - Go: `iv := []byte{0, 1, 2, ...}` → CRITICAL (hardcoded), `iv := make([]byte, 16)` → REVIEW (may not be initialized)
  - Python: `iv = [0, 1, 2, ...]` → CRITICAL (hardcoded)
  - Java: `byte[] iv = {0, 1, 2, ...}` → CRITICAL (hardcoded)

- IV Length Verification:
  - GCM requires 12-byte nonce, CBC requires 16-byte IV
  - Verify IV length matches algorithm requirements
  - Check for IV reuse patterns (same IV used multiple times) by reading file context

### TLS Configuration Extraction

Pattern (works across languages):

```text
{tls_config}(MinVersion={version}, InsecureSkipVerify={bool}, CipherSuites=[...])
```

Language-specific implementations:

- TLS Version:

  - Go: `MinVersion: tls.VersionTLS12` → TLS 1.2, `tls.VersionTLS10` → TLS 1.0 (CRITICAL - deprecated)
  - Python: `ssl.PROTOCOL_TLSv1_2` → TLS 1.2, `ssl.PROTOCOL_TLSv1` → TLS 1.0 (CRITICAL)
  - Java: `SSLContext.getInstance("TLSv1.2")` → TLS 1.2
  - JavaScript: `minVersion: 'TLSv1.2'` → TLS 1.2

- Certificate Validation:

  - Go: `InsecureSkipVerify: true` → CRITICAL (bypasses validation)
  - Python: `ssl._create_unverified_context()` → CRITICAL
  - Java: `setHostnameVerifier(NoopHostnameVerifier.INSTANCE)` → CRITICAL
  - JavaScript: `rejectUnauthorized: false` → CRITICAL

- Cipher Suites:
  - Extract cipher suite list from configuration
  - Flag weak ciphers: `TLS*RSA_WITH*_`, `TLS*DHE_RSA_WITH*_`
  - Read file context to extract full cipher suite list

### Hash Function Context Analysis

#### Password Hashing Detection (All Languages)

```bash
# Function names that suggest password hashing
grep -rE "(hashPassword|hashpassword|hashPwd|hashpwd|passwordHash|password_hash)" --include="*.go" --include="*.py" --include="*.js" --include="*.java" .
# If using raw SHA256/MD5 for password hashing → Flag as INSECURE
# Should use PBKDF2/scrypt/Argon2/bcrypt instead
```

#### Usage Context Detection

```bash
# File integrity / checksum usage (ACCEPTABLE)
grep -rE "(checksum|integrity|verify.file|hash.file)" --include="*.go" --include="*.py" .

# Digital signature usage (SECURE)
grep -rE "(sign|verify.signature|digital.signature)" --include="*.go" --include="*.py" .
```

## Security Assessment Rules

Reference: See `crypto-detection-core` skill (Phase 6: Security Assessment Rules) for complete security assessment rules including:

- RSA Key Size Assessment
- PBKDF2 Iteration Assessment
- Scrypt Parameter Assessment
- AES Mode Assessment
- IV/Nonce Generation Assessment
- TLS Version Assessment
- Certificate Validation Assessment
- Hash Function Context Assessment

Use these rules when evaluating extracted parameters to determine security severity.

## Search Strategy

1. Start broad: Search for crypto-related imports/packages
2. Get specific: Find function calls and usage patterns
3. Check dependencies: Parse package manager files
4. Categorize: Group findings by operation type
5. Extract context: Read files to understand usage

## Example grep Commands

Multi-language search:

```bash
# Find all crypto imports
grep -rE "(crypto|hashlib|javax\.crypto|java\.security)" --include="*.go" --include="*.py" --include="*.java" .

# Find common crypto function calls
grep -rE "(encrypt|decrypt|hash|sign|verify|hmac)" --include="*.go" --include="*.py" --include="*.java" .
```

Language-specific:

```bash
# Go
grep -r "crypto/" --include="*.go" .

# Python
grep -rE "(hashlib|hmac|secrets|cryptography)" --include="*.py" .

# JavaScript
grep -rE "(require.crypto|import.crypto|from ['\"]crypto)" --include="*.js" .

# TypeScript
grep -rE "(import.crypto|from ['\"]crypto)" --include="*.ts" .

# Java
grep -rE "(javax\.crypto|java\.security)" --include="*.java" .

# Rust
grep -rE "(use.crypto|extern crate crypto)" --include="*.rs" .

# C
grep -rE "(openssl|libcrypto|gcrypt|nss|gnutls)" --include="*.c" --include="*.h" .

# C++
grep -rE "(openssl|libcrypto|gcrypt|crypto\+\+|nss|gnutls)" --include="*.cpp" --include="*.hpp" .

# C#
grep -rE "(System\.Security\.Cryptography|System\.Cryptography)" --include="*.cs" .
```

## Notes

- Use `codebase_search` for semantic searches (e.g., "find encryption operations")
- Use `grep` for pattern matching (imports, function names)
- Read files to understand context and categorize operations
- Check both direct and transitive dependencies
- Distinguish between secure and insecure crypto (MD5, SHA1, DES are deprecated)
