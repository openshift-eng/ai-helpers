# Crypto Inventory Plugin

Find and inventory cryptographic usage across your codebase. Works with Go, Python, Java, JavaScript, TypeScript, Rust, C, C++, and C#.

## Features

- Scans user code and dependencies for crypto usage
- Detects crypto operations across 9 languages
- Extracts parameter values when available (from semgrep metavariables or code snippets)
- Security assessment for critical issues
- Categorizes findings by operation type

## Installation

```bash
/plugin install crypto-inventory@ai-helpers
```

See the main [README.md](/README.md) for marketplace setup.

## Prerequisites

- Read access to source files
- Optional: `semgrep` for better detection (uses GitHub rules, no local install needed)
- Optional: Language toolchains (`go`, `pip`, `npm`, `mvn`, `cargo`) for dependency analysis

Dependency tools are optional - the plugin parses dependency files directly if tools aren't available.

## Available Commands

- `/crypto-inventory:scan` - Generate comprehensive crypto usage inventory (user code + dependencies)
  - See [commands/scan.md](commands/scan.md) for full documentation
- `/crypto-inventory:security` - Security-critical findings and recommendations
  - See [commands/security.md](commands/security.md) for full documentation
- `/crypto-inventory:find` - Search for specific crypto algorithms or APIs
  - See [commands/find.md](commands/find.md) for full documentation

## Parameter Extraction

Extracts parameter values from semgrep results when available:

- Semgrep metavariables: Check `extra.metavars.$VAR.abstract_content` in semgrep output (most reliable)
- Code snippets: Extract literals from `extra.lines` if metavariables aren't available
- Optional script: See `skills/crypto-parameter-extraction/` for complex cases

Security assessment uses extracted parameters to evaluate against thresholds. See `skills/crypto-detection-core/SKILL.md` for assessment rules.

## Supported Languages

- Go: Standard library (`crypto/*`), extended (`golang.org/x/crypto/*`), third-party
- Python: `hashlib`, `hmac`, `secrets`, `cryptography`, `pycryptodome`
- JavaScript: `crypto`, `node:crypto`, `crypto-js`, `node-forge`
- TypeScript: `crypto`, `node:crypto`, `crypto-js`, `node-forge`
- Java: `java.security.*`, `javax.crypto.*`, `org.bouncycastle.*`
- Rust: `ring`, `rustls`, `aes-gcm`, `sha2`, `hmac`
- C: OpenSSL, NSS (Network Security Services), GnuTLS, Libgcrypt, Windows CryptoAPI
- C++: OpenSSL, NSS, GnuTLS, Crypto++, Botan
- C#: `System.Security.Cryptography.*`

## Skills

- crypto-detection-core: Shared logic (language detection, semgrep setup, filtering, security assessment)
- crypto-finder-patterns: Language-specific search patterns
- crypto-parameter-extraction: Optional parameter extraction script
- crypto-semgrep-execution: Semgrep execution and result processing

See `skills/` directory for details.

## Examples

```bash
/crypto-inventory:scan
/crypto-inventory:security
/crypto-inventory:find AES --language go
```

## Troubleshooting

No crypto found: Check that source files exist for detected languages. Try `--language` flag to specify explicitly.

Dependency analysis incomplete: Install language tools (`go`, `pip`, `npm`, etc.) or check dependency files manually.

Language not detected: Use `--language` flag to specify explicitly.

## Contributing

Contributions welcome! Please submit pull requests to the [ai-helpers repository](https://github.com/openshift-eng/ai-helpers).

## License

Apache-2.0
