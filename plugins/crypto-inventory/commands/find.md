---
description: Search for specific cryptographic algorithms, APIs, or operations in the codebase
argument-hint: <algorithm|api> [--language go|python|java|javascript|typescript|rust|c|cpp|csharp|auto] [--format markdown|json] [--output path]
---

## Name

crypto-inventory:find

## Synopsis

```
/crypto-inventory:find <algorithm|api> [--language go|python|java|javascript|typescript|rust|c|cpp|csharp|auto] [--format markdown|json] [--output path]
```

## Description

Searches for specific crypto algorithms or APIs in the codebase.

### Examples

- `/crypto-inventory:find AES` - Find AES encryption usage
- `/crypto-inventory:find SHA256` - Find SHA256 hashing
- `/crypto-inventory:find crypto/rand` - Find secure random in Go
- `/crypto-inventory:find math/rand` - Find insecure random in Go

## Implementation

Follow instructions directly. Do not write scripts. Execute steps using available tools (grep, codebase_search, read_file) and generate the report directly.

### Phase 1: Parse Search Query

1. Extract search term from first argument (algorithm name or API)

2. Normalize search term to lowercase for case-insensitive matching

3. Use `--language` flag if specified, otherwise search all languages

### Phase 2: Language Detection

If `--language` is "auto" or not specified, detect languages using same method as scan command.

### Phase 3: Search for Crypto Usage

1. Build search patterns based on query

   Reference `crypto-finder-patterns` skill to build language-specific patterns:

   For algorithm names (e.g., "AES", "SHA256"):

   ```bash
   # Go
   grep -rE "(AES|aes|Aes)" --include="*.go" .
   grep -rE "(SHA256|sha256|SHA-256)" --include="*.go" .

   # Python
   grep -rE "(AES|aes)" --include="*.py" .
   grep -rE "(sha256|SHA256)" --include="*.py" .

   # JavaScript
   grep -rE "(AES|aes)" --include="*.js" --include="*.ts" .
   grep -rE "(sha256|SHA256)" --include="*.js" --include="*.ts" .
   ```

   For API names (e.g., "crypto/rand", "hashlib"):

   ```bash
   # Go: crypto/rand
   grep -r "crypto/rand" --include="*.go" .

   # Python: hashlib
   grep -rE "(import hashlib|from hashlib)" --include="*.py" .

   # Java: javax.crypto
   grep -rE "(import javax\.crypto|javax\.crypto\.)" --include="*.java" .
   ```

2. Use semantic search for complex queries

   - Use `codebase_search` for semantic queries:
     - "AES encryption" → finds AES usage in encryption context
     - "password hashing" → finds password hashing operations
     - "TLS configuration" → finds TLS/SSL setup

3. Search across all detected languages

   - Run language-specific searches in parallel
   - Collect all matches

### Phase 4: Filter and Categorize Results

1. Filter out false positives

   - Exclude comments and documentation (read file context)
   - Exclude vendor/dependency directories
   - Exclude test files (unless explicitly requested)
   - Exclude build artifacts

2. Categorize findings

   - Import/Include: Where the crypto API is imported
   - Function Calls: Where crypto functions are called
   - Variable Assignments: Where crypto values are assigned
   - Type Definitions: Where crypto types are defined

3. Extract context (optimized)

   - Batch matches by file before reading
   - Read file once per file (not per match)
   - Cache file contents during processing
   - For each match:
     - Read 5-10 lines around match (not entire file)
     - Identify function/method name
     - Extract code snippet (3-5 lines)
     - Understand usage context

### Phase 5: Generate Search Report

1. Create Report Structure

   - Location: `.work/crypto-inventory/find/{query}/report.md` (or user-specified path)
   - Format: Markdown (default) or JSON (if `--format json`)
   - Create directory if needed: `mkdir -p .work/crypto-inventory/find/{query}/`

