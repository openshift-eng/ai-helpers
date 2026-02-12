# OWASP Top 10:2025 Reference

Quick reference for mapping findings to OWASP categories.

Source: <https://owasp.org/Top10/2025/>

## OWASP Top 10:2025 Categories

| ID | Category | Description | Common CWEs |
|----|----------|-------------|-------------|
| **A01** | Broken Access Control | Missing or improper access restrictions; SSRF now included | CWE-22, CWE-284, CWE-285, CWE-352, CWE-918 |
| **A02** | Security Misconfiguration | Insecure defaults, open cloud storage, verbose errors, missing hardening | CWE-16, CWE-209, CWE-548 |
| **A03** | Software Supply Chain Failures | Vulnerable dependencies, compromised build pipelines, untrusted sources | CWE-426, CWE-494, CWE-829 |
| **A04** | Cryptographic Failures | Weak crypto, exposed keys, missing encryption, improper certificate validation | CWE-259, CWE-327, CWE-328, CWE-330, CWE-331 |
| **A05** | Injection | SQL, NoSQL, OS command, LDAP, XSS injection | CWE-20, CWE-74, CWE-77, CWE-78, CWE-79, CWE-89 |
| **A06** | Insecure Design | Missing threat modeling, insecure architecture patterns | CWE-73, CWE-183, CWE-209, CWE-312 |
| **A07** | Authentication Failures | Broken auth, credential stuffing, weak passwords, session issues | CWE-287, CWE-384, CWE-522, CWE-798 |
| **A08** | Software or Data Integrity Failures | Code/data without integrity verification, insecure deserialization | CWE-345, CWE-353, CWE-426, CWE-502 |
| **A09** | Security Logging and Alerting Failures | Missing audit logs, unmonitored security events | CWE-117, CWE-223, CWE-532, CWE-778 |
| **A10** | Mishandling of Exceptional Conditions | Improper error handling, fail-open logic, unhandled exceptions | CWE-252, CWE-280, CWE-388, CWE-754, CWE-755 |

---

## Pattern to OWASP Mapping

| Security Pattern | OWASP | MITRE | CWE |
|-----------------|-------|-------|-----|
| **Command Injection** | A05 | T1059 | CWE-78 |
| Shell exec with unsanitized input | A05 | T1059 | CWE-78 |
| fmt.Sprintf() building shell commands | A05 | T1059 | CWE-78 |
| **Hardcoded Credentials** | A07 | T1552 | CWE-798 |
| Passwords in source code | A07 | T1552 | CWE-798 |
| API keys in config files | A07 | T1552 | CWE-798 |
| **Broken Access Control** | A01 | T1078 | CWE-284 |
| Missing authorization checks | A01 | T1078 | CWE-285 |
| Path traversal | A01 | T1083 | CWE-22 |
| SSRF | A01 | T1046 | CWE-918 |
| **Cryptographic Failures** | A04 | T1573 | CWE-327 |
| Weak algorithms (MD5, SHA1) | A04 | T1573 | CWE-328 |
| Disabled TLS verification | A04 | T1557 | CWE-295 |
| InsecureSkipVerify = true | A04 | T1557 | CWE-295 |
| **Security Misconfiguration** | A02 | T1562 | CWE-16 |
| Debug mode in production | A02 | T1562 | CWE-489 |
| Privileged containers | A02 | T1611 | CWE-250 |
| **Insecure Deserialization** | A08 | T1059 | CWE-502 |
| pickle.loads(), yaml.load() | A08 | T1059 | CWE-502 |
| **Logging Sensitive Data** | A09 | T1005 | CWE-532 |
| Credentials in logs | A09 | T1005 | CWE-532 |
| **Missing Error Handling** | A10 | - | CWE-754 |
| Unchecked error returns | A10 | - | CWE-252 |
| Fail-open logic | A10 | T1562 | CWE-636 |

---

## TNF-Specific OWASP Mappings

| TNF Component | Risk | OWASP | MITRE | CWE | DFD Elements | PE-* IDs |
|---------------|------|-------|-------|-----|--------------|----------|
| BMC credentials in install-config | Hardcoded secrets | A07 | T1552 | CWE-798 | P1, DS1, DF1, DF2 | PE-P1-I-1, PE-DS1-I-1 |
| BMC password in shell command | Command injection | A05 | T1059 | CWE-78 | P5, DF9 | PE-P5-T-1, PE-P5-I-1 |
| Credentials in CIB XML | Plaintext storage | A04 | T1552 | CWE-312 | DS3, DF7 | PE-DS3-I-1, PE-DF7-I-1 |
| InsecureSkipVerify on BMC | Crypto failure | A04 | T1557 | CWE-295 | P8, DF10 | PE-P8-S-1, PE-DF10-T-1 |
| Privileged TNF setup pods | Misconfiguration | A02 | T1611 | CWE-250 | P3, P4, P5 | PE-P4-E-1, PE-P5-E-1 |
| fencing-credentials Secret | Access control | A01 | T1552 | CWE-284 | DS2, DF4 | PE-DS2-I-1, PE-DS2-T-1 |
| Corosync unencrypted | Crypto failure | A04 | T1557 | CWE-319 | EE3, DF12 | PE-EE3-S-1 |
| PCS token generation | Auth weakness | A07 | T1078 | CWE-330 | P3, DS4, DF5 | PE-P3-S-1, PE-DS4-I-1 |
| Credentials in CLI args | Info exposure | A07 | T1552 | CWE-214 | P6, P8, DF9 | PE-DF9-I-1, PE-P8-I-1 |
| No fencing audit trail | Logging failure | A09 | - | CWE-778 | P5, P6 | PE-P5-R-1, PE-P1-R-1 |

---

## TNA-Specific OWASP Mappings

| TNA Component | Risk | OWASP | MITRE | CWE | DFD Elements | PE-* IDs |
|---------------|------|-------|-------|-----|--------------|----------|
| Arbiter taint as sole scheduling protection | Misconfiguration | A02 | T1562 | CWE-250 | P3 | PE-P3-T-1 |
| Worker ignition token | Credential exposure | A07 | T1552 | CWE-798 | DS6 | PE-DS6-I-1 |
| Worker lateral movement to control plane | Access control | A01 | T1021 | CWE-284 | P5, DS5 | PE-P5-E-1 |
| etcd data on compromised node | Crypto failure | A04 | T1552 | CWE-312 | DS5 | PE-DS5-I-1 |
| Rogue worker CSR approval | Auth failure | A07 | T1078 | CWE-287 | P5, DS6 | PE-P5-S-1 |
| No arbiter taint drift alert | Logging failure | A09 | - | CWE-778 | P3 | PE-P3-T-1 |

---

## OWASP Cheat Sheets

| Topic | URL |
|-------|-----|
| OS Command Injection | <https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html> |
| Secrets Management | <https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html> |
| Input Validation | <https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html> |
| Cryptographic Storage | <https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html> |
| Error Handling | <https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html> |
| Docker Security | <https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html> |
| Kubernetes Security | <https://cheatsheetseries.owasp.org/cheatsheets/Kubernetes_Security_Cheat_Sheet.html> |
