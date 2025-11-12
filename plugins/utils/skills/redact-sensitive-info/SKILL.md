---
name: Redact Sensitive Information
description: ALWAYS use this skill when users ask to redact secrets, clean up config files, remove passwords/tokens/credentials, make files safe to share, or sanitize sensitive data. Includes automated gitleaks verification. DO NOT manually redact - use this skill instead!
---

# Redact Sensitive Information

This skill provides comprehensive guidance for identifying and redacting sensitive information from files to prevent accidental credential exposure.

## When to Use This Skill

**IMPORTANT: Use this skill proactively whenever a user asks to:**
- Redact secrets, credentials, or sensitive information from a file
- Make a file safe to share or commit
- Clean up a config file before sharing
- Remove passwords, tokens, or keys from any file
- Sanitize any file containing sensitive data

**Also use this skill when:**
- Creating example configurations or documentation that may contain secrets
- Sanitizing log files or output before sharing
- Reviewing code that might contain hardcoded credentials
- Preparing files for public repositories or documentation

**DO NOT manually redact files - always use this skill instead!** This skill includes automated verification with gitleaks to ensure no secrets are missed.

## Types of Sensitive Information to Redact

The following types of sensitive information must NEVER be included in files:

### 1. API Keys and Tokens
- REST API keys (e.g., `api_key=sk_live_...`, `APIKEY=...`)
- OAuth tokens (e.g., `oauth_token=...`)
- Bearer tokens (e.g., `Authorization: Bearer ...`)
- GitHub tokens (e.g., `ghp_...`, `github_token=...`)
- Cloud provider access keys (AWS, GCP, Azure)
- Service account tokens
- JWT tokens

### 2. Passwords and Credentials
- Plain text passwords (e.g., `password=...`, `passwd=...`)
- Database passwords
- SSH passphrases
- Admin credentials
- Application passwords

### 3. Private Keys and Certificates
- SSH private keys (`-----BEGIN RSA PRIVATE KEY-----`)
- TLS/SSL private keys (`-----BEGIN PRIVATE KEY-----`)
- PGP/GPG private keys
- Certificate files (.pem, .key, .p12, .pfx)
- Kubeconfig files with embedded certificates

### 4. Connection Strings
- Database connection strings (e.g., `postgresql://user:password@host/db`)
- Redis connection strings
- SMTP credentials
- LDAP bind credentials

### 5. Cloud and Infrastructure Secrets
- AWS Access Key IDs and Secret Access Keys
- GCP Service Account JSON files
- Azure Storage Account keys
- Docker registry credentials
- Kubernetes secrets

### 6. Session and Cookie Data
- Session tokens
- Authentication cookies
- CSRF tokens

### 7. Webhooks and URLs with Embedded Credentials
- URLs with basic auth (e.g., `https://user:pass@example.com`)
- Webhook URLs with secret tokens
- Slack webhook URLs
- Discord webhook URLs

### 8. Personal Identifiable Information (PII)
- Email addresses in sensitive contexts
- Phone numbers
- Social Security Numbers
- Credit card numbers

## Implementation Steps

### Step 1: Identify Sensitive Information

**Scan the file for common patterns:**

1. **Look for common secret patterns:**
   - Lines containing: `password`, `passwd`, `pwd`, `secret`, `token`, `api_key`, `apikey`, `private_key`
   - Base64 encoded strings that might be credentials
   - Long alphanumeric strings (potential tokens)
   - URLs with embedded credentials

2. **Check for specific formats:**
   - AWS keys: `AKIA[0-9A-Z]{16}`
   - GitHub tokens: `ghp_[a-zA-Z0-9]{36}`, `github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}`
   - Slack tokens: `xox[baprs]-[0-9a-zA-Z-]+`
   - Private keys: `-----BEGIN.*PRIVATE KEY-----`
   - UUIDs that might be secrets: `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`

### Step 2: Redact the Information

**Use appropriate redaction strategies based on context:**

1. **For configuration examples:**
   ```
   # Before:
   api_key = "abc123_secret_key_xyz789"

   # After:
   api_key = "REDACTED"
   ```