2. Report Sections:

   **Search Summary** - Include query, timestamp, codebase path, languages scanned, and match counts.

   **Results by Language** - Group findings by language with subsections:

   - **Import Statements** - Table showing files, line numbers, and import statements
   - **Function Calls** - Table showing files, line numbers, functions, and context
   - **Code Snippets** - Show actual code with file:line headers

   Example structure:

   ```markdown
   # Crypto Search Results

   Query: "{search-term}"
   Generated: {timestamp}
   Codebase: {workspace-path}
   Languages Scanned: {list}

   ## Summary

   - Total Matches: {count}
   - Files: {count}
   - Languages: {list}

   ## Results

   ### Go

   #### Import Statements ({count})

   | File           | Line | Import Statement    |
   | -------------- | ---- | ------------------- |
   | pkg/crypto.go  | 5    | import "crypto/aes" |
   | pkg/encrypt.go | 12   | import "crypto/aes" |

   #### Function Calls ({count})

   | File           | Line | Function             | Context                  |
   | -------------- | ---- | -------------------- | ------------------------ |
   | pkg/encrypt.go | 45   | cipher.NewGCM(block) | AES-GCM encryption setup |
   | pkg/storage.go | 89   | aes.NewCipher(key)   | AES cipher creation      |

   #### Code Snippets

   pkg/encrypt.go:45
   [code snippet shown here]

   ### Python

   [similar structure for Python]

   ## Usage Context

   ### Encryption Operations ({count})

   - AES-GCM encryption in pkg/encrypt.go
   - AES-CBC encryption in pkg/storage.go

   ### Hashing Operations ({count})

   - SHA256 hashing in pkg/auth.go
   - SHA512 hashing in pkg/audit.go
   ```

   For code snippets within the report, show them inline with file:line headers:

   ```go
   pkg/encrypt.go:45
   block, _ := aes.NewCipher(key)
   gcm, _ := cipher.NewGCM(block)
   ciphertext := gcm.Seal(nil, nonce, plaintext, nil)
   ```

3. Format Output

   - Use clear Markdown formatting
   - Group by language and category
   - Include code snippets for context
   - For JSON format, use structured data

### Phase 6: Display Results

1. Display summary

   ```text
   Search complete!

   Query: "AES"
   Matches found: 12
   Files: 5
   Languages: Go, Python

   Report saved to: .work/crypto-inventory/find/AES/report.md
   ```

2. Show quick preview (top 5 matches)

   ```text
   Quick Preview:

   1. pkg/encrypt.go:45 - AES-GCM encryption
   2. pkg/storage.go:89 - AES-CBC encryption
   3. src/crypto.py:12 - AES cipher setup
   ...
   ```

## Return Value

- Format: Markdown report at `.work/crypto-inventory/find/{query}/report.md` (or specified path)
- Content:
  - Search summary
  - Results grouped by language
  - Code snippets and context
  - Usage categorization

## Examples

1. Find AES usage:

   ```bash
   /crypto-inventory:find AES
   ```

   Searches for all AES-related code

2. Find SHA256 in Go only:

   ```bash
   /crypto-inventory:find SHA256 --language go
   ```

   Only searches Go files for SHA256

3. Find insecure random:

   ```bash
   /crypto-inventory:find math/rand
   ```

   Finds insecure random usage in Go

4. Find specific API:

   ```bash
   /crypto-inventory:find hashlib --language python
   ```

   Finds hashlib usage in Python

## Arguments

- `<algorithm|api>`: Required. The cryptographic algorithm, API, or operation to search for
  - Examples: "AES", "SHA256", "crypto/rand", "hashlib", "javax.crypto"
- `--format`: Output format (markdown|json). Default: markdown
- `--output`: Output file path. Default: `.work/crypto-inventory/find/{query}/report.md`
- `--language`: Specific language to scan (go|python|java|javascript|typescript|rust|c|cpp|csharp|auto). Default: auto (detect all)

## Notes

- Searches user code only (excludes vendor/dependencies by default)
- Case-insensitive searches
- Uses grep and semantic search
- Includes code snippets and usage context

## Prerequisites

- Read access to source files in the workspace
- No additional tools required (uses grep and codebase_search)