2. **For showing structure while hiding values:**
   ```
   # Before:
   DATABASE_URL=postgresql://admin:MyS3cr3tP@ss@db.example.com:5432/mydb

   # After:
   DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE
   ```

3. **For partial redaction (when showing format is important):**
   ```
   # Before:
   token = "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456"

   # After:
   token = "ghp_************************************"
   ```

4. **For multi-line secrets:**
   ```
   # Before:
   -----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEA...
   ...
   -----END RSA PRIVATE KEY-----

   # After:
   -----BEGIN RSA PRIVATE KEY-----
   REDACTED
   -----END RSA PRIVATE KEY-----
   ```

### Step 3: Verify with Gitleaks

**After redacting, always verify using gitleaks. Prefer container runtimes over binary installation.**

1. **Check for available container runtimes (preferred) or gitleaks binary:**
   ```bash
   # Check for podman (most preferred)
   which podman

   # If not found, check for docker
   which docker

   # If neither found, check for gitleaks binary
   which gitleaks
   ```

2. **Run gitleaks using the best available method:**

   **Option A: Using Podman (preferred)**
   ```bash
   podman run --rm -v "$(pwd):/scan:Z" -w /scan ghcr.io/gitleaks/gitleaks:latest detect --no-git --source /scan/path/to/file --verbose
   ```

   **Option B: Using Docker**
   ```bash
   docker run --rm -v "$(pwd):/scan:Z" -w /scan ghcr.io/gitleaks/gitleaks:latest detect --no-git --source /scan/path/to/file --verbose
   ```

   **Option C: Using Gitleaks Binary**
   ```bash
   gitleaks detect --no-git --source /path/to/file --verbose
   ```

   **Option D: Install Gitleaks (if none available)**
   ```
   /utils:install-gitleaks
   ```
   Then use Option C after installation completes.

   **Important notes for container usage:**
   - Use `$(pwd)` to mount the current working directory as `/scan`
   - File paths in gitleaks args must be relative to `/scan` (e.g., `/scan/config.yaml`)
   - The `:Z` SELinux label is safe on all systems (ignored when not needed)
   - Prefer podman over docker for better security (rootless by default)

3. **Interpret the results:**
   - **No leaks found**: Success! The file is safe to commit/share
   - **Leaks detected**: Review the output, identify missed secrets, and repeat Step 2
   - **Example output with leak:**
     ```
     Finding:     api_key = "sk_live_..."
     Secret:      sk_live_...
     RuleID:      generic-api-key
     File:        config.yaml
     Line:        12
     ```

### Step 4: Double-Check Common Mistakes

**Common patterns that are easy to miss:**

1. **Comments containing secrets:**
   ```
   # Old API key: sk_test_12345  <- Still a leak!
   api_key = "REDACTED"
   ```

2. **Secrets in environment variable examples:**
   ```bash
   export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   ```

3. **Credentials in URLs:**
   ```
   curl https://admin:password@api.example.com/endpoint
   ```

4. **Base64 encoded secrets:**
   ```
   auth_header: "QWxhZGRpbjpvcGVuIHNlc2FtZQ=="  # Base64("username:password")
   ```

5. **Secrets in JSON or YAML:**
   ```yaml
   credentials:
     username: admin
     password: MyP@ssw0rd  <- Redact this!
   ```

## Error Handling

### Gitleaks Not Available

**Problem:** No container runtime (podman/docker) and gitleaks binary not installed

**Solution:**
1. **Preferred**: If you have podman or docker, use the container method (no installation needed)
2. **Alternative**: Install gitleaks binary:
   ```
   /utils:install-gitleaks
   ```

### Container Image Pull Issues

**Problem:** Cannot pull `ghcr.io/gitleaks/gitleaks:latest`

**Solution:**
1. Check internet connectivity
2. Verify access to GitHub Container Registry
3. Fall back to binary installation: `/utils:install-gitleaks`

### Gitleaks Finds False Positives

**Problem:** Gitleaks reports a leak but it's actually a placeholder or example

**Solution:**
1. Review the finding carefully to ensure it's truly a false positive
2. If confirmed safe, document why it's not a real secret
3. Consider using gitleaks ignore comments if needed:
   ```yaml
   password: example123  # gitleaks:allow
   ```

### Unsure if Something is Sensitive

**Problem:** You're not sure if a value should be redacted

**Solution:**
1. **When in doubt, redact it!** It's better to be overly cautious
2. Ask the user if uncertain about specific values
3. Consider the context: Is this a production value? Would it grant access to something?

## Best Practices

1. **Always use gitleaks verification:** Don't rely solely on manual review
2. **Redact completely:** Don't leave partial secrets that could be guessed
3. **Use descriptive placeholders:** Use `YOUR_API_KEY_HERE` instead of just `REDACTED` in examples
4. **Document the redaction:** Add comments explaining what was redacted and why
5. **Check the entire file:** Don't stop at the first secret found
6. **Be consistent:** Use the same redaction style throughout the file

## Examples

### Example 1: Redacting a Configuration File

**Original file (config.yaml):**
```yaml
database:
  host: db.example.com
  port: 5432
  username: admin
  password: MyS3cr3tP@ss

api:
  endpoint: https://api.example.com
  key: abc123_secret_key_xyz789

aws:
  access_key_id: AKIAIOSFODNN7EXAMPLE
  secret_access_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**Redacted file:**
```yaml
database:
  host: db.example.com
  port: 5432
  username: YOUR_DATABASE_USERNAME
  password: YOUR_DATABASE_PASSWORD

api:
  endpoint: https://api.example.com
  key: YOUR_API_KEY_HERE

aws:
  access_key_id: YOUR_AWS_ACCESS_KEY_ID
  secret_access_key: YOUR_AWS_SECRET_ACCESS_KEY
```

**Verification (using podman if available):**
```bash
# Option A: Using podman (preferred)
podman run --rm -v "$(pwd):/scan:Z" -w /scan ghcr.io/gitleaks/gitleaks:latest detect --no-git --source /scan/config.yaml --verbose

# Option B: Using docker
docker run --rm -v "$(pwd):/scan:Z" -w /scan ghcr.io/gitleaks/gitleaks:latest detect --no-git --source /scan/config.yaml --verbose

# Option C: Using binary
gitleaks detect --no-git --source config.yaml --verbose

# Expected output: No leaks found
```

### Example 2: Redacting a Shell Script

**Original file (deploy.sh):**
```bash
#!/bin/bash
export DB_PASSWORD="MyP@ssw0rd123"
export API_TOKEN="ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456"

curl -H "Authorization: Bearer ${API_TOKEN}" \
     https://api.example.com/deploy
```

**Redacted file:**
```bash
#!/bin/bash
export DB_PASSWORD="YOUR_DATABASE_PASSWORD"
export API_TOKEN="YOUR_GITHUB_TOKEN"

curl -H "Authorization: Bearer ${API_TOKEN}" \
     https://api.example.com/deploy
```

### Example 3: Redacting a Python Script

**Original file (app.py):**
```python
import os

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'admin',
    'password': 'admin123',
    'database': 'myapp'
}

# API keys
OPENAI_API_KEY = "openai-key-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
STRIPE_SECRET_KEY = "stripe-key-51AbCdEfGhIjKlMnOp"
```

**Redacted file:**
```python
import os

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'YOUR_DB_USER',
    'password': 'YOUR_DB_PASSWORD',
    'database': 'myapp'
}

# API keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'YOUR_OPENAI_API_KEY')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'YOUR_STRIPE_SECRET_KEY')
```

## Return Value

After successfully redacting sensitive information:
1. The file should contain no actual secrets
2. Gitleaks verification should show "No leaks found"
3. The file should remain functional as an example or template
4. All placeholders should be clearly marked and documented

## Notes

- **Never commit real secrets:** Even in private repositories, secrets can leak
- **Use environment variables:** Prefer environment variables over hardcoded secrets
- **Use secret management:** Consider tools like HashiCorp Vault, AWS Secrets Manager, etc.
- **Rotate exposed secrets:** If a secret is accidentally committed, rotate it immediately
- **Review git history:** Old secrets in git history are still exposed even if removed from current files
